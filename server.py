import http.server
import json
import os
import socketserver
import subprocess
import threading
import time
from urllib.parse import urlparse, parse_qs

# Serve files from the clawd-dash directory
os.chdir('/home/tang0115/clawd-dash')

PORT = 8080

# Last time one of *my* machines reported Claude activity (via a Claude Code
# hook hitting /heartbeat). The dashboard only wakes from the screensaver on a
# usage change if this is recent, so a friend sharing the account, or me using
# Claude away from home, doesn't wake it. In-memory only; resets on restart.
last_heartbeat = None

# HomeKit control (via the homebridge-clawd-dash plugin). `mode` is which view
# the dashboard shows: 'auto' is the normal idle/wake screensaver logic, the
# rest force that view until changed. Persisted outside the repo since
# auto-update restarts this server on every push; it changes rarely, so the
# SD card writes are negligible (unlike usage.json).
#
# This list is the single source of truth for the HomeKit inputs: the plugin
# picks up additions/removals/renames on its next poll, no Homebridge restart.
# To add a screensaver, add it here (id -> name shown in the Home app) and
# handle the id in dashboard.html's applyControlMode/refreshScreensaverMode.
MODES = {
    'auto':       'Auto',
    'dashboard':  'Claude Usage',
    'dvd':        'DVD Bounce',
    'news':       'News',
    'nowplaying': 'Now Playing',
    'onthisday':  'On This Day',
    'jev':        'Jev Trading',
}

# Live-stream screensavers: id -> (name in the Home app, YouTube video ID).
# Each becomes its own HomeKit input and plays full-screen and muted, with
# no dashboard code needed per stream — adding one is just a line here. Only
# use streams that run 24/7 and allow embedding.
STREAMS = {
    'reef':     ('Tropical Reef', 'DHUnz4dyb54'),  # Aquarium of the Pacific, via explore.org
    'sharks':   ('Shark Cam',     'tEtg5Kg3voQ'),  # Monterey Bay Aquarium
    'aquarium': ('Aquarium 4K',   'nd_ildQK6wc'),  # Francis's Aquarium 4K
    'fishtank': ('Fish Tank',     'k0F4jTkhklI'),  # Cat TV Fish Tank 4K
}
MODES.update({k: name for k, (name, _) in STREAMS.items()})
CONTROL_PATH = os.path.expanduser('~/.clawd_control.json')

# Power is the HDMI output itself, toggled through the Wayland compositor.
# This runs as a systemd service with no session env, so point wlr-randr at
# the desktop session's socket explicitly.
DISPLAY_OUTPUT = 'HDMI-A-1'
WAYLAND_ENV = dict(os.environ, WAYLAND_DISPLAY='wayland-0',
                   XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}')
POWER_CACHE_SECS = 10  # dashboard polls /control every second; don't spawn wlr-randr that often

control_lock = threading.Lock()
power_cache = {'value': True, 'checked': 0.0}

def load_mode():
    try:
        with open(CONTROL_PATH) as f:
            mode = json.load(f).get('mode')
        return mode if mode in MODES else 'auto'
    except Exception:
        return 'auto'

def save_mode(mode):
    with open(CONTROL_PATH, 'w') as f:
        json.dump({'mode': mode}, f)

current_mode = load_mode()

def wlr_randr(*args):
    return subprocess.run(['wlr-randr', *args], env=WAYLAND_ENV,
                          capture_output=True, text=True, timeout=5)

def get_power():
    now = time.monotonic()
    if now - power_cache['checked'] >= POWER_CACHE_SECS:
        try:
            out = wlr_randr('--output', DISPLAY_OUTPUT).stdout
            power_cache['value'] = 'Enabled: yes' in out
        except Exception:
            pass  # compositor not up yet (early boot) — keep last known value
        power_cache['checked'] = now
    return power_cache['value']

def set_power(on):
    result = wlr_randr('--output', DISPLAY_OUTPUT, '--on' if on else '--off')
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or 'wlr-randr failed')
    power_cache['value'] = on
    power_cache['checked'] = time.monotonic()

class Handler(http.server.SimpleHTTPRequestHandler):
    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _control(self, query):
        global current_mode
        with control_lock:
            try:
                if 'mode' in query:
                    mode = query['mode'][0]
                    if mode not in MODES:
                        return self._json({'error': f'unknown mode {mode!r}', 'modes': list(MODES)}, 400)
                    if mode != current_mode:
                        current_mode = mode
                        save_mode(mode)
                if 'power' in query:
                    set_power(query['power'][0] in ('1', 'on', 'true'))
                self._json({
                    'power': get_power(),
                    'mode': current_mode,
                    'modes': [
                        {'id': k, 'name': v, **({'video': STREAMS[k][1]} if k in STREAMS else {})}
                        for k, v in MODES.items()
                    ],
                })
            except Exception as e:
                self._json({'error': str(e)}, 500)

    def do_GET(self):
        global last_heartbeat
        url = urlparse(self.path)
        if url.path == '/heartbeat':
            last_heartbeat = time.monotonic()
            self.send_response(204)
            self.end_headers()
        elif url.path == '/heartbeat_age':
            age = None if last_heartbeat is None else time.monotonic() - last_heartbeat
            self._json({'age': age})
        elif url.path == '/control':
            self._control(parse_qs(url.query))
        else:
            super().do_GET()

    do_POST = do_GET

socketserver.ThreadingTCPServer.allow_reuse_address = True

with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
    print(f"Serving on port {PORT}")
    httpd.serve_forever()

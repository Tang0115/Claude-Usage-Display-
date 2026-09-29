import http.server
import json
import socketserver
import os
import time

# Serve files from the clawd-dash directory
os.chdir('/home/tang0115/clawd-dash')

PORT = 8080

# Last time one of *my* machines reported Claude activity (via a Claude Code
# hook hitting /heartbeat). The dashboard only wakes from the screensaver on a
# usage change if this is recent, so a friend sharing the account, or me using
# Claude away from home, doesn't wake it. In-memory only; resets on restart.
last_heartbeat = None

class Handler(http.server.SimpleHTTPRequestHandler):
    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        global last_heartbeat
        path = self.path.split('?')[0]
        if path == '/heartbeat':
            last_heartbeat = time.monotonic()
            self.send_response(204)
            self.end_headers()
        elif path == '/heartbeat_age':
            age = None if last_heartbeat is None else time.monotonic() - last_heartbeat
            self._json({'age': age})
        else:
            super().do_GET()

    do_POST = do_GET

socketserver.ThreadingTCPServer.allow_reuse_address = True

with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
    print(f"Serving on port {PORT}")
    httpd.serve_forever()

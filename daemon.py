import json
import os
import requests
import threading
import time
from datetime import datetime, timezone
import psutil

CREDENTIALS_PATH = '/home/tang0115/.claude/.credentials.json'
USAGE_PATH       = '/home/tang0115/clawd-dash/usage.json'
OAUTH_REFRESH_URL = 'https://platform.claude.com/v1/oauth/token'
EXPIRY_BUFFER_SECS = 300  # refresh 5 min before actual expiry

# Lives outside the repo (home directory) so it's never committed/pushed.
# Written by spotify_auth_setup.py. Absent = Spotify widget just stays off.
SPOTIFY_CREDENTIALS_PATH = os.path.expanduser('~/.spotify_credentials.json')
SPOTIFY_TOKEN_URL       = 'https://accounts.spotify.com/api/token'
SPOTIFY_NOWPLAYING_URL  = 'https://api.spotify.com/v1/me/player'

# Only show/fast-poll now-playing when it's active on one of these Connect
# devices (matched case-insensitively against the API's device.name). Keeps
# long car drives (which report as a different device) from hammering the
# API at PLAYING_INTERVAL for hours straight.
SPOTIFY_ALLOWED_DEVICES = {"tom's mac", "tomtang0115"}

def load_creds():
    with open(CREDENTIALS_PATH) as f:
        return json.load(f)

def save_creds(creds):
    with open(CREDENTIALS_PATH, 'w') as f:
        json.dump(creds, f, indent=2)

def is_expired(creds):
    expires_at_ms = creds['claudeAiOauth']['expiresAt']
    now = datetime.now(timezone.utc).timestamp()
    return now >= (expires_at_ms / 1000) - EXPIRY_BUFFER_SECS

def do_refresh_request(refresh_token_value):
    return requests.post(
        OAUTH_REFRESH_URL,
        json={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token_value,
            'client_id': '9d1c250a-e61b-44d9-88ed-5944d1962f5e'
        }
    )

def refresh_token(creds):
    print("Refreshing access token...", flush=True)
    resp = do_refresh_request(creds['claudeAiOauth']['refreshToken'])

    if resp.status_code == 400:
        # Our in-memory refresh token may be stale because another process
        # (e.g. the Claude Code CLI itself) already rotated it on disk.
        # Reload the current credentials and retry once before giving up.
        print("Refresh got 400 — reloading credentials from disk and retrying...", flush=True)
        creds = load_creds()
        resp = do_refresh_request(creds['claudeAiOauth']['refreshToken'])

    resp.raise_for_status()
    data = resp.json()

    creds['claudeAiOauth']['accessToken'] = data['access_token']
    if 'refresh_token' in data:
        creds['claudeAiOauth']['refreshToken'] = data['refresh_token']
    if 'expires_in' in data:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        creds['claudeAiOauth']['expiresAt'] = now_ms + data['expires_in'] * 1000

    save_creds(creds)
    print(f"Token refreshed, expires at {creds['claudeAiOauth']['expiresAt']}")
    return creds

def ensure_fresh(creds):
    if is_expired(creds):
        creds = refresh_token(creds)
    return creds

def call_api(access_token):
    return requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        },
        json={
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 1,
            'messages': [{'role': 'user', 'content': 'hi'}]
        }
    )

def get_usage(creds):
    resp = call_api(creds['claudeAiOauth']['accessToken'])

    if resp.status_code == 401:
        print("Got 401, forcing token refresh and retrying...")
        creds = refresh_token(creds)
        resp = call_api(creds['claudeAiOauth']['accessToken'])

    resp.raise_for_status()
    h = resp.headers

    session_pct = float(h.get('anthropic-ratelimit-unified-5h-utilization', 0)) * 100
    weekly_pct  = float(h.get('anthropic-ratelimit-unified-7d-utilization', 0)) * 100

    now = datetime.now(timezone.utc).timestamp()
    session_reset_ts = float(h.get('anthropic-ratelimit-unified-5h-reset', 0))
    weekly_reset_ts  = float(h.get('anthropic-ratelimit-unified-7d-reset', 0))

    return {
        'session': round(session_pct, 2),
        'weekly':  round(weekly_pct, 2),
        'session_reset_mins': max(0, int((session_reset_ts - now) / 60)),
        'weekly_reset_mins':  max(0, int((weekly_reset_ts  - now) / 60))
    }, creds


def get_pi_stats():
    cpu = round(psutil.cpu_percent(interval=0.5), 1)
    ram = round(psutil.virtual_memory().percent, 1)
    temp = None
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            temp = round(int(f.read().strip()) / 1000, 1)
    except Exception:
        try:
            for vals in psutil.sensors_temperatures().values():
                if vals:
                    temp = round(vals[0].current, 1)
                    break
        except Exception:
            pass
    return {'cpu': cpu, 'ram': ram, 'temp': temp}


class SpotifyRateLimited(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after

def load_spotify_creds():
    if not os.path.exists(SPOTIFY_CREDENTIALS_PATH):
        return None
    with open(SPOTIFY_CREDENTIALS_PATH) as f:
        return json.load(f)

def save_spotify_creds(creds):
    with open(SPOTIFY_CREDENTIALS_PATH, 'w') as f:
        json.dump(creds, f, indent=2)
    os.chmod(SPOTIFY_CREDENTIALS_PATH, 0o600)

def spotify_is_expired(creds):
    now = datetime.now(timezone.utc).timestamp()
    return now >= (creds['expires_at'] / 1000) - EXPIRY_BUFFER_SECS

def spotify_refresh(creds):
    resp = requests.post(SPOTIFY_TOKEN_URL, data={
        'grant_type': 'refresh_token',
        'refresh_token': creds['refresh_token'],
        'client_id': creds['client_id'],
        'client_secret': creds['client_secret'],
    })
    resp.raise_for_status()
    data = resp.json()

    creds['access_token'] = data['access_token']
    if 'refresh_token' in data:
        creds['refresh_token'] = data['refresh_token']
    creds['expires_at'] = int(datetime.now(timezone.utc).timestamp() * 1000) + data['expires_in'] * 1000

    save_spotify_creds(creds)
    return creds

def get_now_playing(creds):
    """Returns (usage_fields, creds). No-ops if Spotify isn't set up."""
    if creds is None:
        return {'spotify_playing': False}, creds

    if spotify_is_expired(creds):
        creds = spotify_refresh(creds)

    # additional_types=episode is required for Spotify to include podcast
    # episode data in the response at all; without it, 'item' comes back
    # null/track-shaped even while currently_playing_type says 'episode'.
    resp = requests.get(
        SPOTIFY_NOWPLAYING_URL,
        headers={'Authorization': f"Bearer {creds['access_token']}"},
        params={'additional_types': 'episode'},
        timeout=5
    )
    if resp.status_code == 401:
        creds = spotify_refresh(creds)
        resp = requests.get(
            SPOTIFY_NOWPLAYING_URL,
            headers={'Authorization': f"Bearer {creds['access_token']}"},
            params={'additional_types': 'episode'},
            timeout=5
        )

    if resp.status_code == 429:
        # Back off for as long as Spotify asks so we stop compounding the
        # rate limit; the loop's own sleep is too short to recover from this.
        retry_after = int(resp.headers.get('Retry-After', 5))
        raise SpotifyRateLimited(retry_after)

    if resp.status_code == 204 or not resp.content:
        return {'spotify_playing': False}, creds

    resp.raise_for_status()
    data = resp.json()
    item = data.get('item')
    if not item or not data.get('is_playing'):
        return {'spotify_playing': False}, creds

    # Spotify sends a curly apostrophe (’) in device names like "Tom's
    # Mac", not a straight one, so normalize before matching the allow-list.
    device_name = (data.get('device') or {}).get('name', '')
    device_name_normalized = device_name.strip().lower().replace('’', "'")
    if device_name_normalized not in SPOTIFY_ALLOWED_DEVICES:
        return {'spotify_playing': False}, creds

    # Episodes (podcasts) use a 'show' object instead of 'album'/'artists'.
    # Spotify deprecated 'show.publisher' and no longer populates it, and
    # episodes have no per-item artist anyway, so podcasts have no artist_name
    # at all — the frontend displays show name in the artist slot instead.
    is_podcast = data.get('currently_playing_type') == 'episode' or 'show' in item
    if is_podcast:
        show = item.get('show', {})
        images = item.get('images') or show.get('images', [])
        album_name = show.get('name')
        artist_name = None
    else:
        album_obj = item.get('album', {})
        images = album_obj.get('images', [])
        album_name = album_obj.get('name')
        artist_name = ', '.join(a['name'] for a in item.get('artists', []))

    return {
        'spotify_playing': True,
        'spotify_is_podcast': is_podcast,
        'spotify_track': item.get('name'),
        'spotify_album': album_name,
        'spotify_artist': artist_name,
        'spotify_album_art': images[0]['url'] if images else None,
        'spotify_progress_ms': data.get('progress_ms', 0),
        'spotify_duration_ms': item.get('duration_ms', 0),
    }, creds


creds = load_creds()
spotify_creds = load_spotify_creds()

# Shared in-memory snapshot written to usage.json. Claude usage/Pi stats
# (slow, 15s) and Spotify now-playing (fast, 1s) update it from separate
# loops so a quick song switch doesn't wait on the slow Claude usage poll.
usage_lock = threading.Lock()
usage_state = {}

def merge_and_write(fields):
    with usage_lock:
        usage_state.update(fields)
        with open(USAGE_PATH, 'w') as f:
            json.dump(usage_state, f)

def spotify_loop():
    global spotify_creds
    # Fast polling is only useful while something's actually playing (for the
    # marquee/progress bar). Idling at the same cadence just burns quota
    # against Spotify's rate limit for no benefit, so back off while idle.
    PLAYING_INTERVAL = 2
    IDLE_INTERVAL = 20
    while True:
        sleep_secs = IDLE_INTERVAL
        try:
            spotify_data, spotify_creds = get_now_playing(spotify_creds)
            if spotify_data.get('spotify_playing'):
                sleep_secs = PLAYING_INTERVAL
        except SpotifyRateLimited as e:
            print(f"Spotify rate limited, backing off {e.retry_after}s")
            spotify_data = {'spotify_playing': False}
            sleep_secs = e.retry_after
        except Exception as e:
            print(f"Spotify error: {e}")
            spotify_data = {'spotify_playing': False}
        merge_and_write(spotify_data)
        time.sleep(sleep_secs)

while True:
    try:
        creds = ensure_fresh(creds)
        print("Startup token check passed.")
        break
    except Exception as e:
        print(f"Startup retry (network not ready?): {e}")
        time.sleep(10)

threading.Thread(target=spotify_loop, daemon=True).start()

while True:
    try:
        creds = ensure_fresh(creds)
        usage, creds = get_usage(creds)
        usage.update(get_pi_stats())
        merge_and_write(usage)
        print(f"Updated: {usage_state}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(15)

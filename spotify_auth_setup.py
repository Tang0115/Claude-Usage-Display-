#!/usr/bin/env python3
"""One-time interactive OAuth setup for the Spotify now-playing widget.

Run this manually (not as a service). It asks for your Spotify app's
Client ID/Secret at the prompt (never hardcoded, never written into the
repo) and walks through the OAuth authorization-code flow. The resulting
tokens are saved to ~/.spotify_credentials.json, outside the repo
directory, so they can never be committed or pushed to GitHub.

If the machine running this script has no browser (e.g. a headless Pi
over SSH), run it on your laptop instead and scp the resulting
~/.spotify_credentials.json to the Pi's home directory, then restart
clawd-daemon.
"""
import http.server
import json
import os
import time
import urllib.parse
import webbrowser

import requests

REDIRECT_URI = 'http://127.0.0.1:8888/callback'
SCOPE = 'user-read-currently-playing user-read-playback-state'
CREDS_PATH = os.path.expanduser('~/.spotify_credentials.json')

auth_result = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        if 'code' in params:
            auth_result['code'] = params['code'][0]
            self.wfile.write(b'<html><body><h2>Spotify authorized. You can close this tab.</h2></body></html>')
        else:
            auth_result['error'] = params.get('error', ['unknown_error'])[0]
            self.wfile.write(b'<html><body><h2>Authorization failed. Check the terminal.</h2></body></html>')

    def log_message(self, *args):
        pass


def main():
    print("=== Spotify now-playing setup ===")
    print("1. Go to https://developer.spotify.com/dashboard and create an app.")
    print(f"2. Set its Redirect URI to exactly: {REDIRECT_URI}")
    print()
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()

    auth_url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPE,
    })
    print(f"\nOpen this URL and approve access:\n{auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    server = http.server.HTTPServer(('127.0.0.1', 8888), CallbackHandler)
    print("Waiting for the Spotify redirect on http://127.0.0.1:8888 ...")
    while 'code' not in auth_result and 'error' not in auth_result:
        server.handle_request()

    if 'error' in auth_result:
        raise SystemExit(f"Spotify returned an error: {auth_result['error']}")

    resp = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'authorization_code',
        'code': auth_result['code'],
        'redirect_uri': REDIRECT_URI,
        'client_id': client_id,
        'client_secret': client_secret,
    })
    resp.raise_for_status()
    data = resp.json()

    creds = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': data['refresh_token'],
        'access_token': data['access_token'],
        'expires_at': int(time.time() * 1000) + data['expires_in'] * 1000,
    }
    with open(CREDS_PATH, 'w') as f:
        json.dump(creds, f, indent=2)
    os.chmod(CREDS_PATH, 0o600)

    print(f"\nSaved credentials to {CREDS_PATH}")
    print("This file lives outside the repo and is never committed or pushed.")
    print("Restart the daemon to pick it up: sudo systemctl restart clawd-daemon")


if __name__ == '__main__':
    main()

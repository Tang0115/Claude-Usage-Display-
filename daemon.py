import json
import requests
import time
from datetime import datetime, timezone

CREDENTIALS_PATH = '/home/tang0115/.claude/.credentials.json'
USAGE_PATH       = '/home/tang0115/clawd-dash/usage.json'
OAUTH_REFRESH_URL = 'https://claude.ai/api/auth/oauth/token'
EXPIRY_BUFFER_SECS = 300  # refresh 5 min before actual expiry

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

def refresh_token(creds):
    print("Refreshing access token...")
    resp = requests.post(
        OAUTH_REFRESH_URL,
        json={
            'grant_type': 'refresh_token',
            'refresh_token': creds['claudeAiOauth']['refreshToken']
        }
    )
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


creds = load_creds()
creds = ensure_fresh(creds)

while True:
    try:
        creds = ensure_fresh(creds)
        usage, creds = get_usage(creds)
        with open(USAGE_PATH, 'w') as f:
            json.dump(usage, f)
        print(f"Updated: {usage}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(60)

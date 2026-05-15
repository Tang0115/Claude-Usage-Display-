import json
import requests
import time
from datetime import datetime, timezone

# Load credentials
with open('/home/tang0115/.claude/.credentials.json') as f:
    creds = json.load(f)

token = creds['claudeAiOauth']['accessToken']

def get_usage():
    response = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        },
        json={
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 1,
            'messages': [{'role': 'user', 'content': 'hi'}]
        }
    )

    h = response.headers

    # Usage percentages
    session_pct = float(h.get('anthropic-ratelimit-unified-5h-utilization', 0)) * 100
    weekly_pct  = float(h.get('anthropic-ratelimit-unified-7d-utilization', 0)) * 100

    # Reset timestamps (Unix seconds) — convert to minutes from now
    now = datetime.now(timezone.utc).timestamp()

    session_reset_ts = float(h.get('anthropic-ratelimit-unified-5h-reset', 0))
    weekly_reset_ts  = float(h.get('anthropic-ratelimit-unified-7d-reset', 0))

    session_reset_mins = max(0, int((session_reset_ts - now) / 60))
    weekly_reset_mins  = max(0, int((weekly_reset_ts  - now) / 60))

    return {
        'session': round(session_pct, 2),
        'weekly':  round(weekly_pct, 2),
        'session_reset_mins': session_reset_mins,
        'weekly_reset_mins':  weekly_reset_mins
    }

while True:
    try:
        usage = get_usage()
        with open('/home/tang0115/clawd-dash/usage.json', 'w') as f:
            json.dump(usage, f)
        print(f"Updated: {usage}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(60)

# Claude Usage Display

A Raspberry Pi desk dashboard that shows your Claude Code usage in real time — session and weekly limits with live countdowns, local weather, and Pi system stats.


## What it does

- Shows your current 5h session usage %
- Shows your 7-day weekly usage %
- Countdown timers to each reset
- Color-coded warnings as you approach limits (yellow at 70%, red at 90%)
- Animated Claude logo with pulsing red heartbeat glow when usage hits 80%+ — logo also swaps to an alert image
- "Resetting soon" celebration mode when session reset is under 5 minutes — swaps to a celebration image then reverts automatically
- DVD-style screensaver after 10 minutes of no usage change — bounces wall-to-wall, alternates images on each wall hit, wakes automatically when usage updates
- Live status indicator shows LIVE / SYNCING / ERROR based on connection state
- **Weather widget** — auto-detects the Pi's location via IP geolocation and shows current temperature (°F), weather icon, and condition using the Open-Meteo API (free, no key needed). Updates every 10 minutes
- **Pi system stats** — displays live CPU %, RAM %, and CPU temperature pulled from `usage.json` and updated every 60 seconds
- Auto-refreshes every 60 seconds
- Launches automatically on boot

## Hardware

- Raspberry Pi 5 (1GB+)
- Any HDMI monitor or screen (tested on ROADOM 10.1" touchscreen)
- MicroSD card (16GB+)
- USB-C power supply

## Requirements

- Raspberry Pi OS (64-bit)
- Python 3
- Active Claude Code subscription
- Your `~/.claude/.credentials.json` from a machine with Claude Code installed

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/Tang0115/Claude-Usage-Display-.git
cd Claude-Usage-Display-
```

**2. Copy your Claude credentials onto the Pi**
```bash
mkdir -p ~/.claude
nano ~/.claude/.credentials.json
# Paste the contents of ~/.claude/.credentials.json from your main machine
```

**3. Install dependencies**
```bash
pip3 install requests psutil --break-system-packages
```

**4. Set up systemd services**
```bash
sudo cp clawd-daemon.service /etc/systemd/system/
sudo cp clawd-server.service /etc/systemd/system/
sudo systemctl enable clawd-daemon clawd-server
sudo systemctl start clawd-daemon clawd-server
```

**5. Set up autostart for the dashboard**
```bash
mkdir -p ~/.config/autostart
cp clawd-dash.desktop ~/.config/autostart/
```

**6. Reboot**
```bash
sudo reboot
```

The dashboard will launch automatically on every boot.

## How it works

- `daemon.py` — polls the Anthropic API every 60 seconds using your OAuth token and writes usage data to `usage.json`. Also reads CPU %, RAM %, and CPU temperature via `psutil` and appends them to the same file. Automatically refreshes the access token when it expires (or 5 minutes before) using the refresh token from `~/.claude/.credentials.json` — no manual intervention needed. On boot, retries the initial token check until the network is available
- `server.py` — serves the dashboard files over a local HTTP server on port 8080
- `dashboard.html` — the frontend that reads `usage.json` every 60 seconds and displays usage, Pi stats, and a weather widget. Weather uses IP geolocation (`ipapi.co`) to auto-detect the Pi's location and fetches conditions from Open-Meteo every 10 minutes

## Auto-update from GitHub

The Pi checks for updates from this repo every 5 minutes via cron and automatically restarts services if anything changed.

## Credits

Inspired by [Clawdmeter](https://github.com/HermannBjorgvin/Clawdmeter) by HermannBjorgvin.

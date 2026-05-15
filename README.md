# Claude Usage Display

A Raspberry Pi desk dashboard that shows your Claude Code usage in real time — session and weekly limits with live countdowns.

![Dashboard](https://raw.githubusercontent.com/Tang0115/Claude-Usage-Display-/main/screenshots/dashboard.png)

## What it does

- Shows your current 5h session usage %
- Shows your 7-day weekly usage %
- Countdown timers to each reset
- Color-coded warnings as you approach limits (yellow at 70%, red at 90%)
- Animated Claude logo with red ambient glow when usage hits 80%+ — logo also swaps to an alert image
- DVD-style screensaver after 10 minutes of no usage change — bounces wall-to-wall and wakes automatically when usage updates
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
pip3 install requests --break-system-packages
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

- `daemon.py` — polls the Anthropic API every 60 seconds using your OAuth token and writes usage data to `usage.json`
- `server.py` — serves the dashboard files over a local HTTP server on port 8080
- `dashboard.html` — the frontend that reads `usage.json` and displays usage with animated progress bars and countdown timers

## Auto-update from GitHub

The Pi checks for updates from this repo every 5 minutes via cron and automatically restarts services if anything changed.

## Credits

Inspired by [Clawdmeter](https://github.com/HermannBjorgvin/Clawdmeter) by HermannBjorgvin.

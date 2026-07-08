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
- **Pi system stats** — displays live CPU %, RAM %, and CPU temperature pulled from `usage.json` and updated every 15 seconds
- **Spotify now playing** — while the screensaver is active, shows album art on the left and track name / album name / artist on the right, with a live progress bar. Track and album names marquee-scroll if they're too long to fit on one line. The background dynamically recolors per song, sampled from the album art itself (darkened/desaturated for readability) with a soft vignette, and falls back to the plain black DVD-bounce screensaver when nothing's playing. Also works for podcast episodes (episode/show/publisher in place of track/album/artist) and Spotify DJ sessions. Polled every 1 second for near-instant track-change detection — decoupled from the slower Claude usage poll so it never affects your rate-limit quota. Also swaps the mascot to a headphones image on the main (non-screensaver) view whenever something's playing. Optional — everything above still works without it
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

**6. (Optional) Set up the Spotify now-playing widget**

This is a one-time interactive step done outside of git, so your Spotify API keys are never written into this repo or pushed to GitHub.

1. Create an app at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and add `http://127.0.0.1:8888/callback` as a Redirect URI in the app's settings.
2. Run the setup script and follow the prompts (it opens a browser to authorize, then saves tokens to `~/.spotify_credentials.json` — outside the repo directory, never committed):
   ```bash
   python3 spotify_auth_setup.py
   ```
   If the Pi is headless (no browser), run this step on your laptop instead and `scp` the resulting `~/.spotify_credentials.json` over to the Pi's home directory.
3. Restart the daemon so it picks up the new credentials:
   ```bash
   sudo systemctl restart clawd-daemon
   ```

**7. Reboot**
```bash
sudo reboot
```

The dashboard will launch automatically on every boot.

## How it works

- `daemon.py` — runs two independent loops that both write to `usage.json`: the main loop polls the Anthropic API every 15 seconds using your OAuth token for usage data, and Pi stats (CPU %, RAM %, CPU temp via `psutil`); a background thread polls Spotify's currently-playing endpoint every 1 second (if set up) for track/album/artist/art/progress — including podcast episodes and DJ sessions — so switching songs shows up almost instantly instead of waiting on the slower Claude usage cycle. Claude usage polling is deliberately kept at 15s rather than faster, since every poll is itself a real API call that counts against your own 5h/7d rate-limit window. Automatically refreshes both the Claude and Spotify access tokens before they expire, using the refresh tokens from `~/.claude/.credentials.json` and `~/.spotify_credentials.json` respectively — no manual intervention needed. On boot, retries the initial token check until the network is available
- `spotify_auth_setup.py` — one-time interactive script (run manually, not as a service) that performs the Spotify OAuth authorization-code flow and saves tokens to `~/.spotify_credentials.json`, outside the repo
- `server.py` — serves the dashboard files over a local HTTP server on port 8080
- `dashboard.html` — the frontend that polls `usage.json` every 1 second and displays usage, Pi stats, weather, and (during the screensaver) the Spotify now-playing card — including the marquee scroll and per-song background color extraction, which is done entirely client-side via a canvas (no external API for this; Spotify's own CDN happens to allow cross-origin pixel reads). Weather uses IP geolocation (`ipapi.co`) to auto-detect the Pi's location and fetches conditions from Open-Meteo every 10 minutes
- `assets/claude-spotify.png` — local copy of the headphones mascot image, background-cleaned so it doesn't carry the stock sticker's white die-cut border

## Auto-update from GitHub

The Pi checks for updates from this repo every 5 minutes via cron and automatically restarts services if anything changed.

## Credits

Inspired by [Clawdmeter](https://github.com/HermannBjorgvin/Clawdmeter) by HermannBjorgvin.

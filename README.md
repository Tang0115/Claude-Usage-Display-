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
- **Weather widget** — auto-detects the Pi's location via IP geolocation and shows current temperature (°C) with daily low/high, weather icon, and condition using the Open-Meteo API (free, no key needed). Updates every 10 minutes
- **Pi system stats** — displays live CPU %, RAM %, and CPU temperature pulled from `usage.json` and updated every 15 seconds
- **Spotify now playing** — while the screensaver is active, shows album art on the left and track name / album name / artist on the right, with a live progress bar. Track and album names marquee-scroll if they're too long to fit on one line. The background dynamically recolors per song, sampled from the album art itself (darkened/desaturated for readability) with a soft vignette, and falls back to the plain black DVD-bounce screensaver when nothing's playing. Also works for podcast episodes and Spotify DJ sessions — for episodes, the layout adapts since podcasts have no artist: the middle album line is dropped and the show name takes its place in the artist slot instead (Spotify no longer returns a usable publisher field). Only shows up when playback is active on an allow-listed Spotify Connect device (e.g. your computers) — other devices (like a car's built-in Spotify) are treated as idle, so a long drive doesn't hammer the API or show up on the dashboard. Polled every 2 seconds while something's playing on an allowed device (backing off to every 20 seconds while idle, and further still if Spotify itself returns a rate-limit response) for near-instant track-change detection without hammering Spotify's API — decoupled from the slower Claude usage poll so it never affects your Claude rate-limit quota. Also swaps the mascot to a headphones image on the main (non-screensaver) view whenever something's playing. Optional — everything above still works without it
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
sudo apt install python3-websocket
mkdir -p ~/.config/autostart
cp clawd-dash.desktop ~/.config/autostart/
```
The dashboard is launched via `launch-dashboard.sh`, which starts Chromium
with its DevTools port open (`--remote-debugging-port=9222`, bound to
localhost only) and then runs `nudge_cursor.py`. That script waits for the
page to finish loading and injects a few synthetic mouse-moves over the
DevTools protocol.

This is needed because Chromium doesn't apply the page's `cursor: none` CSS
until it processes a real mouse-move event, so without this the pointer
stays visible on boot until you physically move the mouse once. Wayland
virtual-pointer tools (`wlrctl`, `ydotool`) move the compositor's cursor
sprite but don't reliably deliver the enter/motion sequence Chromium needs
to re-check its own cursor state — dispatching the event straight into
Blink via CDP (the same mechanism Puppeteer/Playwright use) does.

**6. Set up auto-update from GitHub**
```bash
chmod +x auto-update.sh
(crontab -l 2>/dev/null | grep -v auto-update.sh; echo "*/5 * * * * $HOME/clawd-dash/auto-update.sh >> $HOME/clawd-dash/auto-update.log 2>&1") | crontab -
```
Every 5 minutes, `auto-update.sh` fetches `origin/main` and hard-resets the
repo to it, restarting `clawd-daemon`/`clawd-server` if the commit changed —
but only when the working tree is clean; if you have uncommitted local edits
(e.g. mid-way through step 7.4 below), it skips the update rather than
discarding them. It runs `systemctl restart` via `sudo`, so the user running
cron needs passwordless sudo for that (the default `pi`-equivalent user on
Raspberry Pi OS already has this).

**7. (Optional) Set up the Spotify now-playing widget**

This is a one-time interactive step done outside of git, so your Spotify API keys are never written into this repo or pushed to GitHub.

1. Create an app at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and add `http://127.0.0.1:8888/callback` as a Redirect URI in the app's settings.
2. Run the setup script and follow the prompts (it opens a browser to authorize, then saves tokens to `~/.spotify_credentials.json` — outside the repo directory, never committed):
   ```bash
   python3 spotify_auth_setup.py
   ```
   If the Pi is headless (no browser), run this step on your laptop instead and `scp` the resulting `~/.spotify_credentials.json` over to the Pi's home directory. Note: `webbrowser.open()` will silently fall back to a text-mode browser over an SSH session with no `DISPLAY` set, which can't complete a real login — either run the script at the Pi's own physical desktop session, or open the printed authorization URL yourself in a real browser on the Pi's screen (the redirect target is `127.0.0.1:8888`, so it must be opened on the Pi itself, not a remote device).
3. Restart the daemon so it picks up the new credentials:
   ```bash
   sudo systemctl restart clawd-daemon
   ```
4. Edit `SPOTIFY_ALLOWED_DEVICES` at the top of `daemon.py` to list the Spotify Connect device name(s) — exactly as shown in the Spotify app's device picker, lowercase — that should trigger the now-playing widget (e.g. your computers). Playback on any other device (phone, car, speaker, etc.) is treated as idle: it won't show on the dashboard and won't be polled at the fast interval.

**8. Reboot**
```bash
sudo reboot
```

The dashboard will launch automatically on every boot.

## How it works

- `daemon.py` — runs two independent loops that both write to `usage.json`: the main loop polls the Anthropic API every 15 seconds using your OAuth token for usage data, and Pi stats (CPU %, RAM %, CPU temp via `psutil`); a background thread polls Spotify's playback-state endpoint (if set up) for track/album/artist/art/progress/device — including podcast episodes and DJ sessions — every 2 seconds while something's playing on an allow-listed device (`SPOTIFY_ALLOWED_DEVICES`), backing off to 20 seconds while idle or while playback is active on a non-allowed device (and further if Spotify rate-limits the requests) — so switching songs shows up almost instantly without hammering Spotify's API, and playback on other devices (like a car) doesn't burn through the API quota or show on the dashboard. Claude usage polling is deliberately kept at 15s rather than faster, since every poll is itself a real API call that counts against your own 5h/7d rate-limit window. Automatically refreshes both the Claude and Spotify access tokens before they expire, using the refresh tokens from `~/.claude/.credentials.json` and `~/.spotify_credentials.json` respectively — no manual intervention needed. On boot, retries the initial token check until the network is available
- `spotify_auth_setup.py` — one-time interactive script (run manually, not as a service) that performs the Spotify OAuth authorization-code flow and saves tokens to `~/.spotify_credentials.json`, outside the repo
- `server.py` — serves the dashboard files over a local HTTP server on port 8080
- `dashboard.html` — the frontend that polls `usage.json` every 1 second and displays usage, Pi stats, weather, and (during the screensaver) the Spotify now-playing card — including the marquee scroll and per-song background color extraction, which is done entirely client-side via a canvas (no external API for this; Spotify's own CDN happens to allow cross-origin pixel reads). Weather uses IP geolocation (`ipapi.co`) to auto-detect the Pi's location and fetches conditions from Open-Meteo every 10 minutes
- `assets/claude-spotify.png` — local copy of the headphones mascot image, background-cleaned so it doesn't carry the stock sticker's white die-cut border

## Auto-update from GitHub

The Pi checks for updates from this repo every 5 minutes via cron and automatically restarts services if anything changed.

## Credits

Inspired by [Clawdmeter](https://github.com/HermannBjorgvin/Clawdmeter) by HermannBjorgvin.

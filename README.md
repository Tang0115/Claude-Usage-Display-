# Claude Usage Display

A Raspberry Pi desk dashboard that shows your Claude Code usage in real time — session and weekly limits with live countdowns, local weather, and Pi system stats.


## What it does

- Shows your current 5h session usage %
- Shows your 7-day weekly usage %
- Countdown timers to each reset
- Color-coded warnings as you approach limits (yellow at 70%, red at 90%)
- Animated Claude logo with pulsing red heartbeat glow when usage hits 80%+ — logo also swaps to an alert image
- "Resetting soon" celebration mode when session reset is under 5 minutes — swaps to a celebration image then reverts automatically
- DVD-style screensaver after 2.5 minutes of no usage change — bounces wall-to-wall, alternates images on each wall hit, wakes automatically when usage updates
- **News screensaver mode** — if Claude usage stays stale for 30 minutes straight (and nothing's playing on Spotify), the DVD bounce hands off to a big-picture news card: full-bleed headline image with a dark gradient scrim, headline, and dek, cycling through the latest BBC World headlines every 20s. Headlines refresh from BBC's World RSS feed every 10 minutes — free, no API key or account needed. Spotify now-playing still takes priority over this the instant something starts playing, and any Claude usage change instantly drops back to the live dashboard, exactly like the plain DVD screensaver does
- **On This Day screensaver** — Wikipedia's selected "On this day" events for today's date, shown on the same big-picture card as the news (photo, year, event, summary) and cycling every 20s. Picked from HomeKit; free, no key needed
- **Live aquarium screensavers** — full-screen, muted 24/7 YouTube live streams, each its own HomeKit input: Tropical Reef (Aquarium of the Pacific), Shark Cam (Monterey Bay Aquarium), Aquarium 4K and Fish Tank. The player only exists while a stream is on screen (~17–24% CPU on a Pi 5 while playing)
- Live status indicator shows LIVE / SYNCING / ERROR based on connection state
- **Weather widget** — auto-detects the Pi's location via IP geolocation and shows current temperature (°C) with daily low/high, weather icon, and condition using the Open-Meteo API (free, no key needed). Updates every 10 minutes
- **Pi system stats** — displays live CPU %, RAM %, and CPU temperature pulled from `usage.json` and updated every 15 seconds
- **Spotify now playing** — while the screensaver is active, shows album art on the left and track name / album name / artist on the right, with a live progress bar. Track and album names marquee-scroll if they're too long to fit on one line. The background dynamically recolors per song, sampled from the album art itself (darkened/desaturated for readability) with a soft vignette, and falls back to the plain black DVD-bounce screensaver when nothing's playing. Also works for podcast episodes and Spotify DJ sessions — for episodes, the layout adapts since podcasts have no artist: the middle album line is dropped and the show name takes its place in the artist slot instead (Spotify no longer returns a usable publisher field). Only shows up when playback is active on an allow-listed Spotify Connect device (e.g. your computers) — other devices (like a car's built-in Spotify) are treated as idle, so a long drive doesn't hammer the API or show up on the dashboard. Polled every 1 second while something's playing on an allowed device (backing off to every 20 seconds while idle, and further still if Spotify itself returns a rate-limit response) for near-instant track-change detection without hammering Spotify's API — decoupled from the slower Claude usage poll so it never affects your Claude rate-limit quota. Also swaps the mascot to a headphones image on the main (non-screensaver) view whenever something's playing. Optional — everything above still works without it
- **Home-only wake** — usage changes only wake the dashboard from the screensaver if one of your own machines pinged the Pi's `/heartbeat` endpoint in the last 5 minutes, so a friend sharing the account (or you using Claude away from home) doesn't wake it. See "Home-only wake" below
- **HomeKit control** — a small Homebridge plugin shows the dashboard in the Home app as a TV: power turns the HDMI panel on/off, and the inputs pick which screensaver to use (Auto, Dashboard, DVD Bounce, News, Now Playing, On This Day, Jev Trading, and the aquarium streams). See "HomeKit control" below
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
python3 hide_cursor_setup.py
```
`launch-dashboard.sh` opens the dashboard in a Chromium kiosk window.
`hide_cursor_setup.py` hides the mouse cursor. On boot the pointer is drawn
by the Wayland compositor (labwc), not Chromium, and Chromium's own
`cursor: none` only takes over after a real mouse move. So the script
installs an invisible cursor theme (`~/.icons/clawd-hidden`) and sets
`XCURSOR_THEME=clawd-hidden` in `~/.config/labwc/environment`. The cursor is
then invisible from the moment the desktop starts, including over the rest
of the desktop. To undo it, delete that line and reboot.

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

## Home-only wake

The usage API is account-wide, so it can't say which device caused a change. Instead, add a Claude Code hook on each of your machines (`~/.claude/settings.json`) that pings the Pi's `server.py`; use `localhost` as `HOST` on the Pi itself:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "curl -s -m 2 http://HOST:8080/heartbeat >/dev/null 2>&1 || true"}]}],
    "Stop":             [{"hooks": [{"type": "command", "command": "curl -s -m 2 http://HOST:8080/heartbeat >/dev/null 2>&1 || true"}]}]
  }
}
```

`server.py` keeps the last heartbeat time in memory and serves its age at `/heartbeat_age`; `dashboard.html` ignores usage changes (no wake, idle timer keeps running) unless that age is under `HOME_ACTIVE_MS` (5 min). The endpoint is unauthenticated, so anyone on your LAN could wake the display. Away from home the ping fails silently.

## HomeKit control

`homebridge-clawd-dash/` is a Homebridge plugin that publishes the dashboard as a HomeKit **Television** (on the same Pi as `server.py`):

- **Power** — turns the `HDMI-A-1` output off/on with `wlr-randr`. Chromium and the services keep running, so it comes back instantly.
- **Inputs** — choose which screensaver the dashboard uses. Picking one shows it right away; after that the usual rules apply: Claude usage from a home machine wakes to the dashboard, Spotify now-playing takes over while something's playing, and after 2.5 idle minutes it returns to the screensaver you picked. `Auto` is the DVD bounce, handing off to news after 30 idle minutes. `Dashboard` never shows a screensaver. `News` and `On This Day` fall back to the DVD bounce until their items have loaded, and `Now Playing` shows the DVD bounce when nothing's playing. The stream inputs play their YouTube live stream full-screen and muted. `Jev Trading` shows the Jev trading bot's own status page (see below).

**Adding a live stream:** add one line to `STREAMS` in `server.py`: `'id': ('Name in Home app', 'YouTube video ID')`. No dashboard code is needed. Use a stream that's live 24/7 and allows embedding; a YouTube live video ID stays the same only as long as that broadcast keeps running.

**Adding any other screensaver:** add it to `MODES` in `server.py` (id → name shown in the Home app) and handle that id in `dashboard.html` (`applyControlMode` / `refreshScreensaverMode`). Once auto-update restarts `clawd-server`, the plugin sees the new list on its next poll (5s) and adds the input in HomeKit, with no Homebridge restart or plugin reinstall. Removals and renames sync the same way (renaming an input in the Home app still works). Each view keeps a permanent HomeKit input number, stored in `/var/lib/homebridge/clawd-dash-inputs.json`, so reordering or removing views never shifts the others.

The selected input is saved to `~/.clawd_control.json` so it survives the auto-update restarts. `server.py` exposes it at `/control` (`?mode=<id from MODES>`, `?power=on|off`), which you can also hit with `curl`.

Install (the `homebridge` user can't read your home directory, so copy the plugin in instead of symlinking it):
```bash
cd /var/lib/homebridge
sudo -u homebridge mkdir -p local-plugins
sudo rm -rf local-plugins/homebridge-clawd-dash
sudo cp -r ~/clawd-dash/homebridge-clawd-dash local-plugins/
sudo chown -R homebridge:homebridge local-plugins
sudo -u homebridge env PATH=/opt/homebridge/bin:$PATH npm install ./local-plugins/homebridge-clawd-dash
```
Add `{"platform": "ClawdDash", "name": "Clawd Dash"}` to `platforms` in `/var/lib/homebridge/config.json` and restart Homebridge. HomeKit only shows a TV's inputs when it isn't behind a bridge, so the plugin publishes it as a separate accessory. Add it in the Home app with **Add Accessory → More options** and your bridge's setup code. Only changes to the plugin's own code require running the copy and restart steps again (auto-update does not do this).

## How it works

- `daemon.py` — runs three independent loops that all write to `usage.json`. **This file lives on tmpfs (`/dev/shm/usage.json`), not the SD card** — a symlink at the repo path keeps `server.py`/`dashboard.html` unaware of this. It's rewritten every 15s (down to every 1s while Spotify's playing) and is fully ephemeral/derived, so writing it to RAM instead of flash avoids hammering the SD card on an always-on kiosk with no clean-shutdown routine — that write pattern was traced back as the likely cause of repeated SD corruption requiring reimages. Don't "fix" this back to a plain on-disk path. The main loop polls the Anthropic API every 15 seconds using your OAuth token for usage data, and Pi stats (CPU %, RAM %, CPU temp via `psutil`); a background thread polls Spotify's playback-state endpoint (if set up) for track/album/artist/art/progress/device — including podcast episodes and DJ sessions — every 1 second while something's playing on an allow-listed device (`SPOTIFY_ALLOWED_DEVICES`), backing off to 20 seconds while idle or while playback is active on a non-allowed device (and further if Spotify rate-limits the requests) — so switching songs shows up almost instantly without hammering Spotify's API, and playback on other devices (like a car) doesn't burn through the API quota or show on the dashboard. A third background thread fetches BBC's World News RSS feed (`feeds.bbci.co.uk/news/world/rss.xml`) every 10 minutes and parses out the top 8 headlines/descriptions/images for the news screensaver mode — no API key or account, since BBC's RSS is free and public; thumbnail image URLs are bumped from BBC's default 240px to 1024px for a full-size "big picture" look. This has to happen server-side rather than client-side (unlike the weather widget below) because the BBC feed doesn't set CORS headers, so a browser `fetch()` straight from `dashboard.html` would be blocked. Claude usage polling is deliberately kept at 15s rather than faster, since every poll is itself a real API call that counts against your own 5h/7d rate-limit window. Automatically refreshes both the Claude and Spotify access tokens before they expire, using the refresh tokens from `~/.claude/.credentials.json` and `~/.spotify_credentials.json` respectively — no manual intervention needed. On boot, retries the initial token check until the network is available
- `spotify_auth_setup.py` — one-time interactive script (run manually, not as a service) that performs the Spotify OAuth authorization-code flow and saves tokens to `~/.spotify_credentials.json`, outside the repo
- `server.py` — serves the dashboard files over a threaded local HTTP server on port 8080, and also handles `/heartbeat` (records the time of the last ping from one of your machines' Claude Code hooks) and `/heartbeat_age` (returns seconds since that ping as JSON, or `null` if none since the server started). The heartbeat is in memory only. `/control` gets or sets the HomeKit power state (read live from `wlr-randr`, cached for 10s) and the view mode, and returns the `MODES` list the plugin builds its inputs from
- `dashboard.html` — the frontend that polls `usage.json`, `/heartbeat_age` and `/control` every 1 second and displays usage, Pi stats, weather, and (during the screensaver) the Spotify now-playing card — including the marquee scroll and per-song background color extraction, which is done entirely client-side via a canvas (no external API for this; Spotify's own CDN happens to allow cross-origin pixel reads). A usage change only resets the idle timer and wakes the screensaver if the heartbeat age is under `HOME_ACTIVE_MS` (5 min); otherwise the numbers still update but the screensaver stays. On This Day events come from Wikipedia's REST API (`/feed/onthisday/selected/MM/DD`), fetched client-side since it allows CORS, refetched when the date changes, with images at a standard 1280px Wikimedia thumbnail size. Weather uses IP geolocation (`ipapi.co`) to auto-detect the Pi's location and fetches conditions from Open-Meteo every 10 minutes
- `homebridge-clawd-dash/` — Homebridge plugin that publishes the dashboard as a HomeKit TV and translates power/input changes into `/control` calls, polling it every 5s to keep HomeKit's state and input list in sync (see "HomeKit control")
- **Jev Trading view** — the `jev` input embeds the Jev trading bot's status page, served by the separate jevlab project at `http://localhost:8081/`, as a full-screen iframe. The iframe only exists while the view is on screen. While it's up, the dashboard polls `:8081/health` every 10s. If that service is down or reports `ok: false`, it shows a "Jev dashboard offline" card instead, and switches back to the page once health returns. A `stale` report still shows the page, which has its own warning
- `assets/claude-spotify.png` — local copy of the headphones mascot image, background-cleaned so it doesn't carry the stock sticker's white die-cut border

## Auto-update from GitHub

The Pi checks for updates from this repo every 5 minutes via cron and automatically restarts services if anything changed.

## Credits

Inspired by [Clawdmeter](https://github.com/HermannBjorgvin/Clawdmeter) by HermannBjorgvin.

#!/bin/bash
# Launches the kiosk browser, then injects a synthetic mouse-move via
# Chromium's DevTools protocol so it re-evaluates its cursor hit-test and
# actually applies the page's `cursor: none` rule. Without this, the
# pointer stays visible on boot until the mouse is physically moved once.
#
# Wayland virtual-pointer tools (wlrctl/ydotool) move the compositor's
# cursor sprite but don't reliably deliver the enter/motion sequence
# Chromium needs to re-check its own cursor state, so this uses CDP
# instead -- the same mechanism Puppeteer/Playwright use to inject
# "real" input straight into Blink.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

/usr/bin/chromium --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --start-maximized --disable-session-crashed-bubble \
  --disable-features=TranslateUI --overscroll-history-navigation=0 \
  --remote-debugging-port=9222 --remote-allow-origins=* \
  --app=http://localhost:8080/dashboard.html &

python3 "$SCRIPT_DIR/nudge_cursor.py"

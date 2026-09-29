#!/bin/bash
# Launches the dashboard in a Chromium kiosk window.
#
# The mouse cursor is hidden by the invisible cursor theme that
# hide_cursor_setup.py installs for the compositor (labwc), not from here:
# on boot the pointer belongs to the compositor until a real mouse move, so
# nothing Chromium does (including the page's `cursor: none`) can hide it.

/usr/bin/chromium --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --start-maximized --disable-session-crashed-bubble \
  --disable-features=TranslateUI --overscroll-history-navigation=0 \
  --app=http://localhost:8080/dashboard.html

#!/bin/bash
# Pulls the latest clawd-dash from GitHub and restarts services if anything changed.
# Run via cron every 5 minutes (see README "Auto-update from GitHub").
set -e
cd /home/tang0115/clawd-dash

BEFORE=$(git rev-parse HEAD)
git fetch origin main --quiet
git reset --hard origin/main --quiet
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" != "$AFTER" ]; then
    echo "$(date): updated $BEFORE -> $AFTER, restarting services"
    sudo /usr/bin/systemctl restart clawd-daemon clawd-server
fi

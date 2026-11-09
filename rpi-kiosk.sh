#!/usr/bin/env bash
# Kraken on Raspberry Pi — full-screen kiosk of the web app in Chromium.
# (The native touchscreen launcher is the Python app one level up; this is the
#  web front-end in kiosk mode.)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
chromium-browser --kiosk --incognito --noerrdialogs --disable-infobars \
  --check-for-update-interval=31536000 \
  "file://$DIR/strikeback_x.html" 2>/dev/null || \
chromium --kiosk --incognito "file://$DIR/strikeback_x.html"

#!/usr/bin/env bash
# Regenerate the logo raster pack from logo.svg.
# Needs: rsvg-convert (librsvg2-bin) and ImageMagick (convert).
#   sudo apt install -y librsvg2-bin imagemagick
set -euo pipefail
cd "$(dirname "$0")"

for s in 16 32 48 64 128 256 512 1024; do
  rsvg-convert -w "$s" -h "$s" logo.svg -o "logo-$s.png"
done
cp logo-512.png icon-512.png
cp logo-256.png icon-256.png
rsvg-convert -w 1040 -h 600 logo_lockup.svg -o logo_lockup.png
convert logo-16.png logo-32.png logo-48.png logo-64.png logo-256.png favicon.ico
echo "[✓] Wrote logo-*.png, icon-*.png, logo_lockup.png, favicon.ico"

#!/usr/bin/env bash
# RaspyJack-X installer — Raspberry Pi OS (Bookworm) / Kali ARM.
# Idempotent: safe to re-run. Does NOT install offensive tooling for you;
# it sets up the launcher + its Python deps. Add your own pentest packages.
set -euo pipefail

APP_USER="${SUDO_USER:-$USER}"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$APP_HOME/raspyjackx"

echo "[*] Installing RaspyJack-X for user: $APP_USER"
echo "[*] Source : $SRC_DIR"
echo "[*] Dest   : $DEST"

# --- system packages -------------------------------------------------------
echo "[*] Installing system dependencies (apt)..."
sudo apt-get update
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  python3-pyside6.qtwidgets python3-pyside6.qtcore python3-pyside6.qtgui \
  python3-yaml python3-psutil python3-pyside6.qtsvg \
  fonts-dejavu fonts-noto-core fonts-symbola libatlas-base-dev \
  || echo "[!] Some apt packages unavailable; pip venv will cover them."

# --- copy app --------------------------------------------------------------
echo "[*] Copying application..."
mkdir -p "$DEST"
cp -r "$SRC_DIR/raspyjackx" "$DEST/"
cp "$SRC_DIR/requirements.txt" "$DEST/"
mkdir -p "$APP_HOME/loot"
chown -R "$APP_USER:$APP_USER" "$DEST" "$APP_HOME/loot"

# --- python venv (fallback if distro PySide6 missing) ----------------------
if ! python3 -c "import PySide6" 2>/dev/null; then
  echo "[*] PySide6 not found system-wide; creating venv..."
  python3 -m venv "$DEST/.venv" --system-site-packages
  "$DEST/.venv/bin/pip" install --upgrade pip
  "$DEST/.venv/bin/pip" install -r "$DEST/requirements.txt"
  PYBIN="$DEST/.venv/bin/python3"
else
  PYBIN="$(command -v python3)"
fi
echo "[*] Python interpreter: $PYBIN"

# --- systemd kiosk service -------------------------------------------------
echo "[*] Installing systemd service..."
SERVICE=/etc/systemd/system/raspyjackx.service
sudo tee "$SERVICE" >/dev/null <<EOF
[Unit]
Description=RaspyJack-X touchscreen launcher
After=multi-user.target

[Service]
User=$APP_USER
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/$(id -u "$APP_USER")
Environment=RJX_CONFIG=$DEST/raspyjackx/tools.yaml
WorkingDirectory=$DEST
ExecStart=$PYBIN -m raspyjackx.main
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
echo
echo "[✓] Installed."
echo "    Start now : sudo systemctl start raspyjackx"
echo "    On boot   : sudo systemctl enable raspyjackx"
echo "    Edit menu : nano $DEST/raspyjackx/tools.yaml"
echo "    Dev run   : cd $DEST && $PYBIN -m raspyjackx.main --windowed"

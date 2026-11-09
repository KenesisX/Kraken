#!/usr/bin/env bash
# Alfa AWUS036AC setup for RaspyJack-X (Raspberry Pi 5, Bookworm / Kali ARM).
#
# The AWUS036AC uses the Realtek RTL8812AU chipset (dual-band 802.11ac).
# The in-kernel driver does NOT do monitor mode / injection — you need the
# community 8812au DKMS driver (morrownr fork, maintained). This installs it,
# then gives you a one-shot monitor-mode helper.
set -euo pipefail

echo "[*] AWUS036AC (RTL8812AU) driver + monitor-mode setup"

if [[ $EUID -ne 0 ]]; then echo "[!] Run with sudo."; exit 1; fi

apt-get update
apt-get install -y git dkms build-essential bc \
  "raspberrypi-kernel-headers" "linux-headers-$(uname -r)" 2>/dev/null \
  || apt-get install -y git dkms build-essential bc linux-headers-generic

SRC=/usr/src/8812au
if [[ ! -d "$SRC" ]]; then
  echo "[*] Cloning 8812au driver (morrownr)..."
  git clone https://github.com/morrownr/8812au-20210629 "$SRC"
fi
cd "$SRC"
echo "[*] Building + installing via DKMS (this takes a few minutes on a Pi)..."
./install-driver.sh NoPrompt || {
  echo "[!] DKMS build failed. Check that kernel headers match 'uname -r'."
  exit 1
}

# monitor-mode helper
HELP=/usr/local/bin/rjx-mon
cat > "$HELP" <<'EOF'
#!/usr/bin/env bash
# rjx-mon <iface> on|off  — toggle monitor mode on the AWUS036AC
set -euo pipefail
IFACE="${1:-wlan1}"; MODE="${2:-on}"
if [[ "$MODE" == "on" ]]; then
  ip link set "$IFACE" down
  iw dev "$IFACE" set type monitor
  ip link set "$IFACE" up
  echo "[+] $IFACE -> monitor"
else
  ip link set "$IFACE" down
  iw dev "$IFACE" set type managed
  ip link set "$IFACE" up
  echo "[+] $IFACE -> managed"
fi
iw dev "$IFACE" info | sed -n '2,6p'
EOF
chmod +x "$HELP"

echo
echo "[✓] Done. Plug in the AWUS036AC and check:  iw dev"
echo "    Monitor on :  sudo rjx-mon wlan1 on"
echo "    Monitor off:  sudo rjx-mon wlan1 off"
echo "    Tip: set 'wlan: wlan1' and 'mon: wlan1' in your profile yaml."

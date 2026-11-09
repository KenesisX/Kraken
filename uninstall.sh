#!/usr/bin/env bash
# ============================================================================
#  uninstall.sh — remove Kraken / RaspyJack-X and everything it installed or
#  generated. The "panic wipe" button in the app clears the app's on-device
#  data (localStorage); this script removes the native program, its services,
#  and generated loot on a Pi / Linux install.
#
#  Scoped on purpose: it only touches Kraken's own install dirs, services, and
#  generated data — never your home folder, never system packages you had
#  before. Tools installed by install_tools.sh (nmap, gqrx, …) are LEFT in
#  place unless you pass --tools.
#
#    sudo ./uninstall.sh            # remove app + services + loot/records
#    sudo ./uninstall.sh --tools    # also apt-remove the toolset it installed
#    sudo ./uninstall.sh --yes      # no prompt
# ============================================================================
set -uo pipefail
[[ $EUID -eq 0 ]] || { echo "[!] Run as root (sudo)."; exit 1; }
APP_USER="${SUDO_USER:-$USER}"; APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
YES=0; TOOLS=0
for a in "$@"; do [[ "$a" == "--yes" ]]&&YES=1; [[ "$a" == "--tools" ]]&&TOOLS=1; done

echo "This removes Kraken for user '$APP_USER':"
echo "  • services : raspyjackx.service, kraken-web.service, kraken-firstboot.service"
echo "  • program  : $APP_HOME/raspyjackx, /opt/kraken"
echo "  • data     : $APP_HOME/loot, $APP_HOME/.config/kraken, generated records/stats"
[[ $TOOLS -eq 1 ]] && echo "  • toolset  : apt packages from install_tools.sh (--tools)"
if [[ $YES -ne 1 ]]; then read -rp "Proceed? [y/N] " a; [[ "$a" =~ ^[Yy]$ ]] || { echo "aborted."; exit 0; }; fi

# stop + remove services
for s in raspyjackx kraken-web kraken-firstboot; do
  systemctl stop "$s.service" 2>/dev/null
  systemctl disable "$s.service" 2>/dev/null
  rm -f "/etc/systemd/system/$s.service"
done
systemctl daemon-reload 2>/dev/null

# remove program + generated data (app-scoped paths only)
rm -rf "$APP_HOME/raspyjackx" "/opt/kraken" "$APP_HOME/loot" "$APP_HOME/.config/kraken" \
       "$APP_HOME/.local/share/kraken" /boot/kraken.done /boot/firmware/kraken.done \
       /boot/kraken-firstboot.sh /boot/firmware/kraken-firstboot.sh 2>/dev/null

# optional: remove the toolset this project installed
if [[ $TOOLS -eq 1 ]]; then
  echo "[*] Removing toolset packages (this can take a while)..."
  apt-get remove -y gqrx-sdr rtl-433 multimon-ng inspectrum soapysdr-tools \
    minicom dfu-util avrdude esptool 2>/dev/null || true
  apt-get autoremove -y 2>/dev/null || true
fi

echo "[✓] Kraken removed. (Browser/app local data is cleared by the in-app Panic Wipe button.)"

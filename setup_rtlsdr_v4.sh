#!/usr/bin/env bash
# RTL-SDR Blog V4 setup for RaspyJack-X (Raspberry Pi 5).
#
# The V4 uses an R828D tuner and needs the rtl-sdr-blog driver fork, NOT the
# old osmocom package in apt. Using the wrong driver gives you no signal above
# ~250 MHz and broken HF. This removes the conflicting package, builds the
# correct fork, and blacklists the kernel DVB driver that steals the device.
set -euo pipefail

echo "[*] RTL-SDR Blog V4 driver setup"
if [[ $EUID -ne 0 ]]; then echo "[!] Run with sudo."; exit 1; fi

echo "[*] Removing conflicting osmocom rtl-sdr if present..."
apt-get -y purge ^librtlsdr || true
apt-get -y autoremove || true

apt-get update
apt-get install -y libusb-1.0-0-dev git cmake pkg-config build-essential

SRC=/opt/rtl-sdr-blog
if [[ ! -d "$SRC" ]]; then
  git clone https://github.com/rtlsdrblog/rtl-sdr-blog "$SRC"
fi
cd "$SRC"
mkdir -p build && cd build
cmake ../ -DINSTALL_UDEV_RULES=ON -DDETACH_KERNEL_DRIVER=ON
make -j"$(nproc)"
make install
ldconfig

echo "[*] Installing udev rules + blacklisting kernel DVB driver..."
cp ../rtl-sdr.rules /etc/udev/rules.d/ 2>/dev/null || true
cat > /etc/modprobe.d/blacklist-rtlsdr.conf <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
udevadm control --reload-rules || true

echo
echo "[✓] Done. REBOOT, then verify:"
echo "    rtl_test -t          # should ID an R828D tuner, V4"
echo "    rtl_eeprom           # confirms 'RTL-SDR Blog V4'"
echo "    Bias-tee (LNA):  rtl_biast -b 1   (off: -b 0)"
echo "    SoapySDRUtil --find  # for the Omni-RF / ICU pipeline"

#!/usr/bin/env bash
# ============================================================================
#  build_img.sh  —  Bake a flashable Raspberry Pi 5 image with Kraken / RaspyJack-X
#                   pre-installed, from ANY arm64 base image:
#                   Raspberry Pi OS (Bookworm) · Kali ARM · Parrot ARM · Athena (Pi)
#
#  This does NOT download an OS for you. You bring a base .img (uncompressed),
#  and this script clones it, grows the rootfs, chroots in via qemu, installs
#  the launcher + toolset, enables autostart + landscape rotation, and writes
#  out a new flashable image. Flash the result with Raspberry Pi Imager,
#  balenaEtcher, or dd.
#
#  WHY a script and not a prebuilt .img here: a finished Pi image is 4-12 GB of
#  binary that must be assembled on a Linux host with loop devices + qemu
#  (root + privileged mounts). That can't be produced inside a chat sandbox,
#  so this is the exact, runnable pipeline you execute once on your own machine
#  (an x86 Linux box with binfmt/qemu, OR a Raspberry Pi itself — on a Pi you
#  don't even need qemu, it's native).
#
#  USAGE
#    sudo ./build_img.sh --base 2025-xx-raspios-bookworm-arm64.img
#    sudo ./build_img.sh --base kali-linux-2025-raspberry-pi5-arm64.img --distro kali
#    sudo ./build_img.sh --base Parrot-arm64.img --distro parrot --out kraken-parrot-pi5.img --grow 4G
#    sudo ./build_img.sh --base athena-pi.img --distro athena --no-tools   # launcher only
#
#  FLAGS
#    --base PATH    (required) uncompressed arm64 base .img to clone
#    --out PATH     output image (default: kraken-<distro>-pi5.img)
#    --distro NAME  auto|raspbian|kali|parrot|athena  (default: auto-detect)
#    --grow SIZE    extra rootfs space to add, e.g. 3G (default: 3G). 0 = don't grow
#    --no-tools     install the launcher only; skip install_tools.sh (big download)
#    --user NAME    target login user inside the image (default: auto-detect / pi|kali)
#
#  REQUIREMENTS (host)
#    root, Linux, and: qemu-user-static binfmt-support parted kpartx
#                      e2fsprogs rsync coreutils util-linux
#    On Debian/Ubuntu/Kali host:
#      sudo apt-get install -y qemu-user-static binfmt-support parted kpartx \
#                              e2fsprogs rsync util-linux
# ============================================================================
set -euo pipefail

# ---- args ------------------------------------------------------------------
BASE=""; OUT=""; DISTRO="auto"; GROW="3G"; TOOLS=1; TGT_USER=""
while [[ $# -gt 0 ]]; do case "$1" in
  --base)   BASE="$2"; shift 2;;
  --out)    OUT="$2"; shift 2;;
  --distro) DISTRO="$2"; shift 2;;
  --grow)   GROW="$2"; shift 2;;
  --no-tools) TOOLS=0; shift;;
  --user)   TGT_USER="$2"; shift 2;;
  -h|--help) sed -n '2,46p' "$0"; exit 0;;
  *) echo "[!] Unknown arg: $1"; exit 1;;
esac; done

[[ $EUID -eq 0 ]] || { echo "[!] Run as root (sudo)."; exit 1; }
[[ -n "$BASE" && -f "$BASE" ]] || { echo "[!] --base <image.img> is required and must exist."; exit 1; }
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- host tool check -------------------------------------------------------
need=(losetup parted rsync resize2fs e2fsck)
for t in "${need[@]}"; do command -v "$t" >/dev/null || { echo "[!] Missing host tool: $t  (see REQUIREMENTS)"; exit 1; }; done
QEMU="$(command -v qemu-aarch64-static || true)"
if [[ "$(uname -m)" != aarch64 && "$(uname -m)" != arm64 ]]; then
  [[ -n "$QEMU" ]] || { echo "[!] Cross-building on $(uname -m) needs qemu-aarch64-static. Install qemu-user-static."; exit 1; }
fi

[[ -n "$OUT" ]] || OUT="kraken-${DISTRO}-pi5.img"
echo "[*] Base   : $BASE"
echo "[*] Output : $OUT"
echo "[*] Distro : $DISTRO   Grow:+$GROW   Tools:$([[ $TOOLS -eq 1 ]] && echo yes || echo no)"

# ---- 1. clone base ---------------------------------------------------------
echo "[*] Cloning base image -> $OUT (this copies several GB)..."
cp --reflink=auto "$BASE" "$OUT"

# ---- 2. grow the image file + rootfs --------------------------------------
if [[ "$GROW" != "0" ]]; then
  echo "[*] Growing image by $GROW..."
  truncate -s +"$GROW" "$OUT"
fi

# ---- 3. attach loop (whole disk, -P reads partition table) ----------------
LOOP="$(losetup --show -Pf "$OUT")"
echo "[*] Loop device: $LOOP"
cleanup(){
  set +e
  echo "[*] Cleanup..."
  for m in "$MNT/boot/firmware" "$MNT/boot" "$MNT/dev/pts" "$MNT/dev" "$MNT/proc" "$MNT/sys" "$MNT/run" "$MNT"; do
    mountpoint -q "$m" && umount -lf "$m"
  done
  [[ -n "${LOOP:-}" ]] && losetup -d "$LOOP" 2>/dev/null
  [[ -n "${MNT:-}" && -d "$MNT" ]] && rmdir "$MNT" 2>/dev/null
}
trap cleanup EXIT

# Identify partitions: p1 = FAT boot, p2 = ext4 root (standard Pi layout)
BOOTP="${LOOP}p1"; ROOTP="${LOOP}p2"
[[ -b "$BOOTP" && -b "$ROOTP" ]] || { echo "[!] Expected ${LOOP}p1/p2. Non-standard layout — inspect with: parted $LOOP print"; exit 1; }

# Expand root partition to fill the grown image, then the filesystem
if [[ "$GROW" != "0" ]]; then
  echo "[*] Expanding root partition + ext4..."
  parted -s "$LOOP" resizepart 2 100% || echo "[!] resizepart warning (continuing)"
  losetup -c "$LOOP"
  e2fsck -pf "$ROOTP" || true
  resize2fs "$ROOTP" || echo "[!] resize2fs warning (continuing)"
fi

# ---- 4. mount ----------------------------------------------------------------
MNT="$(mktemp -d /tmp/kraken-img.XXXXXX)"
mount "$ROOTP" "$MNT"
# Pi OS Bookworm uses /boot/firmware; older/others use /boot
if [[ -d "$MNT/boot/firmware" ]]; then BOOTDIR="$MNT/boot/firmware"; else BOOTDIR="$MNT/boot"; fi
mkdir -p "$BOOTDIR"; mount "$BOOTP" "$BOOTDIR"

# ---- 5. auto-detect distro + user ------------------------------------------
if [[ "$DISTRO" == "auto" ]]; then
  if   grep -qi kali   "$MNT/etc/os-release" 2>/dev/null; then DISTRO=kali
  elif grep -qi parrot "$MNT/etc/os-release" 2>/dev/null; then DISTRO=parrot
  elif grep -qi athena "$MNT/etc/os-release" 2>/dev/null; then DISTRO=athena
  else DISTRO=raspbian; fi
  echo "[*] Auto-detected distro: $DISTRO"
fi
if [[ -z "$TGT_USER" ]]; then
  for u in pi kali parrot athena user; do
    [[ -d "$MNT/home/$u" ]] && { TGT_USER="$u"; break; }
  done
  TGT_USER="${TGT_USER:-pi}"
fi
echo "[*] Target user: $TGT_USER"

# ---- 6. stage the app + qemu into the image --------------------------------
echo "[*] Staging application into image..."
install -d "$MNT/opt/kraken"
rsync -a --exclude '.venv' --exclude '__pycache__' --exclude '*.img' \
  "$SRC_DIR"/ "$MNT/opt/kraken/"
# qemu for cross-arch chroot (not needed when building on a Pi)
if [[ -n "$QEMU" && "$(uname -m)" != aarch64 ]]; then
  cp "$QEMU" "$MNT/usr/bin/" 2>/dev/null || true
fi

# bind kernel filesystems for chroot
for fs in dev dev/pts proc sys run; do
  mkdir -p "$MNT/$fs"; mount --bind "/$fs" "$MNT/$fs" 2>/dev/null || true
done
cp /etc/resolv.conf "$MNT/etc/resolv.conf" 2>/dev/null || true

# ---- 7. in-image provisioning script ---------------------------------------
KALIFLAG=""; [[ "$DISTRO" == "kali" ]] && KALIFLAG="--kali"
cat > "$MNT/opt/kraken/_provision.sh" <<PROV
#!/usr/bin/env bash
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "[img] Provisioning Kraken for '$DISTRO' (user $TGT_USER)..."
cd /opt/kraken

# launcher + python deps (install.sh is already distro-flexible + idempotent)
if [ -f install.sh ]; then SUDO_USER=$TGT_USER bash install.sh || echo "[img] install.sh had warnings"; fi

# full toolset (optional; big)
if [ "$TOOLS" = "1" ] && [ -f install_tools.sh ]; then
  bash install_tools.sh $KALIFLAG || echo "[img] install_tools.sh had warnings (some pkgs not in this distro's repo)"
fi

# SDR / Wi-Fi adapter helpers
[ -f hw_setup/setup_rtlsdr_v4.sh ]   && bash hw_setup/setup_rtlsdr_v4.sh   || true
[ -f hw_setup/setup_awus036ac.sh ]   && bash hw_setup/setup_awus036ac.sh   || true

# enable the launcher on boot
systemctl enable raspyjackx.service 2>/dev/null || true

# web build available offline at http://localhost — serve the webapp via a tiny unit
cat > /etc/systemd/system/kraken-web.service <<WEB
[Unit]
Description=Kraken web console (offline)
After=network.target
[Service]
WorkingDirectory=/opt/kraken/webapp
ExecStart=/usr/bin/python3 -m http.server 8088
Restart=on-failure
User=$TGT_USER
[Install]
WantedBy=multi-user.target
WEB
systemctl enable kraken-web.service 2>/dev/null || true

echo "[img] Provisioning done."
PROV
chmod +x "$MNT/opt/kraken/_provision.sh"

echo "[*] Entering chroot to provision (this is the long part)..."
chroot "$MNT" /bin/bash -lc "TOOLS=$TOOLS /opt/kraken/_provision.sh" || echo "[!] chroot provisioning returned non-zero (warnings are normal)"
rm -f "$MNT/opt/kraken/_provision.sh"

# ---- 8. landscape rotation + kiosk niceties on the boot partition ----------
echo "[*] Configuring landscape display + first-boot..."
CFG="$BOOTDIR/config.txt"
if [[ -f "$CFG" ]] && ! grep -q "KRAKEN-LANDSCAPE" "$CFG"; then
cat >> "$CFG" <<'TXT'

# --- KRAKEN-LANDSCAPE (Pi 5 / DSI/HDMI touchscreen in landscape) ---
# Official 7" DSI touch panel: uncomment to rotate to landscape.
#display_lcd_rotate=1
# HDMI panels: rotation is handled by the desktop/compositor (see firstrun).
disable_overscan=1
TXT
fi

# first-boot oneshot: rotate X/Wayland to landscape + calibrate touch
cat > "$BOOTDIR/kraken-firstboot.sh" <<'FB'
#!/usr/bin/env bash
# Runs once on first boot (invoked from rc.local / systemd) to lock landscape.
[ -f /boot/kraken.done ] && exit 0; [ -f /boot/firmware/kraken.done ] && exit 0
# Labwc / Wayland (Pi OS Bookworm default)
if command -v wlr-randr >/dev/null 2>&1; then
  OUT=$(wlr-randr | awk 'NR==1{print $1}'); [ -n "$OUT" ] && wlr-randr --output "$OUT" --transform 90 || true
fi
# X11 fallback
if command -v xrandr >/dev/null 2>&1; then
  xrandr -o right 2>/dev/null || true
fi
touch /boot/kraken.done 2>/dev/null || touch /boot/firmware/kraken.done 2>/dev/null
FB
chmod +x "$BOOTDIR/kraken-firstboot.sh"

# wire first-boot into the image (systemd oneshot)
cat > "$MNT/etc/systemd/system/kraken-firstboot.service" <<'FBS'
[Unit]
Description=Kraken first-boot landscape setup
After=graphical.target
ConditionPathExists=!/boot/kraken.done
[Service]
Type=oneshot
ExecStart=/bin/bash -c '[ -f /boot/firmware/kraken-firstboot.sh ] && bash /boot/firmware/kraken-firstboot.sh || bash /boot/kraken-firstboot.sh'
[Install]
WantedBy=graphical.target
FBS
chroot "$MNT" systemctl enable kraken-firstboot.service 2>/dev/null || true

# ---- 9. finish -------------------------------------------------------------
sync
echo "[*] Image assembled. Unmounting + detaching..."
# cleanup trap handles umount/losetup
trap - EXIT
cleanup
echo
echo "[✓] DONE -> $OUT"
echo
echo "  Flash it:"
echo "    • Raspberry Pi Imager  -> 'Use custom' -> $OUT"
echo "    • balenaEtcher         -> select $OUT"
echo "    • dd (careful!):  sudo dd if=$OUT of=/dev/sdX bs=4M conv=fsync status=progress"
echo
echo "  First boot auto-starts the Kraken launcher (landscape) and serves the"
echo "  web console at http://<pi-ip>:8088 . Shrink before distributing with:"
echo "    pishrink.sh $OUT   (optional, trims free space for a smaller download)"

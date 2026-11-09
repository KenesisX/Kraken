# Kraken / RaspyJack-X — Raspberry Pi 5 flashable image

You asked for a `.img` that boots straight into the launcher and runs on
**Raspberry Pi OS, Kali, Parrot, or Athena**. Here is how to get one. There are
three paths — pick by how much you want to do yourself.

> **Why no prebuilt `.img` is attached:** a finished Pi image is 4–12 GB of
> binary that has to be baked on a Linux host with loop devices + `qemu` (root +
> privileged mounts) or on a Pi itself. That can't be produced inside a chat.
> `build_img.sh` **is** the complete, runnable recipe — you run it once and it
> spits out the flashable image.

---

## Path A — Bake a self-contained image (recommended)

One command turns any arm64 base image into a Kraken image with the launcher,
toolset, SDR/Wi-Fi setup, landscape rotation, and autostart already inside.

```bash
# 1. Grab a base image (uncompressed .img) for the distro you want:
#    Pi OS : https://www.raspberrypi.com/software/operating-systems/   (64-bit)
#    Kali  : https://www.kali.org/get-kali/#kali-arm   (Raspberry Pi 5, arm64)
#    Parrot: https://parrotsec.org/download/   (arm64)
#    Athena: use its Pi/arm64 image
#    (if it's .img.xz, run:  xz -d image.img.xz)

# 2. Host prep (Debian/Ubuntu/Kali x86 box, or a Pi — a Pi needs no qemu):
sudo apt-get install -y qemu-user-static binfmt-support parted kpartx \
                        e2fsprogs rsync util-linux

# 3. Bake:
sudo ./build_img.sh --base 2025-xx-raspios-bookworm-arm64.img
#   Kali / Parrot / Athena:
sudo ./build_img.sh --base kali-...-arm64.img   --distro kali
sudo ./build_img.sh --base Parrot-...-arm64.img --distro parrot
sudo ./build_img.sh --base athena-pi.img        --distro athena

# Launcher only (skip the big toolset download):
sudo ./build_img.sh --base <img> --no-tools

# 4. (optional) shrink for a smaller download before sharing:
sudo pishrink.sh kraken-raspbian-pi5.img
```

Output: `kraken-<distro>-pi5.img` — a standard flashable image.

### Flash it
- **Raspberry Pi Imager** → *Use custom* → pick the `.img`
- **balenaEtcher** → select the `.img`
- **dd** (double-check the device!):
  `sudo dd if=kraken-raspbian-pi5.img of=/dev/sdX bs=4M conv=fsync status=progress`

### First boot
- Auto-starts the **Kraken launcher** in **landscape**.
- Serves the **web console offline** at `http://<pi-ip>:8088`.
- `kraken-firstboot.service` locks landscape (Wayland `wlr-randr` / X11 `xrandr`)
  once, then gets out of the way.

---

## Path B — Flash a stock distro, then run two scripts

If you'd rather not bake an image, flash a normal Pi OS / Kali / Parrot / Athena
card, boot it, copy this folder over, and run:

```bash
sudo ./install.sh            # launcher + Python deps (idempotent, distro-flexible)
sudo ./install_tools.sh      # full toolset   (add --kali on Kali)
sudo systemctl enable --now raspyjackx
```

Same result, you just do the install on the running Pi instead of in a chroot.

---

## Path C — pi-gen (from-scratch Pi OS image, for repeatable CI builds)

For a reproducible Pi OS image built from Raspberry Pi's official `pi-gen`:

```bash
git clone https://github.com/RPi-Distro/pi-gen && cd pi-gen
mkdir -p stage-kraken/00-kraken/files
cp -r /path/to/raspyjackx stage-kraken/00-kraken/files/kraken
cat > stage-kraken/00-kraken/00-run-chroot.sh <<'EOF'
#!/bin/bash -e
cp -r /tmp/kraken /opt/kraken
cd /opt/kraken && SUDO_USER=pi bash install.sh && bash install_tools.sh
systemctl enable raspyjackx.service
EOF
chmod +x stage-kraken/00-kraken/00-run-chroot.sh
echo 'IMG_NAME=kraken' > config && echo 'TARGET_HOSTNAME=kraken' >> config
sudo ./build.sh            # produces deploy/kraken-*.img
```

---

## Distro notes
| Distro  | Notes |
|---------|-------|
| Pi OS 64 (Bookworm) | Reference target. Everything installs from Pi repos + pip venv fallback. |
| Kali ARM | Many tools preloaded. Use `--distro kali` / `install_tools.sh --kali` to skip what's already there. |
| Parrot ARM | Debian-based; same apt packages resolve. A few names differ — the per-package loop reports misses. |
| Athena (Pi) | Arch/Debian hybrid depending on build; launcher runs regardless, toolset coverage depends on the repo. |

All installers use a **per-package loop**: a package missing from one distro's
repo never aborts the run — you get a summary of what landed and how to get the
rest.

## What's deliberately **not** baked in
No evil-twin / captive-portal credential-harvesting frameworks, no RF transmit
jam/spoof/replay, no IMSI-catcher tooling. Kraken is a scanning, analysis, and
**authorized**-engagement launcher — add anything beyond that yourself, under
your own rules of engagement.

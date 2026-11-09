# 🐙 KRAKEN

**Strikebacktech (Kenesis_X) — Northern Colorado**
A touch-first Raspberry Pi pentest, SDR, and RF command deck. One app: every
networking & RF tool a Pi can run, a gqrx-class signal analyzer, licensed-HAM
transmit, device flashing, geofencing, a field notebook, and a stats dashboard —
black & red, built to run hard but stay smooth. Ships as **web, Android (.aab),
desktop (.exe), and a flashable Pi 5 image**.

![Kraken home](docs/screenshots/home.png)

> Authorized testing only. No IMSI catchers, no jam/spoof/replay RF, no evil-twin
> or credential-harvesting tooling, no keystroke/traffic surveillance. Transmit is
> licensed amateur bands only.

---

## Pages

The app is an 11-page deck with a **persistent top navigation** — the numbered
bar is fixed on top of every page, so you can jump to any page from anywhere
(keys `1`–`9`, `0` = About, ⚙ = Settings, 🔒 = Lock).

| # | Page | What it does |
|---|------|--------------|
| 1 | **Home** | The splash. |
| 2 | **Deck** | 155 tools across 19 tabs — recon, scan, web, wireless, Bluetooth, NFC, MITM, passwords, AD, exploitation, cloud, Android. Scope-checked and logged. |
| 3 | **Signal** | gqrx-class analyzer: spectrum, waterfall, spectrogram, constellation, scope, radar, sonar, persistence, vector, power, RF-physics, monitor, HAM, GNSS. Point-click A→B forensics, opt-in cursor info, GQRX/SDR#-style demod + squelch + colormap + bookmarks, 1 MHz–6 GHz band plan, Log-RX to Records. |
| 4 | **Track** | Passive activity monitor (public broadcast only) + attack detection, plus a **CSI heatmap & device-topology flow view** (⬡ Topology). Click a device → Signal, tuned. |
| 5 | **Map** | Leaflet GIS: base/overlay layers, your **Carto Voyager** key, a **WiGLE plugin**, distance + directions, GeoJSON export, and a **geofence** for zone presence. |
| 6 | **TX** | Licensed-HAM transmit behind a gold **safety interlock**: CW/tone/FM/AFSK/SSTV + digital image modes (HamDRM/WEFAX/ATV-DATV/KG-STV/…), Wi-Fi/LoRa/BLE image streaming, **Baofeng/CHIRP** programming, **mesh / VoIP (Call-over-IP) / burst**, and **concurrent multi-channel** RX+TX. |
| 7 | **Records** | Field notebook — auto-logs TX/RX, takes manual entries with images + graph snapshots + GPS, exports the whole thing to one self-contained **notebook .html** (also JSON/Markdown/CSV). |
| 8 | **Stats** | Pwnagotchi-style dashboard — networks/handshakes/pcaps/devices/RX/TX/sessions/uptime, activity chart, import/export. |
| 9 | **Devices** | Flash & manage **your own** hardware — Web-Serial console, firmware flasher (esptool/picotool/avrdude/dfu-util), SSH/SFTP/ADB fleet. |
| 10 | **About** | Platform overview. |
| 11 | **Settings** | 30 themes, logo watermark, device manager, API keys (Carto/WiGLE), data compare, **🔒 lock / panic-wipe**, export/import. |

![Kraken pages](docs/screenshots/pages.png)

*Signal · Deck · Transmit · Stats · Devices*

---

## Run it

Unzip, then pick a target:

### Web
Open **`webapp/index.html`** in a Chromium browser. (Use the shell — that's where
the top navigation lives; the individual `*.html` files are the panes it loads.)
First launch asks you to set a lock code.

### Desktop (.exe / AppImage) — Electron
```bash
cd webapp
npm install
npx electron .            # run
# build installers: see PACKAGING.md (electron-builder)
```

### Android (.aab for Google Play) — Capacitor
```bash
cd webapp
npm install
npx cap init Kraken com.strikeback.kraken --web-dir=.
npx cap add android
npx cap copy && npx cap sync
npx cap open android       # set signing/icon, then Build → Bundle(.aab)
```
Landscape is locked in `capacitor.config.json`; the hard lock is one line in
`AndroidManifest.xml` — see `webapp/PACKAGING.md`.

### Raspberry Pi 5 (.img) — Pi OS / Kali / Parrot / Athena
```bash
# install on a running Pi:
sudo ./install.sh && sudo ./install_tools.sh && sudo systemctl enable --now raspyjackx
# OR bake a flashable image from any arm64 base:
sudo ./build_img.sh --base <raspios|kali|parrot|athena>.img
```
See **`README_IMAGE.md`** for the full image pipeline.

---

## Lock & wipe
- **Lock screen** gates access with a code you set on first launch (stored
  *hashed* on-device). Re-lock anytime from the 🔒 button in the top nav.
- **Panic wipe** (lock screen + Settings) erases all on-device Kraken data after
  a double-confirm. On a native install, `uninstall.sh` removes the program,
  services, and generated loot — scoped to Kraken's own paths only.

---

## Project layout
```
raspyjackx/
├─ webapp/              # the app (index.html = entry) + packaging
│  ├─ index.html, *.html, assets/
│  ├─ package.json, electron-main.js, capacitor.config.json
│  └─ rpi-kiosk.sh, PACKAGING.md
├─ raspyjackx/          # native Pi Python app (PySide6)
├─ hw_setup/            # SDR / Wi-Fi adapter helpers
├─ systemd/             # service units
├─ install.sh, install_tools.sh, uninstall.sh
├─ build_img.sh, README_IMAGE.md
└─ docs/screenshots/
```

---

## Scope & safety
Kraken is a scanning, analysis, and **authorized**-engagement platform. It
deliberately omits replay/clone/jam/spoof RF, cellular/GSM/satphone transmit,
evil-twin/credential-harvesting, keystroke/traffic surveillance, caller-ID
spoofing, and tracking of private individuals. Transmit is gated behind a safety
interlock and limited to amateur bands you're licensed for. You are responsible
for operating within your license and local law (e.g. FCC Part 97 / Part 95).

The web pages are the control surface; on the Pi, the native app runs the real
binaries (nmap, gqrx, CHIRP, baresip, direwolf, hamlib, esptool, …).

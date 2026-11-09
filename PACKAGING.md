# Kraken — build for Web · Desktop (.exe) · Android (.aab) · Raspberry Pi

The whole UI is plain HTML/CSS/JS (`strikeback_x.html` + the page files + Leaflet
for the map). One codebase ships to every target.

## Files
`strikeback_x.html` (shell / entry, also copied as `index.html`), `deck.html`,
`signal_display.html`, `activity_monitor.html`, `map.html`, `settings.html`.
Keep them together. The map needs internet for tiles (or a local tile cache).

---

## 1. Web (HTML)
Already done — it *is* the web app. Host the folder on any static server:
```bash
python3 -m http.server 8080      # then open http://localhost:8080/strikeback_x.html
# or drop the folder on Netlify / Vercel / nginx / GitHub Pages
```

## 2. Desktop (.exe on Windows, AppImage/.deb on Linux) — Electron
```bash
npm install
npm start               # run it
npm run dist:win        # -> dist/Kraken-Setup-1.0.0.exe   (build on Windows, or wine)
npm run dist:linux      # -> dist/Kraken-1.0.0.AppImage + .deb
```
(For a smaller binary, Tauri is an alternative: point `distDir` at this folder.)

## 3. Android (.aab for Google Play) — Capacitor
```bash
npm install
npx cap init Kraken com.strikeback.kraken --web-dir=.
npx cap add android
npx cap copy && npx cap sync
# open in Android Studio to set signing, icon, version:
npx cap open android
# then build the Play bundle:
cd android && ./gradlew bundleRelease     # -> android/app/build/outputs/bundle/release/app-release.aab
```
Upload `app-release.aab` to the Play Console. Set app name **Kraken**, package
`com.strikeback.kraken`. (A Trusted Web Activity via Bubblewrap is a lighter
alternative if you host the web app and just wrap the URL.)

### Lock to LANDSCAPE (menu is far easier to navigate sideways)
Capacitor's config hint is set, but the **hard lock** is one line in the
Android manifest. After `npx cap add android`, edit
`android/app/src/main/AndroidManifest.xml` and add `screenOrientation` to the
`<activity>`:
```xml
<activity
    android:name=".MainActivity"
    android:screenOrientation="landscape"
    android:configChanges="orientation|keyboardHidden|keyboard|screenSize|...">
```
The web app already compacts its chrome in landscape (CSS `@media
(orientation:landscape)`) and calls `screen.orientation.lock('landscape')` at
runtime, so on phones, tablets, and PWA installs it comes up sideways with the
numbered nav reachable and the tool rail full-height. For an even harder lock
you can add the orientation plugin:
```bash
npm i @capacitor/screen-orientation && npx cap sync
```

## 4. Raspberry Pi
Two options:
- **Native touchscreen app** (richer, drives real tools): the Python app in the
  parent folder — `./install.sh` then `sudo systemctl enable --now raspyjackx`.
- **Web kiosk** (this UI full-screen):
  ```bash
  chmod +x rpi-kiosk.sh && ./rpi-kiosk.sh
  ```
  To auto-start, add a systemd `graphical.target` service that runs `rpi-kiosk.sh`.

---

### Notes
- One source of truth: edit the HTML once, rebuild any target.
- Icons/splash: drop a 1024px `logo-1024.png` (in `../assets/`) into each
  platform's icon slot (electron-builder `build.icon`, Capacitor `resources/`).
- Map tiles need network; for offline RPi use a local MBTiles server and point
  Leaflet at `http://localhost:8080/{z}/{x}/{y}.png`.

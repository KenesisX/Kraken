#!/usr/bin/env bash
# install_tools.sh — the Athena-grade toolset referenced by tools.yaml.
#
#   ./install_tools.sh          # Raspberry Pi OS 64 — installs everything
#   ./install_tools.sh --kali   # Kali ARM — skips what's already preloaded
#
# Per-package loop: one missing package never aborts the run. At the end you
# get a summary of what landed and what didn't (with how to get the rest).
set -uo pipefail

KALI=0
[[ "${1:-}" == "--kali" ]] && KALI=1

if [[ $EUID -ne 0 ]]; then echo "[!] Run with sudo."; exit 1; fi

echo "[*] Updating apt..."
apt-get update -y || true

# Core tools present in both Pi OS and Kali repos.
APT_PKGS=(
  nmap masscan arp-scan netdiscover dnsrecon dnsenum dnsutils whois
  tcpdump tshark iw rfkill aircrack-ng wifite kismet bettercap
  mdk4 reaver pixiewps hcxtools hcxdumptool
  bluez nikto whatweb gobuster ffuf feroxbuster wpscan sqlmap hydra medusa
  wafw00f dirb john hashcat hashcat-utils crunch cewl hashid
  ncat netcat-openbsd socat
  rtl-sdr rtl-433 gqrx-sdr soapysdr-tools soapysdr-module-rtlsdr multimon-ng
  hackrf airspy soapysdr-module-hackrf soapysdr-module-airspy
  inspectrum acarsdec dumpvdl2 direwolf fldigi wsjtx gnuradio gr-gsm
  zaproxy wfuzz commix apktool aapt jadx
  android-tools-adb android-tools-fastboot
  minicom python3-serial dfu-util avrdude esptool
  wireshark-common libpcap-dev
  seclists wordlists zip git curl jq golang-go python3-pip pipx
  fonts-noto-core fonts-symbola
)

# Kali-only / heavier packages — only attempt on Kali or if user wants them.
# Note: evil-twin / captive-portal credential-harvesting frameworks
# (wifipumpkin3, eaphammer, hostapd-wpe, airgeddon's evil-twin) are deliberately
# NOT installed — RaspyJack-X doesn't ship phishing/credential-capture tooling.
KALI_PKGS=( metasploit-framework exploitdb responder enum4linux-ng crackmapexec
            theharvester dump1090-mutable
            impacket-scripts kerbrute amass dirsearch fierce recon-ng )

installed=(); missing=()

try_apt () {
  for p in "$@"; do
    if dpkg -s "$p" >/dev/null 2>&1; then installed+=("$p"); continue; fi
    if apt-get install -y "$p" >/dev/null 2>&1; then installed+=("$p")
    else missing+=("$p"); fi
  done
}

echo "[*] Installing core toolset..."
try_apt "${APT_PKGS[@]}"

echo "[*] Installing offensive toolset..."
try_apt "${KALI_PKGS[@]}"

# Go/pipx tools not in Pi OS apt (subfinder, nuclei, netexec).
echo "[*] Fetching tools not in apt (best-effort)..."
if command -v pipx >/dev/null 2>&1; then
  sudo -u "${SUDO_USER:-root}" pipx install netexec 2>/dev/null && installed+=("netexec(pipx)") || missing+=("netexec")
fi
if command -v go >/dev/null 2>&1; then
  export GOBIN=/usr/local/bin
  for t in \
    "subfinder:github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest" \
    "nuclei:github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest" \
    "naabu:github.com/projectdiscovery/naabu/v2/cmd/naabu@latest" \
    "httpx:github.com/projectdiscovery/httpx/cmd/httpx@latest" \
    "katana:github.com/projectdiscovery/katana/cmd/katana@latest" \
    "dalfox:github.com/hahwul/dalfox/v2@latest" \
    "kerbrute:github.com/ropnop/kerbrute@latest" ; do
    name="${t%%:*}"; path="${t#*:}"
    go install "$path" 2>/dev/null && installed+=("${name}(go)") || missing+=("$name")
  done
else
  missing+=("projectdiscovery+dalfox+kerbrute(need golang)")
fi
# Python tools via pipx (bloodhound, URH, cloud auditors)
if command -v pipx >/dev/null 2>&1; then
  for p in bloodhound urh scoutsuite prowler kube-hunter frida-tools objection qspectrumanalyzer; do
    sudo -u "${SUDO_USER:-root}" pipx install "$p" 2>/dev/null \
      && installed+=("${p}(pipx)") || missing+=("$p")
  done
fi
# trivy (own apt repo), satdump, dump978-fa (FlightAware repo) aren't in the
# default repos — the summary lists them; install from their project docs.

# rockyou is gzipped on some distros — unpack if needed.
if [[ -f /usr/share/wordlists/rockyou.txt.gz && ! -f /usr/share/wordlists/rockyou.txt ]]; then
  gunzip -k /usr/share/wordlists/rockyou.txt.gz || true
fi

echo
echo "============================================================"
echo " Installed (${#installed[@]}): ${installed[*]:-none}"
echo
echo " Missing   (${#missing[@]}): ${missing[*]:-none}"
echo "============================================================"
if [[ ${#missing[@]} -gt 0 ]]; then
  echo
  echo " For missing items on Pi OS:"
  echo "   • Metasploit:  use the Rapid7 nightly installer script"
  echo "   • subfinder/nuclei:  sudo apt install golang-go  then re-run"
  echo "   • Kali-only tools:  add Kali ARM repos, or run --kali on Kali"
fi
[[ $KALI -eq 1 ]] && echo "[*] --kali mode: skipped nothing; apt pulled from Kali repos."
echo "[✓] Toolset pass complete."

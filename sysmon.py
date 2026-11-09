"""
sysmon.py — lightweight system telemetry for the status bar.

Everything degrades gracefully: if a sensor or dependency is missing,
the field returns None/"--" instead of throwing. Works with or without
psutil, with or without a PiSugar UPS, on Pi 4 / Pi 5 / CM4.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, field

try:
    import psutil  # optional, nicer numbers if present
    _HAS_PSUTIL = True
except Exception:  # pragma: no cover
    psutil = None
    _HAS_PSUTIL = False


@dataclass
class Telemetry:
    hostname: str = "raspyjack-x"
    ips: dict = field(default_factory=dict)   # {iface: ip}
    cpu_pct: float | None = None
    mem_pct: float | None = None
    temp_c: float | None = None
    battery_pct: float | None = None
    charging: bool | None = None
    uptime_s: float | None = None
    clock: str = ""


class SysMon:
    """Poll once per call; cheap enough for a 1 Hz timer."""

    def __init__(self) -> None:
        self._last_cpu_sample = None

    # ---- individual probes -------------------------------------------------

    def hostname(self) -> str:
        try:
            return socket.gethostname()
        except Exception:
            return "raspyjack-x"

    def ips(self) -> dict:
        found: dict[str, str] = {}
        if _HAS_PSUTIL:
            try:
                for iface, addrs in psutil.net_if_addrs().items():
                    if iface == "lo":
                        continue
                    for a in addrs:
                        if a.family == socket.AF_INET and a.address:
                            found[iface] = a.address
                if found:
                    return found
            except Exception:
                pass
        # fallback: parse `ip -4 addr`
        try:
            out = subprocess.check_output(
                ["ip", "-4", "-o", "addr"], text=True, timeout=2
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[1] != "lo":
                    m = re.match(r"(\d+\.\d+\.\d+\.\d+)", parts[3])
                    if m:
                        found[parts[1]] = m.group(1)
        except Exception:
            pass
        return found

    def cpu_pct(self) -> float | None:
        if _HAS_PSUTIL:
            try:
                return psutil.cpu_percent(interval=None)
            except Exception:
                return None
        # fallback: delta of /proc/stat
        try:
            with open("/proc/stat") as f:
                fields = [float(x) for x in f.readline().split()[1:]]
            idle = fields[3] + fields[4]
            total = sum(fields)
            if self._last_cpu_sample:
                pi, pt = self._last_cpu_sample
                dt = total - pt
                di = idle - pi
                self._last_cpu_sample = (idle, total)
                if dt > 0:
                    return max(0.0, min(100.0, (1 - di / dt) * 100))
            self._last_cpu_sample = (idle, total)
        except Exception:
            return None
        return None

    def mem_pct(self) -> float | None:
        if _HAS_PSUTIL:
            try:
                return psutil.virtual_memory().percent
            except Exception:
                return None
        try:
            info = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, _, v = line.partition(":")
                    info[k.strip()] = float(v.split()[0])
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", 0)
            if total:
                return (1 - avail / total) * 100
        except Exception:
            return None
        return None

    def temp_c(self) -> float | None:
        # vcgencmd is the most accurate on Pi
        vc = shutil.which("vcgencmd")
        if vc:
            try:
                out = subprocess.check_output([vc, "measure_temp"], text=True, timeout=2)
                m = re.search(r"([\d.]+)", out)
                if m:
                    return float(m.group(1))
            except Exception:
                pass
        # generic thermal zone
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000.0
        except Exception:
            return None

    def battery(self) -> tuple[float | None, bool | None]:
        """Try PiSugar first, then a generic power_supply node."""
        # PiSugar server exposes a TCP text protocol on 8423
        try:
            with socket.create_connection(("127.0.0.1", 8423), timeout=0.4) as s:
                s.sendall(b"get battery\n")
                time.sleep(0.05)
                pct = float(s.recv(128).decode().split(":")[-1].strip())
                s.sendall(b"get battery_charging\n")
                time.sleep(0.05)
                chg = "true" in s.recv(128).decode().lower()
                return pct, chg
        except Exception:
            pass
        # generic sysfs battery (some UPS HATs register one)
        base = "/sys/class/power_supply"
        try:
            for name in os.listdir(base):
                cap = os.path.join(base, name, "capacity")
                if os.path.exists(cap):
                    with open(cap) as f:
                        pct = float(f.read().strip())
                    status = "Unknown"
                    sp = os.path.join(base, name, "status")
                    if os.path.exists(sp):
                        with open(sp) as f:
                            status = f.read().strip()
                    return pct, status.lower() == "charging"
        except Exception:
            pass
        return None, None

    def uptime_s(self) -> float | None:
        try:
            with open("/proc/uptime") as f:
                return float(f.read().split()[0])
        except Exception:
            return None

    # ---- aggregate ---------------------------------------------------------

    def sample(self) -> Telemetry:
        pct, chg = self.battery()
        return Telemetry(
            hostname=self.hostname(),
            ips=self.ips(),
            cpu_pct=self.cpu_pct(),
            mem_pct=self.mem_pct(),
            temp_c=self.temp_c(),
            battery_pct=pct,
            charging=chg,
            uptime_s=self.uptime_s(),
            clock=time.strftime("%H:%M:%S"),
        )


if __name__ == "__main__":
    import json
    mon = SysMon()
    mon.cpu_pct()  # prime the delta
    time.sleep(0.3)
    t = mon.sample()
    print(json.dumps(t.__dict__, indent=2))

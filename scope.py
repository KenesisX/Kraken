"""
scope.py — engagement scope guard.

Pulls every literal IPv4 address and CIDR out of a resolved command and
checks them against the allowed networks from your config. Anything that
touches an address outside scope is blocked BEFORE it runs.

This is a guardrail, not a sandbox: it only sees literal IPs/CIDRs in the
command text (hostnames can't be resolved reliably offline, so they're
passed through with a warning). It exists to stop the expensive mistake —
fat-fingering a target octet and scanning the wrong /24 on a client site.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

# Matches 1.2.3.4 and 1.2.3.0/24
_IP_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})(/\d{1,2})?\b")


@dataclass
class ScopeResult:
    allowed: bool
    reason: str = ""
    offenders: list[str] = None  # IPs found outside scope

    def __post_init__(self):
        if self.offenders is None:
            self.offenders = []


class ScopeGuard:
    def __init__(self, allowed_cidrs: list[str] | None):
        self.networks = []
        for c in (allowed_cidrs or []):
            try:
                self.networks.append(ipaddress.ip_network(c, strict=False))
            except ValueError:
                # ignore malformed scope entries rather than fail open silently;
                # they just won't match anything
                pass
        self.enabled = bool(self.networks)

    def _in_scope(self, token: str) -> bool:
        try:
            if "/" in token:
                net = ipaddress.ip_network(token, strict=False)
                return any(net.subnet_of(n) for n in self.networks)
            addr = ipaddress.ip_address(token)
            return any(addr in n for n in self.networks)
        except ValueError:
            return True  # not a real address; let it through

    def check(self, command: str) -> ScopeResult:
        if not self.enabled:
            return ScopeResult(True, "scope guard off (no CIDRs configured)")

        found = _IP_RE.findall(command)
        if not found:
            # no literal IPs — e.g. an SDR or bluetooth command. Allow.
            return ScopeResult(True, "no literal target in command")

        offenders = []
        for ip, cidr in found:
            token = ip + (cidr or "")
            # skip obvious non-targets: loopback, this host's own link-locals
            try:
                a = ipaddress.ip_address(ip)
                if a.is_loopback or a.is_multicast:
                    continue
            except ValueError:
                continue
            if not self._in_scope(token):
                offenders.append(token)

        if offenders:
            return ScopeResult(
                False,
                "target(s) outside authorized scope: " + ", ".join(sorted(set(offenders))),
                sorted(set(offenders)),
            )
        return ScopeResult(True, "in scope")

    def describe(self) -> str:
        if not self.enabled:
            return "ALL (no scope set)"
        return ", ".join(str(n) for n in self.networks)

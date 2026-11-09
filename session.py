"""
session.py — per-engagement logging.

Every launch opens (or reuses) an engagement folder under loot/:

  loot/<engagement>/
    session-YYYYmmdd-HHMMSS.jsonl   # one event per line (machine-readable)
    session-YYYYmmdd-HHMMSS.log     # human transcript (command + output)

This is the backbone of the report side: you finish a job, zip the folder,
and you've got a timestamped record of exactly what was run against what,
with full tool output. No more reconstructing the engagement from memory.
"""

from __future__ import annotations

import json
import os
import time


class SessionLogger:
    def __init__(self, log_dir: str, engagement: str = "default"):
        self.engagement = engagement or "default"
        self.base = os.path.join(os.path.expanduser(log_dir), self.engagement)
        os.makedirs(self.base, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.jsonl_path = os.path.join(self.base, f"session-{stamp}.jsonl")
        self.log_path = os.path.join(self.base, f"session-{stamp}.log")
        self._out = None  # open transcript handle for the active command
        self._event("session_start", engagement=self.engagement)
        self._banner(f"=== RaspyJack-X session · {self.engagement} · {stamp} ===")

    # ---- low level --------------------------------------------------------

    def _event(self, kind: str, **fields) -> None:
        rec = {"ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": kind}
        rec.update(fields)
        try:
            with open(self.jsonl_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            pass

    def _banner(self, text: str) -> None:
        try:
            with open(self.log_path, "a") as f:
                f.write(text + "\n")
        except Exception:
            pass

    # ---- command lifecycle ------------------------------------------------

    def start_command(self, label: str, command: str, in_scope: bool) -> None:
        self._event("command_start", label=label, command=command, in_scope=in_scope)
        self._banner(
            f"\n[{time.strftime('%H:%M:%S')}] $ {command}"
            f"   ({'IN SCOPE' if in_scope else 'SCOPE OVERRIDE'})"
        )
        try:
            self._out = open(self.log_path, "a")
        except Exception:
            self._out = None

    def write_output(self, text: str) -> None:
        if self._out:
            try:
                self._out.write(text)
                self._out.flush()
            except Exception:
                pass

    def end_command(self, exit_code: int) -> None:
        self._event("command_end", exit_code=exit_code)
        if self._out:
            try:
                self._out.write(f"\n[exit {exit_code}]\n")
                self._out.close()
            except Exception:
                pass
            self._out = None

    def blocked(self, label: str, command: str, reason: str) -> None:
        self._event("command_blocked", label=label, command=command, reason=reason)
        self._banner(f"\n[{time.strftime('%H:%M:%S')}] BLOCKED: {label} — {reason}")

    @property
    def folder(self) -> str:
        return self.base

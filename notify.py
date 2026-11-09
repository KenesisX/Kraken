"""
notify.py — push alerts to your phone / Galaxy Watch via ntfy.

ntfy (ntfy.sh, or self-hosted) mirrors to the phone and the watch shows it.
Notifications can carry action buttons, so a "Stop" button on the alert POSTs
straight back to the Pi's companion server — wrist control, no Android app.

Set notify.topic in tools.yaml to a private, hard-to-guess topic and subscribe
the ntfy app on your phone to it. Leave it blank to disable (no-op).
"""

from __future__ import annotations

import json
import threading
import urllib.request

_PRIO = {"min": 1, "low": 2, "default": 3, "high": 4, "max": 5}


class Notifier:
    def __init__(self, server="https://ntfy.sh", topic="", token="",
                 public_url="", priority="default"):
        self.server = (server or "").rstrip("/")
        self.topic = topic or ""
        self.token = token or ""
        self.public_url = (public_url or "").rstrip("/")
        self.priority = priority or "default"
        self.enabled = bool(self.server and self.topic)

    def stop_action(self):
        """ntfy action button that stops the running command on the Pi."""
        if not self.public_url:
            return None
        act = {"action": "http", "label": "Stop",
               "url": self.public_url + "/stop", "method": "POST"}
        if self.token:
            act["headers"] = {"X-RJX-Token": self.token}
        return act

    def push(self, title, message, tags=None, priority=None, actions=None):
        if not self.enabled:
            return
        payload = {
            "topic": self.topic,
            "title": title,
            "message": message,
            "priority": _PRIO.get(priority or self.priority, 3),
        }
        if tags:
            payload["tags"] = tags
        if actions:
            payload["actions"] = [a for a in actions if a]
        threading.Thread(target=self._send, args=(payload,), daemon=True).start()

    def _send(self, payload):
        try:
            data = json.dumps(payload).encode()
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(self.server, data=data, headers=headers)
            urllib.request.urlopen(req, timeout=4)
        except Exception:
            pass  # notifications are best-effort; never block the UI

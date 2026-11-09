"""
wizard.py — first-run setup. Shown once (when no overrides file exists) so a
fresh deck is scoped and labelled before the operator touches a tool.

Sets engagement name, authorized scope (CIDRs), the primary target/domain, the
Wi-Fi interface, and the watch ntfy topic — all via the on-screen keyboard —
then persists them and applies them to the running config.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from . import config as config_mod, osk


_FIELDS = [
    ("engagement", "Engagement name", "lab"),
    ("scope", "Authorized scope (comma CIDRs)", "10.0.0.0/8, 192.168.0.0/16"),
    ("target", "Primary target IP", "192.168.1.1"),
    ("domain", "Target domain", "example.local"),
    ("wlan", "Wi-Fi interface", "wlan1"),
    ("notify_topic", "Watch ntfy topic (optional)", ""),
]


class SetupWizard(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("RaspyJack-X — First-run setup")
        self.setModal(True)
        self.vals = {
            "engagement": cfg.engagement,
            "scope": ", ".join(cfg.scope) if cfg.scope else "",
            "target": cfg.variables.get("target", ""),
            "domain": cfg.variables.get("domain", ""),
            "wlan": cfg.variables.get("wlan", "wlan1"),
            "notify_topic": (cfg.notify or {}).get("topic", ""),
        }
        self._btns = {}

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Set up this deck for the engagement. "
                              "Tap a value to edit; you can change it later in VARS."))
        for key, label, _ph in _FIELDS:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setMinimumWidth(230)
            b = QPushButton(self.vals[key] or "(tap to set)")
            b.setObjectName("VarVal")
            b.clicked.connect(lambda _=False, k=key, t=label: self._edit(k, t))
            self._btns[key] = b
            row.addWidget(lbl)
            row.addWidget(b, 1)
            root.addLayout(row)

        act = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.clicked.connect(self.reject)
        done = QPushButton("Save & start")
        done.setObjectName("Primary")
        done.clicked.connect(self._finish)
        act.addWidget(skip)
        act.addWidget(done)
        root.addLayout(act)
        self.resize(640, 420)

    def _edit(self, key: str, label: str) -> None:
        dlg = osk.KeyEntry(label, self.vals.get(key, ""), self)
        if dlg.exec() == QDialog.Accepted:
            self.vals[key] = dlg.value()
            self._btns[key].setText(dlg.value() or "(tap to set)")

    def _finish(self) -> None:
        scope = [s.strip() for s in self.vals["scope"].split(",") if s.strip()]
        variables = dict(self.cfg.variables)
        variables["target"] = self.vals["target"]
        variables["domain"] = self.vals["domain"]
        variables["wlan"] = self.vals["wlan"]
        variables["mon"] = self.vals["wlan"]
        # apply to live config
        self.cfg.engagement = self.vals["engagement"] or self.cfg.engagement
        self.cfg.scope = scope or self.cfg.scope
        self.cfg.variables = variables
        self.cfg.notify = dict(self.cfg.notify or {})
        if self.vals["notify_topic"]:
            self.cfg.notify["topic"] = self.vals["notify_topic"]
        # persist
        config_mod.save_overrides(
            variables, engagement=self.cfg.engagement, scope=self.cfg.scope,
            notify_topic=self.vals["notify_topic"] or None)
        self.accept()

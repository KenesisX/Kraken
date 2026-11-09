"""
profiles.py — switch between tool config profiles from the UI.

Discovers tools*.yaml next to the active config and any *.yaml under a
profiles/ subfolder, so you can keep focused loadouts (wifi, recon, sdr) beside
the full menu and flip between them on the deck without a restart.
"""

from __future__ import annotations

import glob
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QScroller, QVBoxLayout, QWidget,
)

try:
    import yaml
    _HAS_YAML = True
except Exception:  # pragma: no cover
    yaml = None
    _HAS_YAML = False


def discover(current_path: str) -> list[tuple[str, str]]:
    base = os.path.dirname(os.path.abspath(current_path))
    paths = set(glob.glob(os.path.join(base, "tools*.yaml")))
    paths |= set(glob.glob(os.path.join(base, "profiles", "*.yaml")))
    paths.add(os.path.abspath(current_path))
    out = []
    for p in sorted(paths):
        out.append((_label(p), p))
    return out


def _label(path: str) -> str:
    n = "?"
    if _HAS_YAML:
        try:
            with open(path) as f:
                d = yaml.safe_load(f) or {}
            n = str(len(d.get("categories", [])))
        except Exception:
            pass
    return f"{os.path.basename(path)}  ·  {n} tabs"


class ProfileDialog(QDialog):
    def __init__(self, current_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Switch profile")
        self.setModal(True)
        self.chosen: str | None = None
        self._current = os.path.abspath(current_path)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Pick a tool profile to load:"))

        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setAlignment(Qt.AlignTop)
        for label, path in discover(current_path):
            mark = "● " if os.path.abspath(path) == self._current else "○ "
            b = QPushButton(mark + label)
            b.setObjectName("VarVal")
            b.clicked.connect(lambda _=False, p=path: self._pick(p))
            lay.addWidget(b)
        scroll = QScrollArea()
        scroll.setWidget(host)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        try:
            QScroller.grabGesture(scroll.viewport(), QScroller.LeftMouseButtonGesture)
        except Exception:
            pass
        root.addWidget(scroll, 1)

        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(cancel)
        root.addLayout(row)
        self.resize(560, 420)

    def _pick(self, path: str) -> None:
        self.chosen = path
        self.accept()

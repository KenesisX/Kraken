"""
academy.py — the master cert reference, browsable on the deck.

Lazy: academy.yaml is parsed only when the Learn screen is first opened, so it
adds nothing to boot time or the running footprint. Left list = certifications;
right pane = that cert's modules, each command shown with its note and a "Run"
button that fills placeholders from your VARS and runs it (scope-checked).
"""

from __future__ import annotations

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

_PATH = os.path.join(os.path.dirname(__file__), "academy.yaml")

# teaching placeholders -> VARS keys
_SUBS = {
    "<ip>": "target", "<url>": "url", "<domain>": "domain", "<subnet>": "subnet",
    "<iface>": "iface", "<mon>": "mon", "<bssid>": "bssid", "<lhost>": "gateway",
}


def load_certs() -> list:
    if not _HAS_YAML or not os.path.exists(_PATH):
        return []
    try:
        with open(_PATH) as f:
            return (yaml.safe_load(f) or {}).get("certs", [])
    except Exception:
        return []


def fill(cmd: str, variables: dict) -> str:
    out = cmd
    for ph, key in _SUBS.items():
        out = out.replace(ph, str(variables.get(key, ph)))
    return out


def _touch(area: QScrollArea) -> None:
    try:
        QScroller.grabGesture(area.viewport(), QScroller.LeftMouseButtonGesture)
    except Exception:
        pass


class AcademyDialog(QDialog):
    def __init__(self, variables: dict, run_cb, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Academy — cert reference")
        self.setModal(True)
        self.variables = variables
        self.run_cb = run_cb
        self.certs = load_certs()

        root = QHBoxLayout(self)

        # left: cert picker
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)
        if not self.certs:
            left_lay.addWidget(QLabel("academy.yaml not found\nor PyYAML missing."))
        for i, cert in enumerate(self.certs):
            b = QPushButton(f"{cert.get('code','?')}\n{cert.get('exam','')}")
            b.setObjectName("Tab")
            b.clicked.connect(lambda _=False, idx=i: self._show(idx))
            left_lay.addWidget(b)
        left_lay.addStretch(1)
        left_scroll = QScrollArea()
        left_scroll.setWidget(left)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setFixedWidth(120)
        _touch(left_scroll)
        root.addWidget(left_scroll)

        # right: content
        self.content_host = QWidget()
        self.content_lay = QVBoxLayout(self.content_host)
        self.content_lay.setAlignment(Qt.AlignTop)
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidget(self.content_host)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        _touch(self.content_scroll)
        root.addWidget(self.content_scroll, 1)

        self.resize(780, 450)
        if self.certs:
            self._show(0)

    def _clear(self) -> None:
        while self.content_lay.count():
            item = self.content_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show(self, idx: int) -> None:
        self._clear()
        cert = self.certs[idx]
        head = QLabel(f"{cert.get('code','')} · {cert.get('name','')}")
        head.setObjectName("Title")
        self.content_lay.addWidget(head)
        for mod in cert.get("modules", []):
            m = QLabel("▌ " + mod.get("topic", ""))
            m.setObjectName("Crumb")
            self.content_lay.addWidget(m)
            for it in mod.get("items", []):
                self.content_lay.addWidget(self._item(cert, it))

    def _item(self, cert, it) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 4, 6, 8)
        lay.setSpacing(3)

        note = QLabel(it.get("note", ""))
        note.setWordWrap(True)
        lay.addWidget(note)

        raw = it.get("cmd", "")
        row = QHBoxLayout()
        cmd_lbl = QLabel(raw)
        cmd_lbl.setObjectName("VarVal")
        cmd_lbl.setWordWrap(True)
        cmd_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(cmd_lbl, 1)
        if not raw.strip().startswith("#"):
            run = QPushButton("Run")
            run.setObjectName("Primary")
            run.setFixedWidth(70)
            run.clicked.connect(
                lambda _=False, c=raw: self.run_cb(
                    fill(c, self.variables), f"{cert.get('code','')} · {c[:40]}")
            )
            row.addWidget(run)
        lay.addLayout(row)
        return box

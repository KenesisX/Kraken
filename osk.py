"""
osk.py — on-screen keyboard + variables editor.

No physical keyboard on a field deck, so target/bssid/channel/domain/etc. are
edited by touch. VarsEditor lists every variable from tools.yaml; tap a value
to open a key-entry pad. Saved values persist via config.save_overrides so they
survive a restart, and commands pick them up on the next launch (no reboot).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


_ROWS = [
    list("1234567890"),
    list("qwertyupoi"),
    list("asdfghjkl"),
    list("zxcvbnm"),
    [".", ":", "/", "-", "_", "@", ",", "*"],
]


class OnScreenKeyboard(QWidget):
    """A compact touch keyboard bound to a QLineEdit."""

    def __init__(self, target: QLineEdit, parent=None):
        super().__init__(parent)
        self.target = target
        self._shift = False
        self._letter_btns: list[QPushButton] = []
        lay = QVBoxLayout(self)
        lay.setSpacing(6)
        lay.setContentsMargins(0, 0, 0, 0)

        for row in _ROWS:
            rw = QHBoxLayout()
            rw.setSpacing(6)
            for ch in row:
                b = self._key(ch)
                if ch.isalpha():
                    self._letter_btns.append(b)
                rw.addWidget(b)
            lay.addLayout(rw)

        # action row
        act = QHBoxLayout()
        act.setSpacing(6)
        self.btn_shift = QPushButton("⇧ ABC")
        self.btn_shift.setObjectName("Key")
        self.btn_shift.clicked.connect(self._toggle_shift)
        space = QPushButton("space")
        space.setObjectName("Key")
        space.clicked.connect(lambda: self._insert(" "))
        back = QPushButton("⌫")
        back.setObjectName("Key")
        back.clicked.connect(self._backspace)
        clear = QPushButton("clear")
        clear.setObjectName("Key")
        clear.clicked.connect(self.target.clear)
        for w, s in ((self.btn_shift, 2), (space, 4), (back, 1), (clear, 2)):
            act.addWidget(w, s)
        lay.addLayout(act)

    def _key(self, ch: str) -> QPushButton:
        b = QPushButton(ch)
        b.setObjectName("Key")
        b.clicked.connect(lambda _=False, c=ch: self._insert(c))
        return b

    def _insert(self, ch: str) -> None:
        if ch.isalpha() and self._shift:
            ch = ch.upper()
        self.target.insert(ch)

    def _backspace(self) -> None:
        self.target.backspace()

    def _toggle_shift(self) -> None:
        self._shift = not self._shift
        self.btn_shift.setText("⇧ abc" if self._shift else "⇧ ABC")
        for b in self._letter_btns:
            b.setText(b.text().upper() if self._shift else b.text().lower())


class KeyEntry(QDialog):
    """Edit one value with the on-screen keyboard."""

    def __init__(self, name: str, value: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit  {name}")
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(name))
        self.edit = QLineEdit(value)
        self.edit.setClearButtonEnabled(True)
        lay.addWidget(self.edit)
        lay.addWidget(OnScreenKeyboard(self.edit, self))

        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Save")
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        self.resize(760, 430)

    def value(self) -> str:
        return self.edit.text()


class VarsEditor(QDialog):
    """List all variables; tap a value to edit it on-screen."""

    def __init__(self, variables: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Variables")
        self.setModal(True)
        self._vars = dict(variables)
        self._value_btns: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.addWidget(QLabel("Tap a value to edit. Changes apply to the next command."))

        host = QWidget()
        grid = QGridLayout(host)
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)
        for r, (k, v) in enumerate(self._vars.items()):
            name = QLabel(k)
            name.setMinimumWidth(120)
            val = QPushButton(str(v))
            val.setObjectName("VarVal")
            val.clicked.connect(lambda _=False, key=k: self._edit(key))
            self._value_btns[k] = val
            grid.addWidget(name, r, 0)
            grid.addWidget(val, r, 1)

        scroll = QScrollArea()
        scroll.setWidget(host)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll, 1)

        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        done = QPushButton("Save all")
        done.setObjectName("Primary")
        done.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(done)
        outer.addLayout(row)
        self.resize(720, 440)

    def _edit(self, key: str) -> None:
        dlg = KeyEntry(key, str(self._vars.get(key, "")), self)
        if dlg.exec() == QDialog.Accepted:
            self._vars[key] = dlg.value()
            self._value_btns[key].setText(dlg.value())

    def result_vars(self) -> dict:
        return dict(self._vars)

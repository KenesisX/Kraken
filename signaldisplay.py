"""
signaldisplay.py — the Signal Display screen.

Same rail-and-grid layout as the main deck, but the categories are signal
DISPLAY types (spectrum, waterfall, constellation, scope, spectrogram, radar,
sonar, persistence, vector, power). Each entry launches a real instrument —
gqrx, GNU Radio Companion, URH, inspectrum, qspectrumanalyzer, rtl_power —
driven by the RTL-SDR V4 / HackRF. Run via the same scope-checked runner.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QScroller, QVBoxLayout, QWidget,
)

# category -> [(label, command, note)]
SIGNAL = [
    ("∿ Spectrum", [
        ("gqrx (FFT + waterfall GUI)", "gqrx", "Live FFT power vs frequency."),
        ("qspectrumanalyzer", "qspectrumanalyzer", "Multi-backend spectrum GUI."),
        ("rtl_power sweep → CSV", "timeout 20 rtl_power -f 400M:450M:10k {outdir}/spectrum.csv", "Wideband power sweep to file."),
    ]),
    ("▦ Waterfall", [
        ("gqrx waterfall", "gqrx", "Scrolling spectrum over time."),
        ("SDR++ ", "sdrpp", "Modern waterfall + demod."),
    ]),
    ("✦ Constellation (IQ)", [
        ("GNU Radio Companion", "gnuradio-companion", "Add a Constellation Sink to your flowgraph."),
        ("URH (analyze IQ)", "urh", "Inspect modulation / symbols."),
    ]),
    ("⎓ Oscilloscope", [
        ("GNU Radio (Time Sink)", "gnuradio-companion", "Time-domain waveform view."),
    ]),
    ("▤ Spectrogram", [
        ("inspectrum (capture)", "inspectrum {outdir}/capture.iq", "Time × frequency of a recorded IQ file."),
        ("Record IQ first", "rtl_sdr -f 433920000 -s 2400000 -n 24000000 {outdir}/capture.iq", "Grab 10 s of IQ to analyze."),
    ]),
    ("◎ Radar / Sonar", [
        ("GNU Radio flowgraph", "gnuradio-companion", "Build a PPI/ranging flowgraph (pulse + sweep)."),
    ]),
    ("◠ Persistence / Eye", [
        ("GNU Radio (persistence)", "gnuradio-companion", "Overlaid traces / eye diagram."),
    ]),
    ("✧ Vector / Phase", [
        ("GNU Radio (phase)", "gnuradio-companion", "Polar / phasor display."),
    ]),
    ("▮ Power meter", [
        ("rtl_power → heatmap", "timeout 20 rtl_power -f 400M:450M:1k {outdir}/power.csv", "RMS power over a band."),
        ("Soapy probe", "SoapySDRUtil --probe", "Device capabilities / gains."),
    ]),
]


def _touch(area: QScrollArea) -> None:
    try:
        QScroller.grabGesture(area.viewport(), QScroller.LeftMouseButtonGesture)
    except Exception:
        pass


class SignalDisplayDialog(QDialog):
    def __init__(self, variables: dict, run_cb, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Signal Display")
        self.setModal(True)
        self.variables = variables
        self.run_cb = run_cb

        root = QHBoxLayout(self)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)
        for i, (cat, _items) in enumerate(SIGNAL):
            b = QPushButton(cat)
            b.setObjectName("Tab")
            b.setMinimumHeight(46)
            b.clicked.connect(lambda _=False, idx=i: self._show(idx))
            ll.addWidget(b)
        ll.addStretch(1)
        ls = QScrollArea()
        ls.setWidget(left)
        ls.setWidgetResizable(True)
        ls.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ls.setFrameShape(QFrame.NoFrame)
        ls.setFixedWidth(150)
        _touch(ls)
        root.addWidget(ls)

        self.body_host = QWidget()
        self.body_lay = QVBoxLayout(self.body_host)
        self.body_lay.setAlignment(Qt.AlignTop)
        bs = QScrollArea()
        bs.setWidget(self.body_host)
        bs.setWidgetResizable(True)
        bs.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bs.setFrameShape(QFrame.NoFrame)
        _touch(bs)
        root.addWidget(bs, 1)

        self.resize(780, 450)
        self._show(0)

    def _fill(self, cmd: str) -> str:
        return cmd.replace("{outdir}", str(self.variables.get("outdir", "~/loot")))

    def _clear(self) -> None:
        while self.body_lay.count():
            it = self.body_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _show(self, idx: int) -> None:
        self._clear()
        cat, items = SIGNAL[idx]
        head = QLabel(cat)
        head.setObjectName("Title")
        self.body_lay.addWidget(head)
        for label, cmd, note in items:
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(6, 4, 6, 8)
            lay.setSpacing(3)
            n = QLabel(note)
            n.setWordWrap(True)
            lay.addWidget(n)
            row = QHBoxLayout()
            c = QLabel(self._fill(cmd))
            c.setObjectName("VarVal")
            c.setWordWrap(True)
            row.addWidget(c, 1)
            run = QPushButton("Launch")
            run.setObjectName("Primary")
            run.setFixedWidth(84)
            run.clicked.connect(
                lambda _=False, cc=self._fill(cmd), ll=label: self.run_cb(cc, "Signal · " + ll))
            row.addWidget(run)
            lay.addLayout(row)
            self.body_lay.addWidget(box)

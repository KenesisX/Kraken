"""
art.py — the anime layer: kitsune-mask mascot, boot splash, flavor quips.

Everything degrades gracefully. If PySide6.QtSvg isn't installed, the mascot
simply doesn't render (the app still runs); the splash falls back to text.
All assets are inline so there's no file dependency and nothing to lose.
"""

from __future__ import annotations

import random
import time

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap

from . import theme

try:
    from PySide6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except Exception:  # pragma: no cover
    _HAS_SVG = False


# Logo: a flashy neon bomb — glowing red outline on black, glossy highlights,
# lit fuse with a hot spark burst. ORIGINAL emblem in the app's black/red theme
# with amber spark. Neon glow is faked with layered strokes (no SVG filters) so
# QtSvg renders it identically to a browser.
MASCOT_SVG = b"""
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="halo" cx="48%" cy="58%" r="55%">
      <stop offset="0" stop-color="#ff1f3d" stop-opacity="0.35"/>
      <stop offset="0.6" stop-color="#b3001b" stop-opacity="0.15"/>
      <stop offset="1" stop-color="#b3001b" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="spark" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="#ffe9a6" stop-opacity="0.95"/>
      <stop offset="0.5" stop-color="#ff6a1f" stop-opacity="0.55"/>
      <stop offset="1" stop-color="#ff1f3d" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <!-- ambient glow -->
  <circle cx="96" cy="118" r="98" fill="url(#halo)"/>

  <!-- bomb body: neon = wide dim halo stroke + crisp bright rim -->
  <circle cx="94" cy="132" r="52" fill="none" stroke="#ff1f3d" stroke-width="13" opacity="0.30"/>
  <circle cx="94" cy="132" r="52" fill="#140406"/>
  <circle cx="94" cy="132" r="52" fill="none" stroke="#ff3b52" stroke-width="4.5"/>
  <circle cx="94" cy="132" r="52" fill="none" stroke="#ffd0d6" stroke-width="1.2" opacity="0.5"/>
  <!-- glossy highlights -->
  <ellipse cx="70" cy="150" rx="10" ry="6" fill="#ff5c6c" opacity="0.45" transform="rotate(-35 70 150)"/>
  <ellipse cx="58" cy="166" rx="5" ry="3" fill="#ff5c6c" opacity="0.4" transform="rotate(-35 58 166)"/>

  <!-- big neon X across the bomb -->
  <g stroke-linecap="round">
    <line x1="63" y1="101" x2="125" y2="163" stroke="#ff1f3d" stroke-width="11" opacity="0.30"/>
    <line x1="125" y1="101" x2="63" y2="163" stroke="#ff1f3d" stroke-width="11" opacity="0.30"/>
    <line x1="63" y1="101" x2="125" y2="163" stroke="#ff3b52" stroke-width="5.5"/>
    <line x1="125" y1="101" x2="63" y2="163" stroke="#ff3b52" stroke-width="5.5"/>
    <line x1="63" y1="101" x2="125" y2="163" stroke="#ffd0d6" stroke-width="1.5" opacity="0.6"/>
    <line x1="125" y1="101" x2="63" y2="163" stroke="#ffd0d6" stroke-width="1.5" opacity="0.6"/>
  </g>

  <!-- fuse cap (neon) -->
  <path d="M78 86 L110 86 L104 62 L84 62 Z" fill="#140406" stroke="#ff1f3d" stroke-width="9" opacity="0.30"/>
  <path d="M78 86 L110 86 L104 62 L84 62 Z" fill="#140406" stroke="#ff3b52" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M82 75 L106 75" stroke="#ff5c6c" stroke-width="2.5" stroke-linecap="round"/>
  <ellipse cx="94" cy="62" rx="10" ry="3.2" fill="#140406" stroke="#ff3b52" stroke-width="2.5"/>

  <!-- fuse (neon, lit) -->
  <path d="M94 60 C 102 40 120 50 138 26" fill="none" stroke="#ff1f3d" stroke-width="9" opacity="0.30" stroke-linecap="round"/>
  <path d="M94 60 C 102 40 120 50 138 26" fill="none" stroke="#ff6a1f" stroke-width="3.5" stroke-linecap="round"/>

  <!-- spark burst (flashy) -->
  <circle cx="140" cy="22" r="22" fill="url(#spark)"/>
  <g stroke-linecap="round">
    <line x1="140" y1="22" x2="170" y2="6"  stroke="#ff8a1f" stroke-width="2"   opacity="0.85"/>
    <line x1="140" y1="22" x2="166" y2="42" stroke="#ff1f3d" stroke-width="2"   opacity="0.75"/>
    <line x1="140" y1="22" x2="150" y2="0"  stroke="#ffd36a" stroke-width="1.6" opacity="0.85"/>
    <line x1="140" y1="22" x2="112" y2="10" stroke="#ff8a1f" stroke-width="1.6" opacity="0.7"/>
  </g>
  <path d="M140 0 L148 16 L164 22 L148 28 L140 44 L132 28 L116 22 L132 16 Z" fill="#ff1f3d" opacity="0.75"/>
  <path d="M140 7 L146 18 L156 22 L146 26 L140 37 L134 26 L124 22 L134 18 Z" fill="#ffb648"/>
  <circle cx="140" cy="22" r="3.6" fill="#fff6e6"/>
  <!-- flying spark bits -->
  <g fill="#ffb648">
    <circle cx="164" cy="12" r="1.8" opacity="0.85"/>
    <circle cx="158" cy="40" r="1.6" opacity="0.8"/>
    <circle cx="118" cy="8" r="1.5" opacity="0.75"/>
    <circle cx="176" cy="26" r="1.5" opacity="0.7"/>
  </g>
</svg>
"""

QUIPS = [
    "trace clean. ghost in the wire.",
    "scope locked. hunt authorized.",
    "the fox sees every port.",
    "silent recon // loud results",
    "no packet escapes the mask.",
    "red team, red screen.",
    "listening on all frequencies…",
    "signal acquired. stand by.",
    "stay in scope, stay invisible.",
    "every badge has a shadow.",
]


def _svg_pixmap(svg: bytes, w: int, h: int) -> QPixmap | None:
    if not _HAS_SVG:
        return None
    try:
        renderer = QSvgRenderer(QByteArray(svg))
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        renderer.render(p)
        p.end()
        return pm
    except Exception:
        return None


def mascot_pixmap(size: int = 84) -> QPixmap | None:
    return _svg_pixmap(MASCOT_SVG, size, size)


def quip() -> str:
    return random.choice(QUIPS)


def make_splash():
    """A short black/red boot splash with the mascot and glitch wordmark."""
    from PySide6.QtWidgets import QSplashScreen

    w, h = 520, 340
    pm = QPixmap(w, h)
    pm.fill(QColor(theme.BG))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    # frame
    p.setPen(QPen(QColor(theme.ACCENT), 2))
    p.drawRect(5, 5, w - 10, h - 10)
    p.setPen(QPen(QColor(theme.ACCENT_DIM), 1))
    p.drawRect(12, 12, w - 24, h - 24)

    # mascot
    mp = mascot_pixmap(150)
    if mp:
        p.drawPixmap((w - 150) // 2, 34, mp)

    # wordmark
    p.setFont(QFont("DejaVu Sans Mono", 10, QFont.Bold))
    p.setPen(QColor(theme.FG_MUTED))
    p.drawText(0, 188, w, 18, Qt.AlignHCenter, "RED TEAM COMMAND DECK")
    p.setFont(QFont("DejaVu Sans Mono", 30, QFont.Bold))
    p.setPen(QColor(theme.ACCENT))
    p.drawText(0, 210, w, 44, Qt.AlignHCenter, "STRIKEBACK X")
    p.setFont(QFont("DejaVu Sans Mono", 10))
    p.setPen(QColor(theme.FG_MUTED))
    p.drawText(0, 256, w, 20, Qt.AlignHCenter, "// red team command deck  ·  KITSUNE build")
    p.setFont(QFont("DejaVu Sans Mono", 9))
    p.setPen(QColor(theme.ACCENT2))
    p.drawText(0, 290, w, 18, Qt.AlignHCenter, quip())
    p.end()

    return QSplashScreen(pm)


def hold_splash(app, splash, seconds: float = 1.1) -> None:
    """Pump the event loop so the splash paints, without freezing the UI."""
    if splash is None:
        return
    splash.show()
    t0 = time.time()
    while time.time() - t0 < seconds:
        app.processEvents()
        time.sleep(0.02)

"""
theme.py — "KITSUNE" skin: black + red, Athena/Cyborg-inspired, anime edge.

Tuned for small capacitive touchscreens: near-black base, crimson accents,
monospace headers for the hacker-deck feel, big hit targets, zero animation
so it stays snappy on the Pi 5's GPU. Swap ACCENT to retint everything.
"""

# ---- palette (black & red) ------------------------------------------------
ACCENT = "#ff1f3d"       # primary red
ACCENT_DIM = "#b3001b"   # deep crimson
ACCENT2 = "#ff5c6c"      # light red / anime pop
BG = "#0a0a0d"           # near black
BG_RAISED = "#111116"
BG_TILE = "#15151b"
BG_TILE_HOT = "#2a0e14"  # dark red wash on hover
FG = "#f5f5f7"
FG_MUTED = "#8a8a93"
DANGER = "#ff2d2d"
WARN = "#ffb648"
OK = "#ff5c6c"

TOUCH = 64               # min comfortable touch target (px)

MONO = '"DejaVu Sans Mono", "Noto Mono", monospace'
SANS = '"DejaVu Sans", "Noto Sans", sans-serif'


def stylesheet() -> str:
    return f"""
    QWidget {{
        background: {BG};
        color: {FG};
        font-family: {SANS};
        font-size: 15px;
    }}
    #StatusBar {{
        background: {BG_RAISED};
        border-bottom: 2px solid {ACCENT};
    }}
    #StatusBar QLabel {{ color: {FG_MUTED}; font-family: {MONO}; font-size: 13px; }}
    #StatusBar QLabel[role="value"] {{ color: {FG}; font-weight: 600; }}
    #StatusBar QLabel#Quip {{ color: {ACCENT2}; font-style: italic; }}

    QPushButton {{
        background: {BG_TILE};
        border: 1px solid #2a2a33;
        border-radius: 6px;
        padding: 10px;
        color: {FG};
    }}
    QPushButton:hover {{ background: {BG_TILE_HOT}; border-color: {ACCENT}; }}
    QPushButton:pressed {{ background: {ACCENT_DIM}; }}
    QPushButton:disabled {{ color: {FG_MUTED}; background: #0e0e12; }}

    QPushButton#Tool {{
        min-height: {TOUCH + 24}px;
        font-size: 16px;
        text-align: left;
        padding-left: 14px;
        border-left: 3px solid {ACCENT_DIM};
    }}
    QPushButton#Tool:hover {{ border-left: 3px solid {ACCENT}; }}

    QPushButton#Tab {{
        min-height: {TOUCH}px;
        min-width: 92px;
        border-radius: 6px;
        font-family: {MONO};
        font-size: 13px;
    }}
    QPushButton#Tab[active="true"] {{
        background: {ACCENT_DIM};
        border: 1px solid {ACCENT};
        color: #ffffff;
        font-weight: 700;
    }}
    QPushButton#Ctrl {{ min-height: {TOUCH}px; min-width: {TOUCH}px; font-size: 18px; }}
    QPushButton#Danger {{ border: 1px solid {DANGER}; color: {DANGER}; }}
    QPushButton#Danger:pressed {{ background: {DANGER}; color: #ffffff; }}

    QPlainTextEdit, QTextEdit {{
        background: #050506;
        color: #e6e6ea;
        border: 1px solid {ACCENT_DIM};
        border-radius: 6px;
        font-family: {MONO};
        font-size: 13px;
    }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ width: 14px; background: {BG}; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {ACCENT_DIM}; border-radius: 7px; min-height: 48px; }}
    QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

    QLabel#Title {{ font-family: {MONO}; font-size: 18px; font-weight: 700; color: {ACCENT}; }}
    QLabel#Crumb {{ color: {FG_MUTED}; font-family: {MONO}; font-size: 13px; }}

    QDialog {{ background: {BG_RAISED}; border: 1px solid {ACCENT}; }}
    QPushButton#Key {{ min-height: 48px; min-width: 40px; font-family: {MONO}; font-size: 16px; }}
    QPushButton#Primary {{ background: {ACCENT_DIM}; border: 1px solid {ACCENT}; color: #fff; font-weight: 700; min-height: 48px; }}
    QPushButton#Primary:pressed {{ background: {ACCENT}; }}
    QPushButton#VarVal {{ text-align: left; padding-left: 12px; min-height: 44px; font-family: {MONO}; color: {ACCENT2}; }}
    QLineEdit {{
        background: #050506; border: 1px solid #2a2a33;
        border-radius: 6px; padding: 10px; min-height: {TOUCH - 24}px;
    }}
    QToolTip {{ background: {BG_RAISED}; color: {FG}; border: 1px solid {ACCENT}; }}
    """

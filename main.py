"""
main.py — entry point.

  python3 -m raspyjackx.main              # fullscreen (device)
  python3 -m raspyjackx.main --windowed   # 800x480 window (desktop dev)
  RJX_CONFIG=/path/to/tools.yaml python3 -m raspyjackx.main

On a headless dev box with no Qt platform, set:
  QT_QPA_PLATFORM=offscreen
"""

from __future__ import annotations

import argparse
import os
import sys

from .config import load
from . import ui


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="RaspyJack-X touchscreen launcher")
    p.add_argument("--windowed", action="store_true", help="run in a window")
    p.add_argument("--config", default=None, help="path to tools.yaml")
    args = p.parse_args(argv)

    path = (
        args.config
        or os.environ.get("RJX_CONFIG")
        or os.path.join(os.path.dirname(__file__), "tools.yaml")
    )
    try:
        cfg = load(path)
    except Exception as e:
        print(f"[fatal] could not load config: {e}", file=sys.stderr)
        return 2

    return ui.run(cfg, fullscreen=not args.windowed)


if __name__ == "__main__":
    raise SystemExit(main())

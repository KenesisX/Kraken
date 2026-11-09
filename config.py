"""
config.py — load and validate tools.yaml.

The menu is data-driven: edit tools.yaml, not the code. Variables like
{iface} and {subnet} are expanded into every command at launch time so
you set your interface/target once.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

# Touch-edited variable values persist here, overriding tools.yaml defaults.
OVERRIDES_PATH = os.path.expanduser("~/.config/raspyjackx/vars.json")

try:
    import yaml
    _HAS_YAML = True
except Exception:  # pragma: no cover
    yaml = None
    _HAS_YAML = False


@dataclass
class Tool:
    label: str
    cmd: str
    confirm: bool = False
    shell: bool = False
    desc: str = ""


@dataclass
class Category:
    name: str
    icon: str = "•"
    tools: list[Tool] = field(default_factory=list)


@dataclass
class AppConfig:
    title: str = "RaspyJack-X"
    variables: dict = field(default_factory=dict)
    categories: list[Category] = field(default_factory=list)
    require_consent: bool = True
    scope: list = field(default_factory=list)      # allowed CIDRs
    log_dir: str = "~/loot"
    engagement: str = "default"
    companion: dict = field(default_factory=dict)  # watch/phone HTTP server
    notify: dict = field(default_factory=dict)      # ntfy push config

    def expand(self, cmd: str) -> str:
        out = cmd
        for k, v in self.variables.items():
            out = out.replace("{" + k + "}", str(v))
        return out


def _coerce(raw: dict) -> AppConfig:
    cfg = AppConfig(
        title=raw.get("title", "RaspyJack-X"),
        variables=dict(raw.get("variables", {})),
        require_consent=bool(raw.get("require_consent", True)),
        scope=list(raw.get("scope", [])),
        log_dir=raw.get("log_dir", "~/loot"),
        engagement=raw.get("engagement", "default"),
        companion=dict(raw.get("companion", {})),
        notify=dict(raw.get("notify", {})),
    )
    for c in raw.get("categories", []):
        cat = Category(name=c.get("name", "?"), icon=c.get("icon", "•"))
        for t in c.get("tools", []):
            cat.tools.append(
                Tool(
                    label=t.get("label", "?"),
                    cmd=t.get("cmd", ""),
                    confirm=bool(t.get("confirm", False)),
                    shell=bool(t.get("shell", False)),
                    desc=t.get("desc", ""),
                )
            )
        cfg.categories.append(cat)
    return cfg


def load(path: str) -> AppConfig:
    if not _HAS_YAML:
        raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    cfg = _coerce(raw)
    _apply_overrides(cfg)
    return cfg


def overrides_exist() -> bool:
    return os.path.exists(OVERRIDES_PATH)


def _apply_overrides(cfg: AppConfig) -> None:
    try:
        if not os.path.exists(OVERRIDES_PATH):
            return
        with open(OVERRIDES_PATH) as f:
            ov = json.load(f)
        if not isinstance(ov, dict):
            return
        if "variables" in ov or "engagement" in ov or "scope" in ov:
            # structured overrides (wizard / newer saves)
            cfg.variables.update({str(k): v for k, v in ov.get("variables", {}).items()})
            if ov.get("engagement"):
                cfg.engagement = ov["engagement"]
            if ov.get("scope"):
                cfg.scope = list(ov["scope"])
            if ov.get("notify_topic"):
                cfg.notify = dict(cfg.notify or {})
                cfg.notify["topic"] = ov["notify_topic"]
        else:
            # legacy flat {var: value}
            cfg.variables.update({str(k): v for k, v in ov.items()})
    except Exception:
        pass  # a bad overrides file never blocks startup


def _read_overrides() -> dict:
    try:
        with open(OVERRIDES_PATH) as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d if ("variables" in d or "engagement" in d) else {"variables": d}
    except Exception:
        pass
    return {"variables": {}}


def save_overrides(variables: dict, engagement: str | None = None,
                   scope: list | None = None, notify_topic: str | None = None) -> bool:
    """Persist edited values (merges with any existing overrides)."""
    try:
        cur = _read_overrides()
        cur.setdefault("variables", {})
        cur["variables"].update(variables or {})
        if engagement is not None:
            cur["engagement"] = engagement
        if scope is not None:
            cur["scope"] = scope
        if notify_topic is not None:
            cur["notify_topic"] = notify_topic
        os.makedirs(os.path.dirname(OVERRIDES_PATH), exist_ok=True)
        with open(OVERRIDES_PATH, "w") as f:
            json.dump(cur, f, indent=2)
        return True
    except Exception:
        return False

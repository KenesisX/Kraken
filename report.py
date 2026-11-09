"""
report.py — turn a session's JSONL log into a findings draft.

Reads the newest session-*.jsonl in an engagement folder and writes a
timestamped report.md + report.html (self-contained, black/red styled, so you
can open it and Print-to-PDF). If wkhtmltopdf/pandoc/weasyprint is present it
also drops a .pdf. No external deps required for the md/html.

This closes the loop: LEARN → run tools → the log becomes the deliverable.
"""

from __future__ import annotations

import glob
import html
import json
import os
import re
import shutil
import subprocess
import time

# ---- findings auto-classifier -------------------------------------------
# Scan tool output from the session transcript and tag likely findings by
# severity. Heuristic, not a scanner — it surfaces what to look at, you confirm.
_SEV_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

_RULES = [
    (re.compile(r"MS17-010|EternalBlue", re.I), "CRITICAL", "SMB MS17-010 (EternalBlue) indicated"),
    (re.compile(r"\bVULNERABLE\b"), "HIGH", "nmap script flagged VULNERABLE"),
    (re.compile(r"parameter '([^']+)' is vulnerable", re.I), "HIGH", "SQL injection (sqlmap)"),
    (re.compile(r"\[(critical)\]", re.I), "CRITICAL", "nuclei: critical finding"),
    (re.compile(r"\[(high)\]", re.I), "HIGH", "nuclei: high finding"),
    (re.compile(r"\[(medium)\]", re.I), "MEDIUM", "nuclei: medium finding"),
    (re.compile(r"\[(low)\]", re.I), "LOW", "nuclei: low finding"),
    (re.compile(r"\bPMKID\b|EAPOL.*handshake|handshake.*captured", re.I), "MEDIUM", "WPA PMKID/handshake captured (crackable)"),
    (re.compile(r"Anonymous FTP login allowed|ftp-anon", re.I), "MEDIUM", "Anonymous FTP allowed"),
    (re.compile(r"CVE-\d{4}-\d{3,}", re.I), "HIGH", "CVE referenced in output"),
    (re.compile(r"\[\+\].*(Pwn3d|admin|Administrator)", re.I), "HIGH", "Admin/privileged access indicated"),
    (re.compile(r"(\d{1,5})/tcp\s+open\s+(\S+)"), "INFO", "Open TCP port"),
]


def classify(text: str) -> list[dict]:
    seen = set()
    out = []
    for line in text.splitlines():
        for rx, sev, title in _RULES:
            m = rx.search(line)
            if not m:
                continue
            ev = line.strip()[:160]
            if title == "Open TCP port":
                t = f"Open TCP port {m.group(1)}/{m.group(2)}"
            elif title.startswith("nuclei"):
                t = f"nuclei {m.group(1).lower()}: {ev[:70]}"
            else:
                t = title
            key = (sev, t)
            if key in seen:
                break
            seen.add(key)
            out.append({"sev": sev, "title": t, "evidence": ev})
            break
    out.sort(key=lambda f: _SEV_RANK.get(f["sev"], 9))
    return out


def _latest_jsonl(engagement_dir: str) -> str | None:
    files = sorted(glob.glob(os.path.join(engagement_dir, "session-*.jsonl")))
    return files[-1] if files else None


def _latest_log(engagement_dir: str) -> str | None:
    files = sorted(glob.glob(os.path.join(engagement_dir, "session-*.log")))
    return files[-1] if files else None


def _load_events(path: str) -> list[dict]:
    out = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception:
        pass
    return out


def _digest(events: list[dict]) -> dict:
    cmds = []
    cur = None
    blocked = []
    engagement = "engagement"
    ts_first = ts_last = None
    for e in events:
        ts = e.get("ts")
        if ts:
            ts_first = ts if ts_first is None else ts_first
            ts_last = ts
        kind = e.get("event")
        if kind == "session_start":
            engagement = e.get("engagement", engagement)
        elif kind == "command_start":
            cur = {"iso": e.get("iso", ""), "label": e.get("label", ""),
                   "command": e.get("command", ""), "in_scope": e.get("in_scope", True),
                   "exit": None}
        elif kind == "command_end" and cur is not None:
            cur["exit"] = e.get("exit_code")
            cmds.append(cur)
            cur = None
        elif kind == "command_blocked":
            blocked.append({"iso": e.get("iso", ""), "label": e.get("label", ""),
                            "command": e.get("command", ""), "reason": e.get("reason", "")})
    if cur is not None:
        cmds.append(cur)
    dur = int((ts_last - ts_first)) if (ts_first and ts_last) else 0
    return {
        "engagement": engagement, "commands": cmds, "blocked": blocked,
        "total": len(cmds),
        "ok": sum(1 for c in cmds if c["exit"] == 0),
        "fail": sum(1 for c in cmds if c["exit"] not in (0, None)),
        "overrides": sum(1 for c in cmds if not c["in_scope"]),
        "duration": dur,
    }


def _fmt_dur(s: int) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m}m {sec}s" if h else (f"{m}m {sec}s" if m else f"{sec}s")


def _findings_md(findings: list) -> list:
    if not findings:
        return ["## Auto-detected findings\n", "_None auto-detected. Review the "
                "timeline and raw logs — the classifier is a hint, not a scanner._\n"]
    L = ["## Auto-detected findings\n",
         "_Heuristic — confirm each before reporting._\n",
         "| Severity | Finding | Evidence |", "|---|---|---|"]
    for f in findings:
        ev = f["evidence"].replace("|", "\\|")
        L.append(f"| **{f['sev']}** | {f['title']} | `{ev}` |")
    L.append("")
    return L


def _markdown(d: dict, host: str, findings: list) -> str:
    L = []
    L.append(f"# Strikeback X — Engagement Report: {d['engagement']}\n")
    L.append(f"- **Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"- **Operator host:** {host}")
    L.append(f"- **Commands run:** {d['total']}  (ok {d['ok']}, non-zero {d['fail']})")
    L.append(f"- **Scope overrides:** {d['overrides']}")
    L.append(f"- **Blocked (out of scope):** {len(d['blocked'])}")
    L.append(f"- **Active duration:** {_fmt_dur(d['duration'])}\n")
    L.append("## Activity timeline\n")
    L.append("| Time | Action | Command | Result |")
    L.append("|------|--------|---------|--------|")
    for c in d["commands"]:
        res = "—" if c["exit"] is None else ("ok" if c["exit"] == 0 else f"exit {c['exit']}")
        scope = "" if c["in_scope"] else " ⚠override"
        cmd = c["command"].replace("|", "\\|")
        L.append(f"| {c['iso'][11:]} | {c['label']}{scope} | `{cmd}` | {res} |")
    if d["blocked"]:
        L.append("\n## Blocked by scope guard\n")
        for b in d["blocked"]:
            L.append(f"- `{b['command']}` — {b['reason']}")
    L.append("")
    L += _findings_md(findings)
    L.append("## Findings (fill in)\n")
    L.append("_Add confirmed findings, severity, evidence and remediation here. "
             "Full tool output is in the matching session-*.log file._\n")
    L.append("\n---\n*Generated by Strikeback X. Authorized testing only.*")
    return "\n".join(L)


_HTML_CSS = """
body{background:#0a0a0d;color:#e6e6ea;font-family:DejaVu Sans,sans-serif;max-width:900px;margin:24px auto;padding:0 18px}
h1{color:#ff1f3d;border-bottom:2px solid #b3001b;padding-bottom:8px}
h2{color:#ff5c6c;margin-top:28px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #2a2a33;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#15151b;color:#ff5c6c}
code{font-family:DejaVu Sans Mono,monospace;color:#ffb648;word-break:break-all}
li{margin:4px 0}
.meta{color:#8a8a93}
"""


def _sev_color(sev: str) -> str:
    return {"CRITICAL": "#ff2d2d", "HIGH": "#ff5c6c", "MEDIUM": "#ffb648",
            "LOW": "#7CFC9B", "INFO": "#8a8a93"}.get(sev, "#8a8a93")


def _findings_html(findings: list) -> str:
    if not findings:
        return ("<h2>Auto-detected findings</h2><p class=\"meta\">None auto-detected. "
                "Review the timeline and raw logs.</p>")
    rows = "".join(
        f"<tr><td><b style='color:{_sev_color(f['sev'])}'>{f['sev']}</b></td>"
        f"<td>{html.escape(f['title'])}</td>"
        f"<td><code>{html.escape(f['evidence'])}</code></td></tr>" for f in findings)
    return ("<h2>Auto-detected findings</h2>"
            "<p class=\"meta\">Heuristic — confirm each before reporting.</p>"
            f"<table><tr><th>Severity</th><th>Finding</th><th>Evidence</th></tr>{rows}</table>")


def _html(d: dict, host: str, findings: list) -> str:
    rows = []
    for c in d["commands"]:
        res = "—" if c["exit"] is None else ("ok" if c["exit"] == 0 else f"exit {c['exit']}")
        scope = "" if c["in_scope"] else " ⚠override"
        rows.append(
            f"<tr><td>{html.escape(c['iso'][11:])}</td>"
            f"<td>{html.escape(c['label'])}{scope}</td>"
            f"<td><code>{html.escape(c['command'])}</code></td>"
            f"<td>{res}</td></tr>")
    blocked = ""
    if d["blocked"]:
        items = "".join(f"<li><code>{html.escape(b['command'])}</code> — {html.escape(b['reason'])}</li>"
                        for b in d["blocked"])
        blocked = f"<h2>Blocked by scope guard</h2><ul>{items}</ul>"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Strikeback X Report — {html.escape(d['engagement'])}</title><style>{_HTML_CSS}</style></head><body>
<h1>Strikeback X — Engagement Report: {html.escape(d['engagement'])}</h1>
<p class="meta">Generated {time.strftime('%Y-%m-%d %H:%M:%S')} · host {html.escape(host)} ·
run {d['total']} (ok {d['ok']}, non-zero {d['fail']}) · overrides {d['overrides']} ·
blocked {len(d['blocked'])} · active {_fmt_dur(d['duration'])}</p>
<h2>Activity timeline</h2>
<table><tr><th>Time</th><th>Action</th><th>Command</th><th>Result</th></tr>{''.join(rows)}</table>
{blocked}
{_findings_html(findings)}
<h2>Findings (fill in)</h2>
<p class="meta">Add confirmed findings, severity, evidence and remediation here.
Full tool output is in the matching session log.</p>
<hr><p class="meta">Generated by Strikeback X. Authorized testing only.</p>
</body></html>"""


def _try_pdf(html_path: str, pdf_path: str) -> bool:
    if shutil.which("wkhtmltopdf"):
        try:
            subprocess.run(["wkhtmltopdf", "-q", html_path, pdf_path], timeout=60, check=True)
            return True
        except Exception:
            return False
    if shutil.which("pandoc"):
        try:
            subprocess.run(["pandoc", html_path, "-o", pdf_path], timeout=60, check=True)
            return True
        except Exception:
            return False
    return False


def generate(engagement_dir: str, host: str = "raspyjack-x") -> dict:
    """Returns {'md','html','pdf'(optional),'stats'}. Raises if no session log."""
    engagement_dir = os.path.expanduser(engagement_dir)
    jsonl = _latest_jsonl(engagement_dir)
    if not jsonl:
        raise FileNotFoundError("no session-*.jsonl in " + engagement_dir)
    d = _digest(_load_events(jsonl))
    logp = _latest_log(engagement_dir)
    findings = []
    if logp:
        try:
            with open(logp, errors="replace") as f:
                findings = classify(f.read())
        except Exception:
            findings = []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    md_path = os.path.join(engagement_dir, f"report-{stamp}.md")
    html_path = os.path.join(engagement_dir, f"report-{stamp}.html")
    with open(md_path, "w") as f:
        f.write(_markdown(d, host, findings))
    with open(html_path, "w") as f:
        f.write(_html(d, host, findings))
    d["findings"] = len(findings)
    out = {"md": md_path, "html": html_path, "stats": d}
    pdf_path = os.path.join(engagement_dir, f"report-{stamp}.pdf")
    if _try_pdf(html_path, pdf_path):
        out["pdf"] = pdf_path
    return out


if __name__ == "__main__":
    import sys
    print(generate(sys.argv[1] if len(sys.argv) > 1 else "."))

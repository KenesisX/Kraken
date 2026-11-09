"""
companion.py — tiny HTTP companion server for phone / Galaxy Watch.

Dependency-free (stdlib only). Serves:
  GET  /           round-watch control page (live status + Stop/Shutdown)
  GET  /status     JSON telemetry + engagement + scope + running command
  POST /stop       stop the running command   (token required)
  POST /shutdown   safe shutdown of the Pi    (token required)

Security posture: the only write endpoints are stop/shutdown (bounded, not
arbitrary exec), gated by a token header. Run it on the Pi's own hotspot or a
VPN, not a client LAN, and set a real token. Remote tool-launch is deliberately
NOT exposed here.

The UI thread pushes live status into CompanionState each second; /stop sets an
event the UI polls and acts on from the GUI thread (thread-safe).
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class CompanionState:
    def __init__(self):
        self._lock = threading.Lock()
        self.stop_event = threading.Event()
        self._status = {}

    def set_status(self, d: dict) -> None:
        with self._lock:
            self._status = dict(d)

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)


WATCH_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>RJX</title><style>
:root{--red:#ff1f3d;--dim:#b3001b;--bg:#0a0a0d;--fg:#f5f5f7;--mut:#8a8a93}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%;background:#000;color:var(--fg);font-family:monospace}
.wrap{min-height:100%;background:var(--bg);display:flex;flex-direction:column;
 align-items:center;justify-content:center;gap:8px;padding:16px;text-align:center}
.t{color:var(--red);font-weight:700;font-size:16px;letter-spacing:1px}
.row{font-size:13px;color:var(--mut)} .row b{color:var(--fg)}
.run{font-size:13px;color:var(--red);min-height:16px;max-width:92%;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.btn{width:88%;max-width:240px;min-height:52px;border-radius:26px;border:2px solid var(--red);
 background:#15151b;color:var(--fg);font-size:16px;font-weight:700;margin-top:6px}
.btn.sd{border-color:var(--dim);color:var(--dim)}
.ok{color:#7CFC9B;font-size:12px;min-height:14px}
</style></head><body><div class="wrap">
<div class="t">🦊 RJX</div>
<div class="row">eng <b id="eng">—</b></div>
<div class="row">🌐 <b id="ip">—</b> · 🌡 <b id="temp">—</b> · 🔋 <b id="batt">—</b></div>
<div class="row">scope <b id="scope">—</b></div>
<div class="run" id="run">idle</div>
<button class="btn" onclick="act('/stop')">■ STOP</button>
<button class="btn sd" onclick="if(confirm('Shut down the Pi?'))act('/shutdown')">⏻ SHUTDOWN</button>
<div class="ok" id="msg"></div>
</div><script>
const TOKEN="__TOKEN__";
async function poll(){try{const r=await fetch('/status');const s=await r.json();
 eng.textContent=s.engagement||'—';ip.textContent=s.ip||'—';
 temp.textContent=(s.temp!=null?s.temp+'°C':'—');batt.textContent=(s.batt!=null?s.batt+'%':'ext');
 scope.textContent=s.scope||'—';run.textContent=s.running?('▶ '+(s.current||'running')):'idle';
}catch(e){}}
async function act(p){try{const r=await fetch(p,{method:'POST',headers:{'X-RJX-Token':TOKEN}});
 msg.textContent=r.ok?'sent':'rejected';setTimeout(()=>msg.textContent='',1500);}catch(e){msg.textContent='no link';}}
poll();setInterval(poll,2000);
</script></body></html>"""


def _make_handler(state: CompanionState, token: str, html: str):
    class H(BaseHTTPRequestHandler):
        def _auth(self) -> bool:
            return (not token) or self.headers.get("X-RJX-Token") == token

        def _send(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/watch", "/index.html"):
                self._send(200, html, "text/html; charset=utf-8")
            elif self.path.startswith("/status"):
                self._send(200, json.dumps(state.status()))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            if not self._auth():
                self._send(401, json.dumps({"error": "unauthorized"}))
                return
            if self.path.startswith("/stop"):
                state.stop_event.set()
                self._send(200, json.dumps({"ok": True, "action": "stop"}))
            elif self.path.startswith("/shutdown"):
                self._send(200, json.dumps({"ok": True, "action": "shutdown"}))
                threading.Thread(
                    target=lambda: os.system("sudo shutdown -h now"), daemon=True
                ).start()
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def log_message(self, *a):
            pass  # keep the console clean

    return H


def start(cfg, state: CompanionState):
    """Start the companion server in a daemon thread. Returns the server or None."""
    cc = getattr(cfg, "companion", {}) or {}
    if not cc.get("enable"):
        return None
    token = str(cc.get("token", ""))
    html = WATCH_HTML.replace("__TOKEN__", token)
    handler = _make_handler(state, token, html)
    try:
        srv = ThreadingHTTPServer((cc.get("bind", "0.0.0.0"), int(cc.get("port", 8088))), handler)
    except Exception as e:
        print(f"[companion] could not bind: {e}")
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[companion] listening on {cc.get('bind','0.0.0.0')}:{cc.get('port',8088)}")
    return srv

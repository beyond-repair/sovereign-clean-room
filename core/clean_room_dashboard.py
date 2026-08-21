#!/usr/bin/env python3
"""
Local Loopback Web Dashboard & Telemetry Inspector

- stdlib HTTP only (http.server)
- Binds exclusively to 127.0.0.1 (never 0.0.0.0)
- Serves JSON telemetry + minimal HTML UI
- network_access: false / air-gapped presentation layer
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

LOOPBACK = "127.0.0.1"


def collect_telemetry(workspace: Path) -> Dict[str, Any]:
    """Assemble offline workspace snapshot for the dashboard."""
    from clean_room_vsa import CleanRoomVSAEngine
    from clean_room_ledger import CleanRoomLedger, CheckpointStore

    ws = Path(workspace)
    out: Dict[str, Any] = {
        "workspace": str(ws.resolve()),
        "network_access": False,
        "bind_policy": "127.0.0.1-only",
    }

    twin = ws / "twin_state"
    eng = CleanRoomVSAEngine(dim=8192)
    if twin.is_dir():
        try:
            eng.load(twin)
            out["engine"] = {
                "loaded": True,
                "jump_start_ok": eng.verify_jump_start_integrity(),
                "codebook": eng.codebook_stats(),
                "min_invertibility": eng.min_invertibility,
                "dim": eng.dim,
            }
        except Exception as e:
            out["engine"] = {"loaded": False, "error": str(e)}
    else:
        out["engine"] = {"loaded": False, "error": "no twin_state"}

    audit = ws / "audit"
    if audit.is_dir():
        led = CleanRoomLedger(audit)
        chain = led.verify_chain()
        out["ledger"] = {
            **chain,
            "seq": led.seq,
            "tip_hash": led.tip_hash,
        }
    else:
        out["ledger"] = {"ok": True, "entries": 0, "tip_hash": None}

    ckpt_dir = ws / "checkpoints"
    checkpoints = []
    if ckpt_dir.is_dir():
        store = CheckpointStore(ckpt_dir)
        for p in sorted(ckpt_dir.glob("ckpt_*.json")):
            pid = p.stem.replace("ckpt_", "", 1)
            try:
                ck = store.load(pid, verify=True)
                checkpoints.append(
                    {
                        "pipeline_id": ck.pipeline_id,
                        "status": ck.status,
                        "next_index": ck.next_index,
                        "valid": True,
                        "ledger_tip": ck.ledger_tip,
                    }
                )
            except Exception as e:
                checkpoints.append(
                    {"pipeline_id": pid, "valid": False, "error": str(e)}
                )
    out["checkpoints"] = checkpoints

    mem_manifest = ws / "memory" / "manifest.json"
    if mem_manifest.is_file():
        man = json.loads(mem_manifest.read_text(encoding="utf-8"))
        out["memory"] = {
            "episodes": len(man.get("episodes") or {}),
            "bundles": len(man.get("bundles") or {}),
            "tau": man.get("tau", 0.92),
            "recent": list(man.get("episodes", {}).keys())[-8:],
        }
    else:
        out["memory"] = {"episodes": 0, "bundles": 0, "tau": 0.92, "recent": []}

    keys_dir = ws / "keys"
    pubs = list(keys_dir.glob("*.pub")) if keys_dir.is_dir() else []
    out["trust"] = {
        "verify_key_count": len(pubs),
        "keys": [p.name for p in pubs],
    }

    # SHACL constitutional shape inventory (static)
    try:
        from clean_room_shacl import CONSTITUTIONAL_SHAPES

        out["shacl"] = {
            "shape_ids": [s.get("id") for s in CONSTITUTIONAL_SHAPES.get("shapes", [])],
            "source": "constitutional",
        }
    except Exception as e:
        out["shacl"] = {"error": str(e)}

    return out


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SEEM Sovereign Dashboard</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#e6edf3; --muted:#8b949e;
          --ok:#3fb950; --bad:#f85149; --acc:#58a6ff; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background:var(--bg); color:var(--text); }
  header { padding:1rem 1.5rem; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
  h1 { font-size:1.1rem; margin:0; letter-spacing:.04em; }
  .badge { font-size:.75rem; padding:.2rem .5rem; border-radius:999px; background:#21262d; color:var(--muted); }
  .badge.ok { color:var(--ok); border:1px solid var(--ok); }
  main { padding:1rem 1.5rem; display:grid; gap:1rem; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:1rem; }
  .card h2 { margin:0 0 .75rem; font-size:.95rem; color:var(--acc); }
  .row { display:flex; justify-content:space-between; gap:.5rem; margin:.35rem 0; font-size:.85rem; }
  .muted { color:var(--muted); }
  .ok { color:var(--ok); } .bad { color:var(--bad); }
  code { font-size:.75rem; word-break:break-all; }
  ul { margin:.25rem 0 0 1rem; padding:0; font-size:.8rem; color:var(--muted); }
  footer { padding:1rem 1.5rem; color:var(--muted); font-size:.75rem; border-top:1px solid var(--border); }
</style>
</head>
<body>
<header>
  <h1>SEEM Sovereign Dashboard</h1>
  <span class="badge ok" id="net">network_access: false · 127.0.0.1</span>
</header>
<main id="root"><div class="card muted">Loading telemetry…</div></main>
<footer>Air-gapped local inspector · refresh every 5s · no external assets</footer>
<script>
async function load() {
  const r = await fetch('/api/telemetry');
  const t = await r.json();
  const el = document.getElementById('root');
  const eng = t.engine || {};
  const led = t.ledger || {};
  const mem = t.memory || {};
  const trust = t.trust || {};
  const shacl = t.shacl || {};
  const ckpts = t.checkpoints || [];
  function yn(v){ return v ? '<span class="ok">yes</span>' : '<span class="bad">no</span>'; }
  el.innerHTML = `
  <div class="card">
    <h2>FHRR Core</h2>
    <div class="row"><span class="muted">loaded</span>${yn(eng.loaded)}</div>
    <div class="row"><span class="muted">jump_start_ok</span>${yn(eng.jump_start_ok)}</div>
    <div class="row"><span class="muted">dim</span><span>${eng.dim||'—'}</span></div>
    <div class="row"><span class="muted">codebook size</span><span>${(eng.codebook&&eng.codebook.size)||'—'}</span></div>
    <div class="row"><span class="muted">min_invertibility</span><span>${eng.min_invertibility||'—'}</span></div>
  </div>
  <div class="card">
    <h2>Audit Ledger</h2>
    <div class="row"><span class="muted">chain ok</span>${yn(led.ok)}</div>
    <div class="row"><span class="muted">entries</span><span>${led.entries??0}</span></div>
    <div class="row"><span class="muted">tip</span><code>${(led.tip_hash||'—').slice(0,16)}…</code></div>
    ${led.error?`<div class="bad">${led.error}</div>`:''}
  </div>
  <div class="card">
    <h2>Checkpoints / Daemon</h2>
    <div class="row"><span class="muted">count</span><span>${ckpts.length}</span></div>
    <ul>${ckpts.map(c=>`<li>${c.pipeline_id}: ${c.valid===false?'INVALID '+c.error:(c.status+' @'+c.next_index)}</li>`).join('')||'<li class="muted">none</li>'}</ul>
  </div>
  <div class="card">
    <h2>Episodic Memory</h2>
    <div class="row"><span class="muted">episodes</span><span>${mem.episodes||0}</span></div>
    <div class="row"><span class="muted">bundles</span><span>${mem.bundles||0}</span></div>
    <div class="row"><span class="muted">τ</span><span>${mem.tau||0.92}</span></div>
    <ul>${(mem.recent||[]).map(id=>`<li>${id}</li>`).join('')||'<li class="muted">empty</li>'}</ul>
  </div>
  <div class="card">
    <h2>SHACL / Trust</h2>
    <div class="row"><span class="muted">shapes</span><span>${(shacl.shape_ids||[]).length}</span></div>
    <ul>${(shacl.shape_ids||[]).map(s=>`<li>${s}</li>`).join('')}</ul>
    <div class="row"><span class="muted">verify keys</span><span>${trust.verify_key_count||0}</span></div>
    <ul>${(trust.keys||[]).map(k=>`<li>${k}</li>`).join('')||'<li class="muted">none</li>'}</ul>
  </div>
  <div class="card">
    <h2>Workspace</h2>
    <div class="row"><code>${t.workspace||''}</code></div>
    <div class="row"><span class="muted">policy</span><span>${t.bind_policy}</span></div>
  </div>`;
}
load(); setInterval(load, 5000);
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    workspace: Path = Path(".")

    def log_message(self, fmt: str, *args: Any) -> None:
        # quiet default logging; still local-only
        pass

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Network-Access", "false")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ("/", "/index.html", "/dashboard"):
            body = DASHBOARD_HTML.encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
            return

        if path == "/api/telemetry":
            try:
                data = collect_telemetry(self.workspace)
                body = json.dumps(data).encode("utf-8")
                self._send(200, body, "application/json")
            except Exception as e:
                body = json.dumps({"error": str(e), "network_access": False}).encode("utf-8")
                self._send(500, body, "application/json")
            return

        if path == "/api/health":
            body = json.dumps(
                {"status": "ok", "bind": LOOPBACK, "network_access": False}
            ).encode("utf-8")
            self._send(200, body, "application/json")
            return

        self._send(404, b'{"error":"not found"}', "application/json")


def make_handler(workspace: Path):
    class BoundHandler(DashboardHandler):
        pass

    BoundHandler.workspace = Path(workspace)
    return BoundHandler


class LoopbackDashboard:
    """HTTP server forced to 127.0.0.1."""

    def __init__(self, workspace: Path, host: str = LOOPBACK, port: int = 8765):
        if host not in (LOOPBACK, "localhost"):
            raise PermissionError(
                f"dashboard host must be loopback ({LOOPBACK}), got {host!r}"
            )
        self.workspace = Path(workspace)
        self.host = LOOPBACK  # normalize localhost → 127.0.0.1
        self.port = int(port)
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, blocking: bool = True) -> Tuple[str, int]:
        handler = make_handler(self.workspace)
        self._httpd = HTTPServer((self.host, self.port), handler)
        # Defense: refuse if server somehow bound elsewhere
        bound_host = self._httpd.server_address[0]
        if bound_host not in (LOOPBACK, "localhost", "::1"):
            self._httpd.server_close()
            raise PermissionError(f"refusing non-loopback bind: {bound_host}")

        if blocking:
            print(
                f"[+] Dashboard on http://{self.host}:{self.port}/ "
                f"(workspace={self.workspace}) network_access=false"
            )
            self._httpd.serve_forever()
        else:
            self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
            self._thread.start()
        return self.host, self.port

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


def run_dashboard(workspace: Path, host: str = LOOPBACK, port: int = 8765) -> None:
    LoopbackDashboard(workspace, host=host, port=port).start(blocking=True)

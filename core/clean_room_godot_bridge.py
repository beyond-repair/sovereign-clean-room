#!/usr/bin/env python3
"""
CleanRoomGodotBridge — Project Cold Boot IPC

Air-gapped channel between Godot 4.x / C++ graph engine and the
Sovereign Clean-Room stack.

Transport: Unix domain socket only (filesystem path under workspace).
No TCP, no UDP, no external hosts. network_access: false.

Wire protocol: newline-delimited JSON (NDJSON).
Request:  {"id": "...", "op": "<op>", ...}
Response: {"id": "...", "ok": true|false, ...}
"""

from __future__ import annotations

import json
import os
import socket
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate
from clean_room_memory import EpisodicMemoryStore
from clean_room_ledger import CleanRoomLedger
from clean_room_shacl import ConstitutionalValidator, ShapeEngine, LocalGraph

OPS = frozenset(
    {
        "ping",
        "telemetry",
        "memory_recall",
        "memory_remember",
        "shacl_check",
        "skill_run",
        "ledger_append",
        "ledger_verify",
        "vsa_similarity",
    }
)


@dataclass
class BridgeConfig:
    workspace: Path
    socket_path: Path
    dim: int = 8192
    require_skill_signature: bool = True
    trusted_verify_keys: Optional[List[str]] = None


class CleanRoomGodotBridge:
    """
    Unix-socket server exposing offline VSA / memory / SHACL / skills to Godot.
    """

    def __init__(self, config: BridgeConfig):
        if config.dim != 8192:
            raise ValueError("Bridge requires dim=8192")
        self.config = config
        self.workspace = Path(config.workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.socket_path = Path(config.socket_path)

        # Ensure socket lives under workspace (path isolation)
        try:
            self.socket_path.resolve().relative_to(self.workspace.resolve())
        except ValueError as e:
            raise PermissionError(
                f"socket path must be under workspace: {self.socket_path}"
            ) from e

        self.engine = CleanRoomVSAEngine(dim=8192)
        twin = self.workspace / "twin_state"
        if twin.is_dir():
            try:
                self.engine.load(twin)
            except Exception:
                self.engine.jump_start_v01()
        if not self.engine.verify_jump_start_integrity():
            self.engine.jump_start_v01()

        self.memory = EpisodicMemoryStore(
            self.workspace / "memory", engine=self.engine, tau=0.92
        )
        self.ledger = CleanRoomLedger(self.workspace / "audit")
        self.shacl = ConstitutionalValidator(engine=self.engine)
        self.gate = CleanRoomGate(
            self.engine,
            trusted_verify_keys=list(config.trusted_verify_keys or []),
            require_skill_signature=config.require_skill_signature,
            enable_shacl=True,
        )

        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def handle(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        req_id = msg.get("id", "")
        op = str(msg.get("op", ""))
        if op not in OPS:
            return {"id": req_id, "ok": False, "error": f"unknown op: {op}"}

        try:
            if op == "ping":
                return {
                    "id": req_id,
                    "ok": True,
                    "pong": True,
                    "dim": 8192,
                    "network_access": False,
                    "transport": "unix_socket",
                }

            if op == "telemetry":
                chain = self.ledger.verify_chain()
                return {
                    "id": req_id,
                    "ok": True,
                    "engine": {
                        "jump_start_ok": self.engine.verify_jump_start_integrity(),
                        "codebook": self.engine.codebook_stats(),
                    },
                    "ledger": chain,
                    "memory": self.memory.stats(),
                    "network_access": False,
                }

            if op == "memory_recall":
                query = str(msg.get("query", ""))
                top_k = int(msg.get("top_k", 5))
                hits = self.memory.recall(query, top_k=top_k)
                return {
                    "id": req_id,
                    "ok": True,
                    "hits": [
                        {
                            "episode_id": h.episode_id,
                            "similarity": h.similarity,
                            "meta": h.meta,
                        }
                        for h in hits
                    ],
                }

            if op == "memory_remember":
                content = str(msg.get("content", ""))
                meta = msg.get("meta") if isinstance(msg.get("meta"), dict) else {}
                # Game telemetry tag
                meta = {**meta, "source": meta.get("source", "godot_cold_boot")}
                eid = self.memory.remember(content, meta=meta)
                self.ledger.append(
                    "godot_memory",
                    {"episode_id": eid, "preview": content[:120]},
                )
                return {"id": req_id, "ok": True, "episode_id": eid}

            if op == "shacl_check":
                data = msg.get("data") or {}
                if not isinstance(data, dict):
                    return {"id": req_id, "ok": False, "error": "data must be object"}
                # Skill package shape or generic mapping
                if "sovereignty" in data or "vsa_bindings" in data:
                    report = self.shacl.validate_skill_package(data)
                else:
                    shape_id = msg.get("shape_id")
                    engine = ShapeEngine()
                    # reuse constitutional by default via validator shapes
                    report = self.shacl.shapes.validate_mapping(data, shape_id=shape_id)
                return {
                    "id": req_id,
                    "ok": True,
                    "conforms": report.conforms,
                    "report": report.to_dict(),
                }

            if op == "skill_run":
                package = msg.get("package")
                if not isinstance(package, dict):
                    return {"id": req_id, "ok": False, "error": "package required"}

                def payload():
                    return {
                        "status": "PASS",
                        "echo": msg.get("payload") or {},
                        "source": "godot_bridge",
                    }

                outcome = self.gate.execute_skill_package(package, payload)
                self.ledger.append(
                    "godot_skill",
                    {
                        "skill_id": package.get("manifest", {}).get("skill_id"),
                        "gate_status": outcome.get("status"),
                        "error": outcome.get("error"),
                    },
                )
                return {
                    "id": req_id,
                    "ok": outcome.get("status") == "PASS",
                    "outcome": outcome,
                }

            if op == "ledger_append":
                event = str(msg.get("event_type", "godot_event"))
                payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
                # Never allow network claims
                payload = {**payload, "network_access": False, "source": "godot"}
                entry = self.ledger.append(event, payload)
                return {
                    "id": req_id,
                    "ok": True,
                    "seq": entry.seq,
                    "entry_hash": entry.entry_hash,
                }

            if op == "ledger_verify":
                return {"id": req_id, "ok": True, **self.ledger.verify_chain()}

            if op == "vsa_similarity":
                # Compare two registered atom names if present
                a = str(msg.get("a", ""))
                b = str(msg.get("b", ""))
                if a not in self.engine.codebook or b not in self.engine.codebook:
                    return {
                        "id": req_id,
                        "ok": False,
                        "error": "atom not in codebook",
                    }
                sim = self.engine.similarity(
                    self.engine.codebook[a], self.engine.codebook[b]
                )
                return {"id": req_id, "ok": True, "similarity": sim}

        except Exception as e:
            return {"id": req_id, "ok": False, "error": f"{type(e).__name__}: {e}"}

        return {"id": req_id, "ok": False, "error": "unhandled"}

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def _client_loop(self, conn: socket.socket) -> None:
        buf = b""
        with conn:
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        if not isinstance(msg, dict):
                            resp = {"ok": False, "error": "message must be object"}
                        else:
                            resp = self.handle(msg)
                    except json.JSONDecodeError as e:
                        resp = {"ok": False, "error": f"json: {e}"}
                    conn.sendall((json.dumps(resp, sort_keys=True) + "\n").encode("utf-8"))

    def start(self, blocking: bool = True) -> Path:
        if self.socket_path.exists():
            self.socket_path.unlink()
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self.socket_path))
        self._server.listen(8)
        self._server.settimeout(1.0)
        self._stop.clear()

        def serve() -> None:
            assert self._server is not None
            while not self._stop.is_set():
                try:
                    conn, _ = self._server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                t = threading.Thread(target=self._client_loop, args=(conn,), daemon=True)
                t.start()

        if blocking:
            print(
                f"[+] CleanRoomGodotBridge listening on unix://{self.socket_path} "
                f"(network_access=false)"
            )
            serve()
        else:
            self._thread = threading.Thread(target=serve, daemon=True)
            self._thread.start()
        return self.socket_path

    def stop(self) -> None:
        self._stop.set()
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass


class BridgeClient:
    """Python test / tooling client for the Unix socket bridge."""

    def __init__(self, socket_path: Union[str, Path]):
        self.socket_path = Path(socket_path)

    def request(self, op: str, **kwargs: Any) -> Dict[str, Any]:
        msg = {"id": kwargs.pop("id", op), "op": op, **kwargs}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10.0)
            s.connect(str(self.socket_path))
            s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
            line = buf.split(b"\n", 1)[0]
            return json.loads(line.decode("utf-8"))


def default_socket_path(workspace: Path) -> Path:
    return Path(workspace) / "ipc" / "cold_boot.sock"

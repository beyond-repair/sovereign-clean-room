#!/usr/bin/env python3
"""
Sovereign Audit Ledger & Pipeline Checkpointing (offline).

- Append-only JSONL ledger with SHA-256 hash chain
- Records orchestrator steps, signature verification outcomes, telemetry
- Checkpoint snapshots for CleanRoomOrchestrator resume (local disk only)
- network_access: never used
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union


GENESIS_HASH = "0" * 64


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entry_hash(prev_hash: str, body: Dict[str, Any]) -> str:
    """H = SHA256(prev_hash || canonical(body_without_entry_hash))."""
    body = dict(body)
    body.pop("entry_hash", None)
    return sha256_hex(prev_hash.encode("ascii") + _canonical(body))


@dataclass
class LedgerEntry:
    seq: int
    timestamp: float
    event_type: str
    payload: Dict[str, Any]
    prev_hash: str
    entry_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LedgerEntry":
        return cls(
            seq=int(d["seq"]),
            timestamp=float(d["timestamp"]),
            event_type=str(d["event_type"]),
            payload=dict(d.get("payload") or {}),
            prev_hash=str(d["prev_hash"]),
            entry_hash=str(d["entry_hash"]),
        )


class CleanRoomLedger:
    """
    Append-only, hash-chained audit log.

    Storage: directory with
      - ledger.jsonl   (one entry per line)
      - tip.json       (last seq + tip hash)
    """

    def __init__(self, directory: Union[str, Path]):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.directory / "ledger.jsonl"
        self.tip_path = self.directory / "tip.json"
        self._seq = 0
        self._tip = GENESIS_HASH
        if self.tip_path.is_file():
            tip = json.loads(self.tip_path.read_text(encoding="utf-8"))
            self._seq = int(tip.get("seq", 0))
            self._tip = str(tip.get("tip_hash", GENESIS_HASH))

    @property
    def tip_hash(self) -> str:
        return self._tip

    @property
    def seq(self) -> int:
        return self._seq

    def append(self, event_type: str, payload: Dict[str, Any]) -> LedgerEntry:
        """Append a chained entry. Returns the sealed entry."""
        body = {
            "seq": self._seq + 1,
            "timestamp": time.time(),
            "event_type": event_type,
            "payload": payload,
            "prev_hash": self._tip,
        }
        h = entry_hash(self._tip, body)
        body["entry_hash"] = h
        entry = LedgerEntry.from_dict(body)

        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")

        self._seq = entry.seq
        self._tip = entry.entry_hash
        self.tip_path.write_text(
            json.dumps({"seq": self._seq, "tip_hash": self._tip}, indent=2),
            encoding="utf-8",
        )
        return entry

    def iter_entries(self) -> Iterator[LedgerEntry]:
        if not self.ledger_path.is_file():
            return
            yield  # pragma: no cover
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield LedgerEntry.from_dict(json.loads(line))

    def verify_chain(self) -> Dict[str, Any]:
        """
        Walk the full chain. Returns {ok, entries, tip_hash, error}.
        Detects broken links and body tampering.
        """
        prev = GENESIS_HASH
        count = 0
        last_hash = GENESIS_HASH
        for entry in self.iter_entries():
            count += 1
            if entry.prev_hash != prev:
                return {
                    "ok": False,
                    "entries": count,
                    "tip_hash": last_hash,
                    "error": f"prev_hash mismatch at seq={entry.seq}",
                }
            expected = entry_hash(entry.prev_hash, entry.to_dict())
            if entry.entry_hash != expected:
                return {
                    "ok": False,
                    "entries": count,
                    "tip_hash": last_hash,
                    "error": f"entry_hash mismatch at seq={entry.seq}",
                }
            if entry.seq != count:
                return {
                    "ok": False,
                    "entries": count,
                    "tip_hash": last_hash,
                    "error": f"seq discontinuity at seq={entry.seq} expected={count}",
                }
            prev = entry.entry_hash
            last_hash = entry.entry_hash

        if count != self._seq or last_hash != self._tip:
            # tip file may be out of sync with jsonl
            if count > 0 and last_hash != self._tip:
                return {
                    "ok": False,
                    "entries": count,
                    "tip_hash": last_hash,
                    "error": "tip.json does not match ledger tip",
                }

        return {"ok": True, "entries": count, "tip_hash": last_hash, "error": None}

    # ------------------------------------------------------------------
    # Orchestrator-facing helpers
    # ------------------------------------------------------------------

    def record_pipeline_start(
        self,
        pipeline_id: str,
        step_count: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> LedgerEntry:
        return self.append(
            "pipeline_start",
            {
                "pipeline_id": pipeline_id,
                "step_count": step_count,
                "meta": meta or {},
            },
        )

    def record_step(
        self,
        pipeline_id: str,
        index: int,
        skill_id: str,
        gate_status: str,
        signature_ok: bool,
        error: Optional[str] = None,
        output_summary: Optional[Dict[str, Any]] = None,
        telemetry_snapshot: Optional[Dict[str, Any]] = None,
    ) -> LedgerEntry:
        return self.append(
            "pipeline_step",
            {
                "pipeline_id": pipeline_id,
                "index": index,
                "skill_id": skill_id,
                "gate_status": gate_status,
                "signature_ok": signature_ok,
                "error": error,
                "output_summary": output_summary or {},
                "telemetry_snapshot": telemetry_snapshot or {},
            },
        )

    def record_pipeline_end(
        self,
        pipeline_id: str,
        status: str,
        aborted_at: Optional[int] = None,
        error: Optional[str] = None,
    ) -> LedgerEntry:
        return self.append(
            "pipeline_end",
            {
                "pipeline_id": pipeline_id,
                "status": status,
                "aborted_at": aborted_at,
                "error": error,
            },
        )


@dataclass
class PipelineCheckpoint:
    """Serializable orchestrator resume state (no network)."""

    pipeline_id: str
    next_index: int
    status: str
    state: Dict[str, Any]
    completed_steps: List[Dict[str, Any]] = field(default_factory=list)
    ledger_tip: Optional[str] = None
    engine_state_dir: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "next_index": self.next_index,
            "status": self.status,
            "state": self.state,
            "completed_steps": self.completed_steps,
            "ledger_tip": self.ledger_tip,
            "engine_state_dir": self.engine_state_dir,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineCheckpoint":
        return cls(
            pipeline_id=str(d["pipeline_id"]),
            next_index=int(d["next_index"]),
            status=str(d["status"]),
            state=dict(d.get("state") or {}),
            completed_steps=list(d.get("completed_steps") or []),
            ledger_tip=d.get("ledger_tip"),
            engine_state_dir=d.get("engine_state_dir"),
            created_at=float(d.get("created_at", time.time())),
        )


class CheckpointStore:
    """Local snapshot / restore for pipeline + optional engine directory path."""

    def __init__(self, directory: Union[str, Path]):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, pipeline_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in pipeline_id)
        return self.directory / f"ckpt_{safe}.json"

    def save(self, checkpoint: PipelineCheckpoint) -> Path:
        path = self._path(checkpoint.pipeline_id)
        body = checkpoint.to_dict()
        body["checkpoint_hash"] = sha256_hex(_canonical(body))
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        return path

    def load(self, pipeline_id: str, verify: bool = True) -> PipelineCheckpoint:
        path = self._path(pipeline_id)
        if not path.is_file():
            raise FileNotFoundError(f"checkpoint not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        stored_hash = raw.pop("checkpoint_hash", None)
        if verify:
            if not stored_hash:
                raise ValueError("checkpoint missing checkpoint_hash")
            calc = sha256_hex(_canonical(raw))
            if calc != stored_hash:
                raise ValueError("checkpoint integrity failure: hash mismatch")
        return PipelineCheckpoint.from_dict(raw)

    def exists(self, pipeline_id: str) -> bool:
        return self._path(pipeline_id).is_file()

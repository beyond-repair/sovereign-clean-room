#!/usr/bin/env python3
"""
Immutable TaskAtom / Episode layer for Sovereign Clean-Room.

# Extracted 2026-08-24
# Source: beyond-repair/My-mind-A.I.
# Files: task_class.py, taskqueue_class.py, delegate_class.py, orchestrate_agent_tasks.py
# Pattern: task queue + delegation → append-only atomic events (no mutable status flips)

Also draws atomic work-unit / hand-off concepts from Auto_Legion (conceptual only).

Rules enforced:
- offline-first, pure Python
- immutable atoms, append-only ledger
- deterministic SHA-256 integrity
- no LLM / HTTP / GitHub runtime dependency
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union

# Re-use existing clean-room ledger primitives when available
try:
    from clean_room_ledger import CleanRoomLedger, GENESIS_HASH, entry_hash, sha256_hex, _canonical
except ImportError:  # pragma: no cover — allow standalone import during tests
    GENESIS_HASH = "0" * 64

    def _canonical(obj: Any) -> bytes:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    def sha256_hex(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def entry_hash(prev_hash: str, body: Dict[str, Any]) -> str:
        body = dict(body)
        body.pop("entry_hash", None)
        return sha256_hex(prev_hash.encode("ascii") + _canonical(body))

    class CleanRoomLedger:  # minimal stub
        def __init__(self, directory: Union[str, Path]):
            self.directory = Path(directory)
            self.directory.mkdir(parents=True, exist_ok=True)
            self._seq = 0
            self._tip = GENESIS_HASH

        def append(self, event_type: str, payload: Dict[str, Any]):
            raise NotImplementedError("CleanRoomLedger required for production")


# ---------------------------------------------------------------------------
# TaskAtom — immutable unit of work / event
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskAtom:
    """
    Immutable, hash-sealed event.

    Extracted pattern from My-mind Task + TaskQueue, rewritten as append-only
    atoms instead of mutable objects with status flips.
    """

    atom_id: str
    task_id: str
    event_type: str  # e.g. created | assigned | completed | failed | transition
    payload: Dict[str, Any]
    timestamp: float
    prev_atom_hash: str = GENESIS_HASH
    atom_hash: str = ""

    def __post_init__(self) -> None:
        # frozen=True prevents assignment; compute hash via object.__setattr__
        if not self.atom_hash:
            body = {
                "atom_id": self.atom_id,
                "task_id": self.task_id,
                "event_type": self.event_type,
                "payload": self.payload,
                "timestamp": self.timestamp,
                "prev_atom_hash": self.prev_atom_hash,
            }
            h = sha256_hex(_canonical(body))
            object.__setattr__(self, "atom_hash", h)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
            "prev_atom_hash": self.prev_atom_hash,
            "atom_hash": self.atom_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskAtom":
        atom = cls(
            atom_id=str(d["atom_id"]),
            task_id=str(d["task_id"]),
            event_type=str(d["event_type"]),
            payload=dict(d.get("payload") or {}),
            timestamp=float(d["timestamp"]),
            prev_atom_hash=str(d.get("prev_atom_hash", GENESIS_HASH)),
            atom_hash=str(d.get("atom_hash", "")),
        )
        # verify integrity if hash was supplied
        expected = cls(
            atom_id=atom.atom_id,
            task_id=atom.task_id,
            event_type=atom.event_type,
            payload=atom.payload,
            timestamp=atom.timestamp,
            prev_atom_hash=atom.prev_atom_hash,
        ).atom_hash
        if atom.atom_hash and atom.atom_hash != expected:
            raise ValueError(f"TaskAtom integrity failure: {atom.atom_id}")
        return atom

    @classmethod
    def create(
        cls,
        task_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        prev_atom_hash: str = GENESIS_HASH,
        timestamp: Optional[float] = None,
    ) -> "TaskAtom":
        return cls(
            atom_id=uuid.uuid4().hex[:16],
            task_id=task_id,
            event_type=event_type,
            payload=dict(payload or {}),
            timestamp=float(timestamp if timestamp is not None else time.time()),
            prev_atom_hash=prev_atom_hash,
        )


# ---------------------------------------------------------------------------
# Episode — reconstructed purely from TaskAtoms (no mutable state)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Episode:
    """
    Reconstructed view of a task lifecycle from an ordered atom sequence.
    Never mutated in place; rebuild from atoms.
    """

    task_id: str
    atoms: tuple  # Tuple[TaskAtom, ...]
    title: str = ""
    description: str = ""
    terminal_status: str = "open"  # open | completed | failed

    @classmethod
    def from_atoms(cls, task_id: str, atoms: Sequence[TaskAtom]) -> "Episode":
        ordered = tuple(sorted(atoms, key=lambda a: (a.timestamp, a.atom_id)))
        title = ""
        description = ""
        status = "open"
        for a in ordered:
            if a.event_type == "created":
                title = str(a.payload.get("title", title))
                description = str(a.payload.get("description", description))
            elif a.event_type == "completed":
                status = "completed"
            elif a.event_type == "failed":
                status = "failed"
        return cls(
            task_id=task_id,
            atoms=ordered,
            title=title,
            description=description,
            terminal_status=status,
        )

    def content_summary(self) -> str:
        """Deterministic text summary for FHRR encoding / MemSkill promotion."""
        parts = [f"task_id={self.task_id}", f"status={self.terminal_status}"]
        if self.title:
            parts.append(f"title={self.title}")
        if self.description:
            parts.append(f"description={self.description}")
        for a in self.atoms:
            parts.append(f"{a.event_type}:{json.dumps(a.payload, sort_keys=True)}")
        return "|".join(parts)


# ---------------------------------------------------------------------------
# EpisodicMemoryLedger — append-only atom store (bridges CleanRoomLedger)
# ---------------------------------------------------------------------------

class EpisodicMemoryLedger:
    """
    Append-only TaskAtom ledger.

    Storage layout (under root):
      atoms.jsonl          — one TaskAtom per line
      tip.json             — last atom_hash + count
      optional CleanRoomLedger integration for dual audit
    """

    def __init__(self, root: Union[str, Path], audit_ledger: Optional[Any] = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.atoms_path = self.root / "atoms.jsonl"
        self.tip_path = self.root / "tip.json"
        self.audit = audit_ledger  # optional CleanRoomLedger
        self._tip = GENESIS_HASH
        self._count = 0
        if self.tip_path.is_file():
            tip = json.loads(self.tip_path.read_text(encoding="utf-8"))
            self._tip = str(tip.get("tip_hash", GENESIS_HASH))
            self._count = int(tip.get("count", 0))

    @property
    def tip_hash(self) -> str:
        return self._tip

    @property
    def count(self) -> int:
        return self._count

    def append(self, atom: TaskAtom) -> TaskAtom:
        """Append a sealed atom. Rejects if prev_atom_hash does not match tip."""
        if atom.prev_atom_hash != self._tip:
            raise ValueError(
                f"prev_atom_hash mismatch: got {atom.prev_atom_hash[:12]}… "
                f"expected tip {self._tip[:12]}…"
            )
        # re-seal to guarantee hash matches current chain tip
        sealed = TaskAtom(
            atom_id=atom.atom_id,
            task_id=atom.task_id,
            event_type=atom.event_type,
            payload=dict(atom.payload),
            timestamp=atom.timestamp,
            prev_atom_hash=self._tip,
        )
        with open(self.atoms_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sealed.to_dict(), sort_keys=True) + "\n")
        self._tip = sealed.atom_hash
        self._count += 1
        self.tip_path.write_text(
            json.dumps({"tip_hash": self._tip, "count": self._count}, indent=2),
            encoding="utf-8",
        )
        if self.audit is not None:
            try:
                self.audit.append(
                    "task_atom",
                    {"atom_id": sealed.atom_id, "task_id": sealed.task_id, "event_type": sealed.event_type},
                )
            except Exception:
                pass  # audit is best-effort; atom store is authoritative
        return sealed

    def create_and_append(
        self,
        task_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> TaskAtom:
        atom = TaskAtom.create(
            task_id=task_id,
            event_type=event_type,
            payload=payload,
            prev_atom_hash=self._tip,
        )
        return self.append(atom)

    def iter_atoms(self) -> Iterator[TaskAtom]:
        if not self.atoms_path.is_file():
            return
            yield  # pragma: no cover
        with open(self.atoms_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield TaskAtom.from_dict(json.loads(line))

    def atoms_for_task(self, task_id: str) -> List[TaskAtom]:
        return [a for a in self.iter_atoms() if a.task_id == task_id]

    def reconstruct_episode(self, task_id: str) -> Episode:
        atoms = self.atoms_for_task(task_id)
        if not atoms:
            raise KeyError(f"no atoms for task_id={task_id}")
        return Episode.from_atoms(task_id, atoms)

    def verify_chain(self) -> Dict[str, Any]:
        prev = GENESIS_HASH
        count = 0
        last = GENESIS_HASH
        for atom in self.iter_atoms():
            count += 1
            if atom.prev_atom_hash != prev:
                return {"ok": False, "count": count, "error": f"prev mismatch at {atom.atom_id}"}
            expected = TaskAtom(
                atom_id=atom.atom_id,
                task_id=atom.task_id,
                event_type=atom.event_type,
                payload=atom.payload,
                timestamp=atom.timestamp,
                prev_atom_hash=atom.prev_atom_hash,
            ).atom_hash
            if atom.atom_hash != expected:
                return {"ok": False, "count": count, "error": f"hash mismatch at {atom.atom_id}"}
            prev = atom.atom_hash
            last = atom.atom_hash
        if count != self._count or (count > 0 and last != self._tip):
            return {"ok": False, "count": count, "error": "tip out of sync"}
        return {"ok": True, "count": count, "tip_hash": last, "error": None}

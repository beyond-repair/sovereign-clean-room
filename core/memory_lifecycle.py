#!/usr/bin/env python3
"""Append-only memory lifecycle.

Evidence and inference are different record kinds. Supersession does not
delete history. Corruption is a hash mismatch. Replay walks the log.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def _canon(obj: Dict[str, Any]) -> bytes:
    body = dict(obj)
    body.pop("hash", None)
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _hash(obj: Dict[str, Any]) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


class MemoryIntegrityError(ValueError):
    pass


class LifecycleMemory:
    def __init__(self) -> None:
        self.log: List[Dict[str, Any]] = []
        self._seq = 0

    def _append(self, kind: str, record_class: str, payload: Dict[str, Any], provenance: Dict[str, Any]) -> Dict[str, Any]:
        if record_class not in ("evidence", "inference"):
            raise ValueError("record_class must be evidence or inference")
        self._seq += 1
        body = {
            "seq": self._seq,
            "kind": kind,
            "record_class": record_class,
            "payload": payload,
            "provenance": provenance,
            "prev_hash": self.log[-1]["hash"] if self.log else "0" * 64,
        }
        body["hash"] = _hash(body)
        self.log.append(body)
        return body

    def store(self, key: str, value: Any, record_class: str, provenance: Dict[str, Any], status: str = "current") -> Dict[str, Any]:
        return self._append("store", record_class, {"key": key, "value": value, "status": status}, provenance)

    def reinforce(self, key: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
        current = self.current(key)
        if current is None:
            raise KeyError(key)
        return self._append(
            "reinforce",
            current["record_class"],
            {"key": key, "value": current["payload"]["value"], "status": "current", "reinforced_from": current["seq"]},
            provenance,
        )

    def contradict(self, key: str, value: Any, record_class: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
        return self._append(
            "contradict",
            record_class,
            {"key": key, "value": value, "status": "conflict"},
            provenance,
        )

    def supersede(self, key: str, value: Any, record_class: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
        return self._append(
            "supersede",
            record_class,
            {"key": key, "value": value, "status": "current"},
            provenance,
        )

    def invalidate(self, key: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
        return self._append(
            "invalidate",
            "evidence",
            {"key": key, "value": None, "status": "invalid"},
            provenance,
        )

    def current(self, key: str) -> Optional[Dict[str, Any]]:
        found = None
        for rec in self.log:
            if rec["payload"].get("key") != key:
                continue
            if rec["kind"] == "contradict":
                continue
            found = rec
        if found is None:
            return None
        if found["payload"].get("status") in ("invalid",):
            return None
        if found["kind"] == "supersede" or found["payload"].get("status") == "current":
            # A later supersede replaces currency, but older rows remain in log.
            return found
        return found

    def history(self, key: str) -> List[Dict[str, Any]]:
        return [rec for rec in self.log if rec["payload"].get("key") == key]

    def conflicts(self, key: str) -> List[Dict[str, Any]]:
        return [rec for rec in self.history(key) if rec["kind"] == "contradict"]

    def recover_failed(self, key: str) -> List[Dict[str, Any]]:
        """Failed strategies stay addressable. Superseded is not current."""
        return [
            rec for rec in self.history(key)
            if rec["payload"].get("status") in ("failed", "superseded") or rec["kind"] == "store"
        ]

    def replay(self) -> List[Dict[str, Any]]:
        self.verify()
        return list(self.log)

    def verify(self) -> None:
        prev = "0" * 64
        for rec in self.log:
            if rec["prev_hash"] != prev:
                raise MemoryIntegrityError(f"prev_hash break at seq {rec['seq']}")
            expect = _hash(rec)
            if rec["hash"] != expect:
                raise MemoryIntegrityError(f"hash mismatch at seq {rec['seq']}")
            prev = rec["hash"]

    def corrupt(self, seq: int) -> None:
        for rec in self.log:
            if rec["seq"] == seq:
                rec["payload"] = dict(rec["payload"])
                rec["payload"]["value"] = "TAMPERED"
                return
        raise KeyError(seq)

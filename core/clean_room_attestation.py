#!/usr/bin/env python3
"""
Clean-Room → BlockSwarm one-way attestation export (offline).

Builds AttestationBundle v0.1 JSON from ledger-style payloads / physics results.
Does not network, sign on-chain, or claim experimental validation.

See: beyond-repair/BlockSwarm docs/ATTESTATION_BRIDGE.md
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = "beyond-repair.attestation.v0.1"
CLAIM_CLASS = "phenomenological_hypothesis"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _keccak_compat_hex(data: bytes) -> str:
    """
    Application contentCID: SHA-256 of canonical payload bytes, hex-encoded.
    On-chain Solidity uses keccak256; bridge docs allow mapping contentCID as
    bytes32 from this digest truncated/padded — export both forms for clarity.
    """
    return _sha256_hex(data)


@dataclass
class AttestationBundle:
    schema: str = SCHEMA
    source: Dict[str, Any] = field(default_factory=dict)
    ledger: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    merkle: Dict[str, Any] = field(default_factory=dict)
    exported_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "source": self.source,
            "ledger": self.ledger,
            "payload": self.payload,
            "merkle": self.merkle,
            "exported_at": self.exported_at,
        }

    def write_json(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def build_attestation_from_physics(
    physics_result: Dict[str, Any],
    *,
    workspace_id: str = "local",
    ledger_seq: Optional[int] = None,
    entry_hash: str = "",
    prev_hash: str = "",
    event_type: str = "physics_ware_sparc",
    proposal_id: int = 0,
    causal_dag_hash: str = "",
) -> AttestationBundle:
    """
    Map WarePhysicsBridge.evaluate() / PhysicsVerification.to_dict() into bundle.
    Forces hypothesis-grade claim flags regardless of input mutation attempts.
    """
    payload = {
        "input_hash": physics_result.get("input_hash", ""),
        "result_hash": physics_result.get("result_hash", ""),
        "status": physics_result.get("status", "INCONCLUSIVE"),
        "claim_class": CLAIM_CLASS,
        "experimental_validation": False,
        "energy_extraction_validated": False,
        "thrust_validated": False,
        "metrics": physics_result.get("metrics") or {},
        "assumptions": physics_result.get("assumptions") or [],
        "warnings": physics_result.get("warnings") or [],
        "network_access": False,
    }

    content_bytes = _canonical_json(payload).encode("utf-8")
    content_cid_hex = _keccak_compat_hex(content_bytes)

    # Leaf preimage fields as hex strings for JSON; on-chain uses bytes32
    merkle = {
        "leaf_encoding": "knowledgeLeaf",
        "content_cid": content_cid_hex,
        "proposal_id": int(proposal_id),
        "causal_dag_hash": causal_dag_hash or ("0" * 64),
        "leaf": None,  # filled below as sha256 of encoded triple for offline checks
        "root": None,
        "proof": [],
        "note": (
            "On-chain leaf = keccak256(abi.encode(contentCID, proposalId, causalDAGHash)); "
            "content_cid here is SHA-256 hex of canonical payload JSON for offline binding."
        ),
    }
    # Offline leaf commitment (not identical to Solidity keccak unless bridged)
    leaf_material = _canonical_json(
        {
            "content_cid": merkle["content_cid"],
            "proposal_id": merkle["proposal_id"],
            "causal_dag_hash": merkle["causal_dag_hash"],
        }
    ).encode("utf-8")
    merkle["leaf_offline"] = _sha256_hex(leaf_material)

    return AttestationBundle(
        source={
            "system": "sovereign-clean-room",
            "workspace_id": workspace_id,
            "network_access": False,
        },
        ledger={
            "seq": ledger_seq,
            "entry_hash": entry_hash,
            "prev_hash": prev_hash,
            "event_type": event_type,
        },
        payload=payload,
        merkle=merkle,
        exported_at=datetime.now(timezone.utc).isoformat(),
    )


def export_physics_attestation(
    physics_result: Dict[str, Any],
    out_path: Path,
    **kwargs: Any,
) -> AttestationBundle:
    bundle = build_attestation_from_physics(physics_result, **kwargs)
    bundle.write_json(out_path)
    return bundle

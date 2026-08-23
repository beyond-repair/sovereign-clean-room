#!/usr/bin/env python3
"""Offline attestation export tests (no network)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_physics import WarePhysicsBridge, CLAIM_CLASS  # noqa: E402
from clean_room_attestation import (  # noqa: E402
    build_attestation_from_physics,
    export_physics_attestation,
)


def test_claim_flags_forced() -> None:
    result = WarePhysicsBridge().evaluate(galaxy_id="SAMPLE_A", n=3.0)
    # Attempt to poison flags
    poisoned = dict(result)
    poisoned["claim_class"] = "experimentally_confirmed"
    poisoned["experimental_validation"] = True
    poisoned["thrust_validated"] = True

    bundle = build_attestation_from_physics(poisoned, workspace_id="test")
    p = bundle.payload
    assert p["claim_class"] == CLAIM_CLASS
    assert p["experimental_validation"] is False
    assert p["energy_extraction_validated"] is False
    assert p["thrust_validated"] is False
    assert p["network_access"] is False
    assert bundle.source["network_access"] is False
    assert bundle.merkle["leaf_encoding"] == "knowledgeLeaf"
    print("[OK] claim flags forced on export")


def test_write_json_roundtrip() -> None:
    result = WarePhysicsBridge().evaluate(galaxy_id="SAMPLE_B", n=3.0)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "attestation.json"
        bundle = export_physics_attestation(
            result, path, workspace_id="ws1", ledger_seq=1, entry_hash="abc"
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema"] == "beyond-repair.attestation.v0.1"
        assert data["payload"]["result_hash"] == result.get("result_hash")
        assert data["ledger"]["seq"] == 1
        assert bundle.to_dict()["merkle"]["content_cid"]
    print("[OK] attestation JSON roundtrip")


if __name__ == "__main__":
    test_claim_flags_forced()
    test_write_json_roundtrip()
    print("--- ATTESTATION EXPORT TESTS PASSED ---")

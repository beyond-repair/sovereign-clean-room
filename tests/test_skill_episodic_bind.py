#!/usr/bin/env python3
"""Validate episodic_bind package schema fields and secure local execution."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT))

from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate  # noqa: E402
from skills.episodic_bind.skill import (  # noqa: E402
    load_package_manifest,
    validate_sovereignty,
    run_episodic_bind,
    run_via_gate,
)

PKG_PATH = ROOT / "skills" / "episodic_bind" / "package.json"
SCHEMA_REQUIRED = ("manifest", "interface", "sovereignty", "vsa_bindings")


def test_package_json_schema_shape() -> None:
    pkg = json.loads(PKG_PATH.read_text(encoding="utf-8"))
    for key in SCHEMA_REQUIRED:
        assert key in pkg, f"missing {key}"
    assert pkg["manifest"]["skill_id"] == "episodic_bind"
    assert pkg["sovereignty"]["network_access"] is False
    assert pkg["vsa_bindings"]["dimension"] == 8192
    assert pkg["vsa_bindings"]["binding_threshold"] >= 0.92
    assert pkg["vsa_bindings"]["sparsity_k"] == 256
    for atom in (
        "SELF",
        "ENVIRONMENT",
        "EPISODIC",
        "SEMANTIC",
        "SUCCESS",
        "FAILURE",
    ):
        assert atom in pkg["vsa_bindings"]["codebook_atoms"]
    validate_sovereignty(pkg)
    print("[OK] package.json sovereignty + VSA bindings")


def test_rejects_network_flag() -> None:
    pkg = load_package_manifest()
    pkg = json.loads(json.dumps(pkg))
    pkg["sovereignty"]["network_access"] = True
    try:
        validate_sovereignty(pkg)
        raise AssertionError("should have rejected network_access=true")
    except PermissionError:
        print("[OK] network_access=true rejected")


def test_bind_pass_with_jump_start() -> None:
    vsa = CleanRoomVSAEngine(dim=8192)
    vsa.jump_start_v01(seed=0x5345454D)
    result = run_episodic_bind(vsa, note="local-only memory trace")
    assert result["status"] == "PASS", result
    assert result["invertibility"] >= 0.92
    assert result["evidence"] == "SUCCESS"
    assert result["bound_atom"] is not None
    assert result["bound_atom"] in vsa.codebook
    print(f"[OK] bind PASS invertibility={result['invertibility']:.6f}")


def test_requires_jump_start() -> None:
    vsa = CleanRoomVSAEngine(dim=8192)
    try:
        run_episodic_bind(vsa, note="no bootstrap", require_jump_start=True)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "Jump-Start" in str(e)
        print("[OK] missing Jump-Start blocked")


def test_empty_note_fails() -> None:
    vsa = CleanRoomVSAEngine(dim=8192)
    vsa.jump_start_v01()
    result = run_episodic_bind(vsa, note="   ")
    assert result["status"] == "FAIL"
    assert result["evidence"] == "FAILURE"
    print("[OK] empty note → FAILURE")


def test_via_clean_room_gate() -> None:
    vsa = CleanRoomVSAEngine(dim=8192)
    vsa.jump_start_v01()
    gate = CleanRoomGate(vsa)
    outcome = run_via_gate(gate, note="gated episodic event")
    assert outcome["status"] == "PASS", outcome
    assert outcome["output"]["status"] == "PASS"
    assert outcome["banel_evidence"] == 0.0
    print("[OK] CleanRoomGate execution PASS")


if __name__ == "__main__":
    test_package_json_schema_shape()
    test_rejects_network_flag()
    test_bind_pass_with_jump_start()
    test_requires_jump_start()
    test_empty_note_fails()
    test_via_clean_room_gate()
    print("--- EPISODIC_BIND SKILL TESTS PASSED ---")

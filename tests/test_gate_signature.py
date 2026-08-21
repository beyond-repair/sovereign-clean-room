#!/usr/bin/env python3
"""
Verify CleanRoomGate rejects unsigned / tampered skill packages
and accepts valid offline Ed25519 signatures.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate  # noqa: E402
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _base_package() -> dict:
    return {
        "manifest": {
            "skill_id": "episodic_bind",
            "version": "1.0.0",
            "signature": "UNSIGNED_DEV_PLACEHOLDER",
            "author": "beyond-repair",
        },
        "sovereignty": {
            "network_access": False,
            "file_system_access": "none",
            "execution_mode": "sandboxed_python",
        },
        "vsa_bindings": {
            "dimension": 8192,
            "binding_threshold": 0.92,
            "sparsity_k": 256,
            "codebook_atoms": [
                "SELF",
                "ENVIRONMENT",
                "EPISODIC",
                "SEMANTIC",
                "SUCCESS",
                "FAILURE",
            ],
        },
        "interface": {"inputs": {}, "outputs": {}},
        "banel": {"on_fail_record": True, "context_vector_required": False},
    }


def _ok_payload():
    return {"ok": True}


def test_unsigned_placeholder_rejected() -> None:
    sk, vk = generate_keypair()
    vsa = CleanRoomVSAEngine(dim=512)
    gate = CleanRoomGate(vsa, trusted_verify_keys=[vk], require_skill_signature=True)
    pkg = _base_package()
    result = gate.execute_skill_package(pkg, _ok_payload)
    assert result["status"] == "FAIL"
    assert "signature" in (result["error"] or "").lower() or "placeholder" in (
        result["error"] or ""
    ).lower()
    assert result["output"] is None
    print("[OK] unsigned placeholder rejected")


def test_tampered_package_rejected() -> None:
    sk, vk = generate_keypair()
    vsa = CleanRoomVSAEngine(dim=512)
    gate = CleanRoomGate(vsa, trusted_verify_keys=[vk], require_skill_signature=True)
    pkg = sign_package(_base_package(), sk)
    # Tamper after sign
    bad = copy.deepcopy(pkg)
    bad["manifest"]["version"] = "9.9.9"
    result = gate.execute_skill_package(bad, _ok_payload)
    assert result["status"] == "FAIL"
    assert result["output"] is None
    print("[OK] tampered package rejected")


def test_valid_signature_accepted() -> None:
    sk, vk = generate_keypair()
    vsa = CleanRoomVSAEngine(dim=512)
    gate = CleanRoomGate(vsa, trusted_verify_keys=[vk], require_skill_signature=True)
    pkg = sign_package(_base_package(), sk)
    result = gate.execute_skill_package(pkg, _ok_payload)
    assert result["status"] == "PASS", result
    assert result["output"]["ok"] is True
    print("[OK] valid signature accepted")


def test_wrong_trust_root_rejected() -> None:
    sk, vk = generate_keypair()
    _sk2, vk2 = generate_keypair()
    vsa = CleanRoomVSAEngine(dim=512)
    gate = CleanRoomGate(vsa, trusted_verify_keys=[vk2], require_skill_signature=True)
    pkg = sign_package(_base_package(), sk)
    result = gate.execute_skill_package(pkg, _ok_payload)
    assert result["status"] == "FAIL"
    print("[OK] foreign trust root rejected")


def test_network_access_true_rejected_even_if_signed() -> None:
    sk, vk = generate_keypair()
    vsa = CleanRoomVSAEngine(dim=512)
    gate = CleanRoomGate(vsa, trusted_verify_keys=[vk], require_skill_signature=True)
    raw = _base_package()
    raw["sovereignty"]["network_access"] = True
    # Sign script would refuse; force a signature on illegal package
    pkg = sign_package(raw, sk)
    result = gate.execute_skill_package(pkg, _ok_payload)
    assert result["status"] == "FAIL"
    assert "network" in (result["error"] or "").lower()
    print("[OK] network_access=true rejected even when signed")


def test_no_trusted_keys_rejects() -> None:
    sk, _vk = generate_keypair()
    vsa = CleanRoomVSAEngine(dim=512)
    gate = CleanRoomGate(vsa, trusted_verify_keys=[], require_skill_signature=True)
    pkg = sign_package(_base_package(), sk)
    result = gate.execute_skill_package(pkg, _ok_payload)
    assert result["status"] == "FAIL"
    print("[OK] empty trust store rejects")


if __name__ == "__main__":
    test_unsigned_placeholder_rejected()
    test_tampered_package_rejected()
    test_valid_signature_accepted()
    test_wrong_trust_root_rejected()
    test_network_access_true_rejected_even_if_signed()
    test_no_trusted_keys_rejects()
    print("--- GATE SIGNATURE TESTS PASSED ---")

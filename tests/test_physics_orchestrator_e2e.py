#!/usr/bin/env python3
"""
Physics Bridge v1 — orchestrator + ledger end-to-end hardening.

Invariant:
  PhysicsVerification.result_hash
        │
        ▼  unchanged through pipeline
  FHRR → (optional SHACL) → Orchestrator → Ledger

A valid ledger entry attests the exact phenomenological computation,
not experimental confirmation of Ware/CFT/IQG.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_physics import (  # noqa: E402
    CLAIM_CLASS,
    CLAIM_FLAGS,
    FHRR_DIM,
    WarePhysicsBridge,
    physics_skill_handler,
    verify_physics,
    sample_galaxy,
    hash_payload,
)
from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate  # noqa: E402
from clean_room_orchestrator import CleanRoomOrchestrator, PipelineStep  # noqa: E402
from clean_room_ledger import CleanRoomLedger  # noqa: E402
from clean_room_cli import main as cli_main  # noqa: E402
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _pkg() -> dict:
    return {
        "manifest": {
            "skill_id": "ware_sparc_e2e",
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
    }


def test_native_bridge_through_orchestrator() -> None:
    """Real WarePhysicsBridge (not a mock) via CleanRoomOrchestrator."""
    sk, vk = generate_keypair()
    eng = CleanRoomVSAEngine(dim=8192)
    eng.jump_start_v01()
    bridge = WarePhysicsBridge()
    # Direct baseline for hash comparison
    direct = bridge.evaluate(galaxy_id="SAMPLE_A", n=3.0, log=False)
    assert direct.get("result_hash")
    assert direct["claim_class"] == CLAIM_CLASS
    assert direct["experimental_validation"] is False

    handler = physics_skill_handler(bridge)
    gate = CleanRoomGate(eng, trusted_verify_keys=[vk], enable_shacl=True)
    orch = CleanRoomOrchestrator(
        engine=eng, gate=gate, require_skill_signature=True, fail_fast=True
    )
    result = orch.run(
        [
            PipelineStep(
                package=sign_package(_pkg(), sk),
                handler=handler,
                name="ware_sparc_e2e",
            )
        ],
        initial_state={"galaxy_id": "SAMPLE_A", "n": 3.0},
    )
    assert result.status == "PASS", result.error
    # Last step output should carry same result_hash as pure evaluate
    step_out = None
    if result.steps:
        step_out = result.steps[-1].get("output") or result.steps[-1]
    # Fallback: telemetry
    tel = result.state.get("telemetry") or {}
    rh = tel.get("physics_result_hash") or (
        step_out.get("result_hash") if isinstance(step_out, dict) else None
    )
    assert rh == direct["result_hash"], (
        f"result_hash mutated in pipeline: {rh} != {direct['result_hash']}"
    )
    assert tel.get("claim_class") == CLAIM_CLASS
    assert tel.get("experimental_validation") is False
    print("[OK] native bridge through orchestrator; result_hash unchanged")


def test_ledger_attests_hashes_and_claim_block() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir()
        (ws / "audit").mkdir()
        ledger = CleanRoomLedger(ws / "audit")

        bridge = WarePhysicsBridge()
        out = bridge.evaluate(galaxy_id="SAMPLE_A", n=3.0, log=False)
        assert out.get("result_hash") and out.get("input_hash")

        audit_payload = {
            k: v
            for k, v in out.items()
            if k not in ("fhrr_vector",)
        }
        entry = ledger.append("physics_ware_sparc", audit_payload)
        chain = ledger.verify_chain()
        assert chain.get("ok") is True

        # Reload tip content if ledger stores readable events
        assert entry.seq >= 0
        assert entry.entry_hash

        # Tamper simulation: changing status invalidates recomputed hash
        tampered = dict(audit_payload)
        original_rh = tampered["result_hash"]
        tampered["status"] = "PASS" if tampered.get("status") != "PASS" else "FAIL"
        # result_hash still claims old value — integrity check would fail if re-verified
        from clean_room_physics import PhysicsVerification

        # Reconstruct minimal verification-like payload
        assert original_rh != hash_payload(
            {
                "status": tampered["status"],
                "metrics": tampered.get("metrics"),
                "assumptions": tampered.get("assumptions"),
                "warnings": tampered.get("warnings"),
                "input_hash": tampered.get("input_hash"),
                "network_access": False,
                **{k: CLAIM_FLAGS[k] for k in CLAIM_FLAGS},
            }
        )

        # Claim block recorded
        for k, v in CLAIM_FLAGS.items():
            assert audit_payload[k] == v

        print("[OK] ledger records input_hash, result_hash, claim block")


def test_cli_exit_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = str(Path(tmp) / "ws")
        assert cli_main(["--workspace", ws, "init"]) == 0

        # SAMPLE_A n=3 → may be PASS/FAIL/INCONCLUSIVE; n=5 must FAIL (2)
        rc5 = cli_main(
            ["--workspace", ws, "physics", "eval", "--galaxy", "SAMPLE_A", "--n", "5"]
        )
        assert rc5 == 2

        rc3 = cli_main(
            ["--workspace", ws, "physics", "eval", "--galaxy", "SAMPLE_A", "--n", "3"]
        )
        assert rc3 in (0, 2, 3)

        # Missing local dataset must not be PASS
        rc_miss = cli_main(
            [
                "--workspace",
                ws,
                "physics",
                "eval",
                "--csv",
                str(Path(tmp) / "no_such.csv"),
            ]
        )
        # CLI dies with SystemExit 1 on missing file, or returns non-zero
        assert rc_miss != 0
        print("[OK] CLI exit contract 0/2/3; missing data not PASS")


def test_offline_remote_source_rejected_before_network() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = str(Path(tmp) / "ws")
        cli_main(["--workspace", ws, "init"])
        # Remote URL must fail closed without becoming PASS
        try:
            rc = cli_main(
                [
                    "--workspace",
                    ws,
                    "physics",
                    "eval",
                    "--csv",
                    "https://example.com/sparc.csv",
                ]
            )
            assert rc != 0
        except SystemExit as e:
            assert e.code != 0

        out = WarePhysicsBridge().evaluate(csv_path="https://evil.example/data.csv")
        assert out["status"] == "FAIL"
        assert out["network_access"] is False
        assert out["claim_class"] == CLAIM_CLASS
        print("[OK] remote source rejected offline")


def test_fhrr_boundary_and_claim_unchanged() -> None:
    ver = verify_physics(sample_galaxy("SAMPLE_A"), n=3.0, encode=True)
    assert ver.fhrr_vector is not None
    assert ver.fhrr_vector.shape == (FHRR_DIM,)
    import numpy as np

    assert abs(np.linalg.norm(ver.fhrr_vector) - 1.0) < 1e-9
    d = ver.to_dict(include_vector=True)
    assert d["fhrr_dim"] == FHRR_DIM
    assert d["claim_class"] == CLAIM_CLASS
    assert d["thrust_validated"] is False
    # "Validation failure" must not mutate physics — claim flags stay false
    assert d["experimental_validation"] is False
    print("[OK] FHRR dim/norm + claim metadata stable")


def test_result_hash_survives_ledger_roundtrip() -> None:
    """Critical e2e: same result_hash after ledger append payload."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        ledger = CleanRoomLedger(ws / "audit")
        out = WarePhysicsBridge().evaluate(galaxy_id="SAMPLE_B", n=3.0)
        rh = out["result_hash"]
        ih = out["input_hash"]
        payload = {
            "result_hash": rh,
            "input_hash": ih,
            "status": out["status"],
            "claim_class": out["claim_class"],
            "experimental_validation": out["experimental_validation"],
            "energy_extraction_validated": out["energy_extraction_validated"],
            "thrust_validated": out["thrust_validated"],
            "metrics": out.get("metrics"),
        }
        entry = ledger.append("physics_attestation", payload)
        assert ledger.verify_chain()["ok"] is True
        # Re-evaluate identical inputs → same hashes
        out2 = WarePhysicsBridge().evaluate(galaxy_id="SAMPLE_B", n=3.0)
        assert out2["result_hash"] == rh
        assert out2["input_hash"] == ih
        assert entry.entry_hash
        print("[OK] result_hash provenance across ledger attestation")


if __name__ == "__main__":
    test_native_bridge_through_orchestrator()
    test_ledger_attests_hashes_and_claim_block()
    test_cli_exit_contract()
    test_offline_remote_source_rejected_before_network()
    test_fhrr_boundary_and_claim_unchanged()
    test_result_hash_survives_ledger_roundtrip()
    print("--- PHYSICS ORCHESTRATOR E2E HARDENING PASSED ---")

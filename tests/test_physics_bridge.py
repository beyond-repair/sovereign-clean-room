#!/usr/bin/env python3
"""Tests for offline Ware Constant / SPARC physics bridge."""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_physics import (  # noqa: E402
    ware_weight,
    ghost_free,
    sample_galaxy,
    fit_galaxy,
    WarePhysicsBridge,
    physics_skill_handler,
)
from clean_room_vsa import CleanRoomVSAEngine  # noqa: E402
from clean_room_orchestrator import CleanRoomOrchestrator, PipelineStep  # noqa: E402
from clean_room_vsa import CleanRoomGate  # noqa: E402
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _pkg() -> dict:
    return {
        "manifest": {
            "skill_id": "ware_sparc",
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


def test_ware_recursion_and_ghost_free() -> None:
    assert abs(ware_weight(3) - 0.08) < 1e-12
    assert ghost_free(3)
    assert ghost_free(4)
    assert not ghost_free(5)  # W(5)≈0.1267 > 0.125
    print("[OK] Ware W(n) + ghost-free domain")


def test_sample_curve_fit() -> None:
    pts = sample_galaxy("SAMPLE_A")
    fit = fit_galaxy(pts, "SAMPLE_A", n=3.0)
    assert fit.points == len(pts)
    assert fit.ghost_free is True
    assert fit.chi2_newton >= 0 and fit.chi2_ware >= 0
    assert fit.network_access is False
    print(f"[OK] sample fit improvement={fit.improvement:.4f} rms_w={fit.rms_ware:.3f}")


def test_local_csv_load() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "gal.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["R", "Vobs", "Vgas", "Vdisk"])
            w.writeheader()
            for row in sample_galaxy("SAMPLE_B"):
                w.writerow(
                    {"R": row.R, "Vobs": row.Vobs, "Vgas": row.Vgas, "Vdisk": row.Vdisk}
                )
        bridge = WarePhysicsBridge(workspace=tmp)
        out = bridge.evaluate(csv_path=path, n=3.0, log=True)
        assert out["network_access"] is False
        assert out["shacl_conforms"] is True
        assert "fit" in out
        assert out.get("ledger_seq") is not None
        print("[OK] local CSV + ledger")


def test_fhrr_atom_registered() -> None:
    eng = CleanRoomVSAEngine(dim=8192)
    eng.jump_start_v01()
    with tempfile.TemporaryDirectory() as tmp:
        bridge = WarePhysicsBridge(workspace=tmp, engine=eng)
        out = bridge.evaluate(galaxy_id="SAMPLE_A", n=3.0)
        atom = out["fhrr_atom"]
        assert atom in eng.codebook
        print("[OK] physics result encoded in FHRR")


def test_orchestrator_signed_physics_skill() -> None:
    sk, vk = generate_keypair()
    with tempfile.TemporaryDirectory() as tmp:
        eng = CleanRoomVSAEngine(dim=8192)
        eng.jump_start_v01()
        bridge = WarePhysicsBridge(workspace=tmp, engine=eng)
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
                    name="ware_sparc",
                )
            ],
            initial_state={"galaxy_id": "SAMPLE_A", "n": 3.0},
        )
        assert result.status == "PASS", result.error
        assert result.state.get("telemetry", {}).get("physics_status") in (
            "PASS",
            "FAIL",
            "INCONCLUSIVE",
        )
        print("[OK] signed orchestrator physics skill")


def test_ghost_free_fail_at_high_n() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        bridge = WarePhysicsBridge(workspace=tmp)
        out = bridge.evaluate(galaxy_id="SAMPLE_A", n=5.0, log=False)
        assert out["fit"]["ghost_free"] is False
        assert out["status"] == "FAIL"
        print("[OK] n=5 fails ghost-free gate")


if __name__ == "__main__":
    test_ware_recursion_and_ghost_free()
    test_sample_curve_fit()
    test_local_csv_load()
    test_fhrr_atom_registered()
    test_orchestrator_signed_physics_skill()
    test_ghost_free_fail_at_high_n()
    print("--- PHYSICS BRIDGE TESTS PASSED ---")

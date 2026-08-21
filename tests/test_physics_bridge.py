#!/usr/bin/env python3
"""Tests for pure Ware/SPARC physics kernel — v1 contract gate."""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_physics import (  # noqa: E402
    CLAIM_CLASS,
    CLAIM_FLAGS,
    FHRR_DIM,
    ware_weight,
    ware_result,
    ghost_free,
    sample_galaxy,
    load_sparc_csv,
    fit_sparc,
    verify_physics,
    verify_result_integrity,
    encode_fhrr,
    hash_payload,
    WarePhysicsBridge,
    physics_skill_handler,
    ProcaField,
    PhysicsVerification,
)
from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate  # noqa: E402
from clean_room_orchestrator import CleanRoomOrchestrator, PipelineStep  # noqa: E402
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


def test_canonical_ware_law() -> None:
    assert abs(ware_weight(3) - 0.08) < 1e-12
    assert abs(ware_weight(4) - 0.08 * np.exp(0.23)) < 1e-12
    assert ghost_free(3) and ghost_free(4) and not ghost_free(5)
    wr = ware_result(3)
    assert wr.bound_satisfied and abs(wr.W - 0.08) < 1e-12
    print("[OK] canonical W(n)=0.08*exp(0.23*(n-3))")


def test_identical_input_identical_result() -> None:
    c = sample_galaxy("SAMPLE_A")
    a = verify_physics(c, n=3.0)
    b = verify_physics(c, n=3.0)
    assert a.input_hash == b.input_hash and a.result_hash == b.result_hash
    assert verify_result_integrity(a)
    print("[OK] deterministic verification hashes")


def test_fhrr_dim_and_determinism() -> None:
    metrics = {"x": 1, "y": [2, 3]}
    v1, v2 = encode_fhrr(metrics), encode_fhrr(metrics)
    assert v1.shape == (FHRR_DIM,)
    assert np.allclose(v1, v2)
    assert abs(np.linalg.norm(v1) - 1.0) < 1e-9
    print("[OK] FHRR dim=8192 deterministic")


def test_tamper_invalidates_hash() -> None:
    ver = verify_physics(sample_galaxy("SAMPLE_A"), n=3.0)
    assert verify_result_integrity(ver)
    ver.status = "PASS" if ver.status != "PASS" else "FAIL"
    assert not verify_result_integrity(ver)
    print("[OK] result_hash detects tampering")


def test_immutable_claim_flags() -> None:
    ver = verify_physics(sample_galaxy("SAMPLE_A"), n=3.0)
    assert ver.claim_class == CLAIM_CLASS == "phenomenological_hypothesis"
    assert ver.experimental_validation is False
    assert ver.energy_extraction_validated is False
    assert ver.thrust_validated is False
    assert ver.network_access is False

    # Constructor overrides must not stick
    forced = PhysicsVerification(
        status="PASS",
        metrics={},
        assumptions=[],
        warnings=[],
        claim_class="experimentally_confirmed",  # type: ignore[arg-type]
        experimental_validation=True,
        energy_extraction_validated=True,
        thrust_validated=True,
        network_access=True,
    )
    assert forced.claim_class == "phenomenological_hypothesis"
    assert forced.experimental_validation is False
    assert forced.energy_extraction_validated is False
    assert forced.thrust_validated is False
    assert forced.network_access is False

    # Claim flags participate in result_hash
    d = ver.to_dict()
    assert d["claim_class"] == "phenomenological_hypothesis"
    assert d["experimental_validation"] is False
    payload = ver.payload_for_hash()
    assert payload["claim_class"] == CLAIM_CLASS
    assert "experimental_validation" in payload

    out = WarePhysicsBridge().evaluate(galaxy_id="SAMPLE_A", n=3.0)
    for k, v in CLAIM_FLAGS.items():
        assert out[k] == v
    print("[OK] immutable claim_class flags in object + hash + evaluate dict")


def test_remote_path_rejected() -> None:
    out = WarePhysicsBridge().evaluate(csv_path="https://example.com/sparc.csv")
    assert out["status"] == "FAIL" and out["network_access"] is False
    assert out["claim_class"] == CLAIM_CLASS
    try:
        load_sparc_csv("https://cdn.example/data.csv")
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass
    print("[OK] remote paths hard-fail")


def test_malformed_curve_inconclusive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.csv"
        path.write_text("not,a,curve\n1,2,3\n", encoding="utf-8")
        out = WarePhysicsBridge().evaluate(csv_path=path)
        assert out["status"] == "INCONCLUSIVE"
        assert out["experimental_validation"] is False
    print("[OK] malformed CSV → INCONCLUSIVE")


def test_local_csv_and_proca_residual() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "gal.csv"
        c = sample_galaxy("SAMPLE_B")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f, fieldnames=["R", "Vobs", "Verr", "Vgas", "Vdisk", "Vbulge"]
            )
            w.writeheader()
            for i in range(c.n_points):
                w.writerow(
                    {
                        "R": c.radius_kpc[i],
                        "Vobs": c.velocity_obs[i],
                        "Verr": c.velocity_err[i],
                        "Vgas": c.velocity_gas[i],
                        "Vdisk": c.velocity_disk[i],
                        "Vbulge": c.velocity_bulge[i],
                    }
                )
        loaded = load_sparc_csv(path)
        proca = ProcaField(coupling=25.0)
        R = np.asarray(loaded.radius_kpc)
        delta = proca.evaluate_delta_v(R, ware_weight(3))
        assert proca.residual is not None and delta.shape == R.shape
        fit = fit_sparc(loaded, n=3.0)
        assert fit.baseline_rmse >= 0
    print("[OK] local CSV + Proca residual")


def test_ghost_free_fail_high_n() -> None:
    out = WarePhysicsBridge().evaluate(galaxy_id="SAMPLE_A", n=5.0)
    assert out["status"] == "FAIL"
    assert out["thrust_validated"] is False
    print("[OK] n=5 fails ghost-free")


def test_disclaimer_present() -> None:
    out = WarePhysicsBridge().evaluate(galaxy_id="SAMPLE_A", n=3.0)
    assert "Not experimental validation" in out.get("disclaimer", "")
    assert len(out.get("assumptions") or []) >= 3
    print("[OK] scientific disclaimer")


def test_orchestrator_signed_skill() -> None:
    sk, vk = generate_keypair()
    eng = CleanRoomVSAEngine(dim=8192)
    eng.jump_start_v01()
    handler = physics_skill_handler(WarePhysicsBridge())
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
    tel = result.state["telemetry"]
    assert tel["physics_status"] in ("PASS", "FAIL", "INCONCLUSIVE")
    assert tel.get("claim_class") == CLAIM_CLASS
    assert tel.get("experimental_validation") is False
    print("[OK] signed orchestrator physics skill + claim telemetry")


if __name__ == "__main__":
    test_canonical_ware_law()
    test_identical_input_identical_result()
    test_fhrr_dim_and_determinism()
    test_tamper_invalidates_hash()
    test_immutable_claim_flags()
    test_remote_path_rejected()
    test_malformed_curve_inconclusive()
    test_local_csv_and_proca_residual()
    test_ghost_free_fail_high_n()
    test_disclaimer_present()
    test_orchestrator_signed_skill()
    print("--- PHYSICS BRIDGE v1 CONTRACT TESTS PASSED ---")

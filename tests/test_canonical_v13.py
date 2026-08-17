#!/usr/bin/env python3
"""
SEEM v1.3 Canonical Verification Harness
Focus: FHRR invertibility, Clean-Room gate threshold, atomic persistence
Aligned with manifests/CONSTITUTION_v1.3.md
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

# Ensure core is importable when run from repo root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate  # noqa: E402

DIMENSION = 8192
GATE_THRESHOLD = 0.92
SPARSITY_K = 256
NUM_TRIALS = 200


def test_fhrr_invertibility_exact_bind() -> None:
    """Exact FHRR bind/unbind of unit vectors should recover near machine precision."""
    vsa = CleanRoomVSAEngine(dim=DIMENSION, sparsity_k=SPARSITY_K, min_invertibility=GATE_THRESHOLD)
    similarities = []
    for _ in range(NUM_TRIALS):
        a = vsa.random_symbol()
        b = vsa.random_symbol()
        bound = vsa.bind(a, b)
        recovered = vsa.unbind(bound, a)
        similarities.append(vsa.similarity(b, recovered))
    mean_sim = float(np.mean(similarities))
    min_sim = float(np.min(similarities))
    print(f"[VSA] Mean invertibility: {mean_sim:.6f} | Min: {min_sim:.6f}")
    assert min_sim > 0.999, f"Exact FHRR invertibility degraded: min={min_sim}"


def test_gated_promotion_rejects_noise() -> None:
    """Clean binding should promote; unstructured noise should fail the gate."""
    vsa = CleanRoomVSAEngine(dim=DIMENSION, sparsity_k=SPARSITY_K, min_invertibility=GATE_THRESHOLD)
    role = vsa.register("ROLE_TEST")
    filler = vsa.register("FILLER_TEST")
    bound = vsa.bind(role, filler)

    ok = vsa.promote_memskill("CLEAN_SKILL", bound, binder=role)
    print(f"[GATE] Clean promotion accepted: {ok}")
    assert ok is True

    noise = vsa.random_symbol()
    bad = vsa.promote_memskill("NOISE_SKILL", noise, binder=role)
    print(f"[GATE] Noise promotion accepted: {bad}")
    assert bad is False


def test_clean_room_gate_sanitizes() -> None:
    vsa = CleanRoomVSAEngine(dim=DIMENSION, sparsity_k=SPARSITY_K)
    gate = CleanRoomGate(vsa)

    def good():
        return np.array([1.0, 2.0, 3.0])

    def bad():
        return np.array([1.0, np.nan, 3.0])

    pass_result = gate.execute_sandboxed_computation("good_job", good)
    fail_result = gate.execute_sandboxed_computation("bad_job", bad)
    print(f"[SANDBOX] good={pass_result['status']} bad={fail_result['status']}")
    assert pass_result["status"] == "PASS"
    assert fail_result["status"] == "FAIL"
    assert len(vsa.banel.failure_ledger) >= 1


def test_atomic_persistence_roundtrip() -> None:
    vsa = CleanRoomVSAEngine(dim=DIMENSION, sparsity_k=SPARSITY_K)
    for name in ("SELF", "ENVIRONMENT", "EPISODIC", "SEMANTIC", "SUCCESS", "FAILURE"):
        vsa.register(name)

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "twin_state"
        vsa.save(state_path)
        restored = CleanRoomVSAEngine()
        restored.load(state_path)
        keys = set(restored.codebook.keys())
        print(f"[PERSIST] Restored atoms: {sorted(keys)}")
        assert keys == {"SELF", "ENVIRONMENT", "EPISODIC", "SEMANTIC", "SUCCESS", "FAILURE"}
        assert restored.dim == DIMENSION
        assert restored.sparsity_k == SPARSITY_K
        assert restored.min_invertibility == GATE_THRESHOLD


if __name__ == "__main__":
    print("--- SEEM v1.3 CANONICAL SUITE ---")
    test_fhrr_invertibility_exact_bind()
    test_gated_promotion_rejects_noise()
    test_clean_room_gate_sanitizes()
    test_atomic_persistence_roundtrip()
    print("--- ALL BENCHMARKS PASSED ---")

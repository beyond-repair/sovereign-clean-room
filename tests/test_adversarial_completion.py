"""Adversarial inputs fail closed."""

from __future__ import annotations

import numpy as np
import pytest

from benchmark_metrics import phasor_project
from clean_room_vsa import BaNEL, CleanRoomVSAEngine
from memskill_ir import CanonicalizationError, canonicalize
from memskill_runtime import execute_trace


def _base():
    return {
        "skillId": "11111111-1111-4111-8111-111111111111",
        "invertibilityScore": 0.95,
        "maxExecutionMs": 10,
        "networkAccessPermitted": False,
        "verificationHash": "cd" * 32,
        "transitions": [
            {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1}
        ],
    }


def test_malformed_and_malicious_memskill():
    with pytest.raises(CanonicalizationError):
        canonicalize({"transitions": "nope"})
    with pytest.raises(CanonicalizationError):
        canonicalize(_base() | {"networkAccessPermitted": True})
    with pytest.raises(CanonicalizationError):
        canonicalize(
            _base()
            | {
                "transitions": [
                    {"stepIndex": 0, "operatorSymbol": "exec", "resourceCost": 1}
                ]
            }
        )
    label, _ = execute_trace(
        {
            "transitions": [
                {"stepIndex": 0, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 100000}
            ]
        }
    )
    assert label == "UNSAFE"


def test_zero_phasor_and_corrupted_vector():
    z = np.array([1 + 0j, 0j, 1j], dtype=np.complex128)
    out, faults = phasor_project(z)
    assert faults == 1
    assert out[1] == 0
    corrupted = np.array([np.nan, 1], dtype=np.complex128)
    projected, faults = phasor_project(corrupted)
    assert faults >= 1
    assert projected[0] == 0


def test_resource_exhaustion_and_superseded_repulsion():
    label, reason = execute_trace(
        {
            "transitions": [
                {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 70},
                {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 70},
            ]
        },
        max_resource_capacity=100,
    )
    assert label == "UNSAFE"
    assert "resource" in reason
    engine = CleanRoomVSAEngine(dim=32, seed=1)
    query = engine.random_symbol()
    failure = engine.random_symbol()
    banel = BaNEL()
    repelled = banel.parallel_repulsion(query, failure)
    assert abs(float(np.linalg.norm(repelled)) - 1.0) < 1e-8
    before = abs(engine.similarity(query, failure))
    after = abs(engine.similarity(repelled, failure))
    assert after <= before + 1e-6

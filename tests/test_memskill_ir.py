"""Canonical IR rejects split representations."""

from __future__ import annotations

import pytest

from memskill_ir import CanonicalizationError, canonicalize, canonical_sha256


def _candidate(**overrides):
    base = {
        "skillId": "11111111-1111-4111-8111-111111111111",
        "invertibilityScore": 0.95,
        "maxExecutionMs": 100,
        "networkAccessPermitted": False,
        "verificationHash": "a" * 64,
        "transitions": [
            {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1}
        ],
    }
    base.update(overrides)
    return base


def test_round_trip_hash_stable():
    ir = canonicalize(_candidate())
    assert canonical_sha256(ir) == canonical_sha256(ir)


def test_disagreeing_step_lists_rejected():
    bad = _candidate(
        hasTransitionStep=[
            {"stepIndex": 0, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 1}
        ]
    )
    with pytest.raises(CanonicalizationError):
        canonicalize(bad)


def test_network_true_rejected():
    with pytest.raises(CanonicalizationError):
        canonicalize(_candidate(networkAccessPermitted=True))

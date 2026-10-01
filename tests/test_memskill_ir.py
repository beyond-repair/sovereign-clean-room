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
            {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1},
            {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 2},
            {"stepIndex": 2, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 3},
        ],
    }
    base.update(overrides)
    return base


def test_round_trip_hash_stable():
    ir = canonicalize(_candidate())
    assert canonical_sha256(ir) == canonical_sha256(canonicalize(ir))


def test_reordered_fields_same_hash():
    a = _candidate()
    b = {k: a[k] for k in reversed(list(a))}
    assert canonical_sha256(canonicalize(a)) == canonical_sha256(canonicalize(b))


def test_reordered_same_steps_agree_and_sort():
    steps = _candidate()["transitions"]
    flipped = list(reversed(steps))
    ir = canonicalize(_candidate(transitions=steps, hasTransitionStep=flipped))
    assert [s["stepIndex"] for s in ir["transitions"]] == [0, 1, 2]


def test_disagreeing_step_lists_rejected():
    bad = _candidate(
        hasTransitionStep=[
            {"stepIndex": 0, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 1}
        ]
    )
    with pytest.raises(CanonicalizationError, match="disagree"):
        canonicalize(bad)


def test_order_that_changes_step_identity_rejected():
    left = [
        {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1},
        {"stepIndex": 1, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 1},
    ]
    right = [
        {"stepIndex": 0, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 1},
        {"stepIndex": 1, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1},
    ]
    with pytest.raises(CanonicalizationError, match="disagree"):
        canonicalize(_candidate(transitions=left, hasTransitionStep=right))


def test_duplicate_missing_and_extra_steps():
    with pytest.raises(CanonicalizationError):
        canonicalize(
            _candidate(
                transitions=[
                    {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1},
                    {"stepIndex": 0, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 1},
                ]
            )
        )
    with pytest.raises(CanonicalizationError):
        canonicalize(_candidate(transitions=[]))
    extra = _candidate()["transitions"] + [
        {"stepIndex": 3, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 1}
    ]
    with pytest.raises(CanonicalizationError, match="disagree"):
        canonicalize(_candidate(hasTransitionStep=extra))


def test_malformed_types_and_resources_and_targets():
    bad_type = _candidate()
    bad_type["transitions"] = [
        {"stepIndex": "0", "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1}
    ]
    with pytest.raises(CanonicalizationError):
        canonicalize(bad_type)
    with pytest.raises(CanonicalizationError):
        canonicalize(
            _candidate(
                transitions=[{"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 101}]
            )
        )
    with pytest.raises(CanonicalizationError):
        canonicalize(
            _candidate(
                transitions=[
                    {
                        "stepIndex": 0,
                        "operatorSymbol": "ISOLATE_ENVIRONMENT",
                        "resourceCost": 1,
                        "target": "not valid",
                    }
                ]
            )
        )
    with pytest.raises(CanonicalizationError):
        canonicalize(
            _candidate(
                transitions=[
                    {
                        "stepIndex": 0,
                        "operatorSymbol": "ISOLATE_ENVIRONMENT",
                        "resourceCost": 1,
                        "targetStep": 9,
                    }
                ]
            )
        )


def test_missing_precondition_rejected():
    with pytest.raises(CanonicalizationError, match="precondition"):
        canonicalize(_candidate(preconditions=[{"dischargedBy": "ISOLATE_ENVIRONMENT"}]))


def test_network_true_rejected():
    with pytest.raises(CanonicalizationError):
        canonicalize(_candidate(networkAccessPermitted=True))

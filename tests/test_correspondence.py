"""Formal/runtime correspondence. Z3 SAT is not runtime safety."""

from __future__ import annotations

import pytest

z3 = pytest.importorskip("z3")

from clean_room_z3 import MemSkillZ3Verifier
from memskill_runtime import correspondence, execute_trace


def _pipe(ops, costs=None, preconditions=None):
    costs = costs or [1] * len(ops)
    body = {
        "transitions": [
            {"stepIndex": i, "operatorSymbol": op, "resourceCost": costs[i]}
            for i, op in enumerate(ops)
        ]
    }
    if preconditions is not None:
        body["preconditions"] = preconditions
    return body


def test_correspondence_matrix_cases():
    verifier = MemSkillZ3Verifier(max_resource_capacity=100)
    safe = _pipe(["ISOLATE_ENVIRONMENT", "VERIFY_INTEGRITY", "EXECUTE_PRIMITIVE"])
    z_ok, _ = verifier.verify_memskill(safe)
    r_label, _ = execute_trace(safe)
    assert correspondence(z_ok, r_label)["interpretation"] == "true_positive"

    unsafe = _pipe(["EXECUTE_PRIMITIVE"])
    z_ok, _ = verifier.verify_memskill(unsafe)
    r_label, _ = execute_trace(unsafe)
    assert correspondence(z_ok, r_label)["interpretation"] == "correct_rejection"

    overflow = _pipe(
        ["ISOLATE_ENVIRONMENT", "VERIFY_INTEGRITY"],
        costs=[60, 50],
    )
    z_ok, _ = verifier.verify_memskill(overflow)
    r_label, _ = execute_trace(overflow)
    assert correspondence(z_ok, r_label)["interpretation"] == "correct_rejection"

    external = _pipe(
        ["ISOLATE_ENVIRONMENT", "VERIFY_INTEGRITY", "EXECUTE_PRIMITIVE"],
        preconditions=[{"id": "HUMAN_APPROVAL", "dischargedBy": "EXTERNAL"}],
    )
    z_ok, _ = verifier.verify_memskill(external)
    r_label, _ = execute_trace(external, observed_external=["HUMAN_APPROVAL"])
    assert correspondence(z_ok, r_label)["interpretation"] == "conservative_rejection"
    # Same candidate without the observation is a correct rejection, not a pass.
    r_miss, _ = execute_trace(external, observed_external=[])
    assert correspondence(z_ok, r_miss)["interpretation"] == "correct_rejection"


def test_no_builtin_formal_unsoundness():
    verifier = MemSkillZ3Verifier()
    fixtures = [
        _pipe(["ISOLATE_ENVIRONMENT", "VERIFY_INTEGRITY", "EXECUTE_PRIMITIVE"]),
        _pipe(["EXECUTE_PRIMITIVE"]),
        _pipe(["VERIFY_INTEGRITY"]),
        _pipe(["ISOLATE_ENVIRONMENT", "EXECUTE_PRIMITIVE"]),
        _pipe(["ISOLATE_ENVIRONMENT", "VERIFY_INTEGRITY"], costs=[80, 30]),
        _pipe(["NOOP"]),
    ]
    for fixture in fixtures:
        z_ok, _ = verifier.verify_memskill(fixture)
        r_label, _ = execute_trace(fixture)
        assert correspondence(z_ok, r_label)["interpretation"] != "formal_model_unsound"

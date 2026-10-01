"""Z3 MemSkill gate. Skips when z3-solver is not installed (default CI)."""

from __future__ import annotations

import pytest

z3 = pytest.importorskip("z3")

from clean_room_z3 import MemSkillZ3Verifier


def test_valid_isolate_verify_execute_is_sat():
    verifier = MemSkillZ3Verifier(max_resource_capacity=100)
    ok, msg = verifier.verify_memskill(
        {
            "transitions": [
                {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 15},
                {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 10},
                {"stepIndex": 2, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 30},
            ]
        }
    )
    assert ok, msg
    assert "Z3_PROVED_SAT" in msg


def test_execute_without_isolate_is_unsat():
    verifier = MemSkillZ3Verifier(max_resource_capacity=100)
    ok, msg = verifier.verify_memskill(
        {"transitions": [{"stepIndex": 0, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 30}]}
    )
    assert not ok
    assert "UNSAT" in msg


def test_resource_overflow_is_unsat():
    verifier = MemSkillZ3Verifier(max_resource_capacity=100)
    ok, msg = verifier.verify_memskill(
        {
            "transitions": [
                {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 60},
                {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 50},
            ]
        }
    )
    assert not ok
    assert "UNSAT" in msg


def test_empty_pipeline_rejected_without_solver_sat():
    verifier = MemSkillZ3Verifier()
    ok, msg = verifier.verify_memskill({"transitions": []})
    assert not ok
    assert "Empty" in msg

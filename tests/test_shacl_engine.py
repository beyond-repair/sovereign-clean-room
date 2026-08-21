#!/usr/bin/env python3
"""Tests for offline SHACL-subset engine, FHRR bridge, gate/daemon hooks."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate  # noqa: E402
from clean_room_shacl import (  # noqa: E402
    ShapeEngine,
    LocalGraph,
    NeuroSymbolicBridge,
    ConstitutionalValidator,
    CONSTITUTIONAL_SHAPES,
    skill_package_to_graph,
)
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def test_valid_skill_package_shape() -> None:
    eng = ShapeEngine(CONSTITUTIONAL_SHAPES)
    pkg = {
        "sovereignty": {"network_access": False},
        "vsa_bindings": {"dimension": 8192},
    }
    report = eng.validate_graph(skill_package_to_graph(pkg), "SkillPackageSovereigntyShape")
    assert report.conforms, report.to_dict()
    print("[OK] valid skill package conforms")


def test_reject_network_true() -> None:
    eng = ShapeEngine(CONSTITUTIONAL_SHAPES)
    pkg = {
        "sovereignty": {"network_access": True},
        "vsa_bindings": {"dimension": 8192},
    }
    report = eng.validate_graph(skill_package_to_graph(pkg), "SkillPackageSovereigntyShape")
    assert not report.conforms
    assert any("network" in v.message or "hasValue" in v.message for v in report.violations)
    print("[OK] network_access=true rejected by shape")


def test_reject_wrong_dimension() -> None:
    eng = ShapeEngine(CONSTITUTIONAL_SHAPES)
    pkg = {
        "sovereignty": {"network_access": False},
        "vsa_bindings": {"dimension": 4096},
    }
    report = eng.validate_graph(skill_package_to_graph(pkg), "SkillPackageSovereigntyShape")
    assert not report.conforms
    print("[OK] wrong dimension rejected")


def test_closed_shape_unexpected_property() -> None:
    shapes = ShapeEngine.from_python(
        [
            {
                "id": "ClosedDemo",
                "targetNode": "n1",
                "closed": True,
                "properties": [{"path": "ex:a", "minCount": 1}],
            }
        ]
    )
    g = LocalGraph.from_mapping({"n1": {"ex:a": 1, "ex:b": 2}})
    report = shapes.validate_graph(g, "ClosedDemo")
    assert not report.conforms
    assert any("unexpected" in v.message for v in report.violations)
    print("[OK] closed shape rejects extra properties")


def test_neuro_symbolic_compliance_vector() -> None:
    vsa = CleanRoomVSAEngine(dim=8192)
    vsa.jump_start_v01()
    bridge = NeuroSymbolicBridge(vsa)
    eng = ShapeEngine(CONSTITUTIONAL_SHAPES)
    good = eng.validate_graph(
        skill_package_to_graph(
            {
                "sovereignty": {"network_access": False},
                "vsa_bindings": {"dimension": 8192},
            }
        ),
        "SkillPackageSovereigntyShape",
    )
    assert good.conforms
    assert bridge.query_conforms(good, tau=0.92)
    sim = bridge.compliance_similarity(good, expect_conforms=True)
    assert sim >= 0.92, sim

    bad = eng.validate_graph(
        skill_package_to_graph(
            {
                "sovereignty": {"network_access": True},
                "vsa_bindings": {"dimension": 8192},
            }
        ),
        "SkillPackageSovereigntyShape",
    )
    assert not bad.conforms
    assert bridge.compliance_similarity(bad, expect_conforms=True) < 0.92
    print("[OK] neuro-symbolic compliance vectors")


def test_gate_integration_shacl_precheck() -> None:
    """Gate path: SHACL package check before signature path."""
    sk, vk = generate_keypair()
    vsa = CleanRoomVSAEngine(dim=8192)
    vsa.jump_start_v01()
    gate = CleanRoomGate(vsa, trusted_verify_keys=[vk], require_skill_signature=True)
    validator = ConstitutionalValidator(engine=vsa)

    good_pkg = sign_package(
        {
            "manifest": {
                "skill_id": "demo",
                "version": "1.0.0",
                "signature": "UNSIGNED_DEV_PLACEHOLDER",
                "author": "x",
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
                "codebook_atoms": [],
            },
            "interface": {"inputs": {}, "outputs": {}},
        },
        sk,
    )
    report = validator.validate_skill_package(good_pkg)
    assert report.conforms

    # Malformed status result shape
    bad_result = {"status": "MAYBE"}
    r2 = validator.validate_gate_result(bad_result)
    assert not r2.conforms

    # Valid gate result shape after execution simulation
    outcome = gate.execute_skill_package(good_pkg, lambda: {"ok": True})
    assert outcome["status"] == "PASS"
    r3 = validator.validate_gate_result(outcome)
    assert r3.conforms
    print("[OK] gate + SHACL pre/post checks")


def test_load_shapes_from_json_file() -> None:
    path = ROOT / "shapes" / "constitutional_shapes.json"
    eng = ShapeEngine.from_json_file(path)
    assert len(eng.shapes) >= 3
    print("[OK] shapes loaded from local JSON file")


if __name__ == "__main__":
    test_valid_skill_package_shape()
    test_reject_network_true()
    test_reject_wrong_dimension()
    test_closed_shape_unexpected_property()
    test_neuro_symbolic_compliance_vector()
    test_gate_integration_shacl_precheck()
    test_load_shapes_from_json_file()
    print("--- SHACL ENGINE TESTS PASSED ---")

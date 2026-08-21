#!/usr/bin/env python3
"""Integration tests for CleanRoomOrchestrator multi-skill pipelines."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import CleanRoomVSAEngine  # noqa: E402
from clean_room_orchestrator import (  # noqa: E402
    CleanRoomOrchestrator,
    PipelineStep,
)
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _pkg(skill_id: str, network: bool = False) -> dict:
    return {
        "manifest": {
            "skill_id": skill_id,
            "version": "1.0.0",
            "signature": "UNSIGNED_DEV_PLACEHOLDER",
            "author": "beyond-repair",
        },
        "sovereignty": {
            "network_access": network,
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
        "banel": {"on_fail_record": True},
    }


def _bind_handler(engine, gate, state, idx):
    """Simulate episodic_bind: use note from inputs, chain marker into telemetry."""
    note = state.get("inputs", {}).get("note", "default-note")
    # Touch constitutional atoms to prove shared core continuity
    assert "EPISODIC" in engine.codebook
    role = engine.codebook["EPISODIC"]
    filler = engine.random_symbol()
    bound = engine.bind(role, filler)
    recovered = engine.unbind(bound, role)
    score = engine.similarity(filler, recovered)
    engine.touch("SUCCESS" if score >= 0.92 else "FAILURE")
    state.setdefault("telemetry", {})["bind_score"] = score
    state["telemetry"]["note"] = note
    return {"status": "PASS", "invertibility": score, "stage": "bind"}


def _enrich_handler(engine, gate, state, idx):
    """Second skill: consume last_output from prior step (offline chain)."""
    prev = state.get("last_output") or {}
    if prev.get("stage") != "bind":
        raise RuntimeError("missing bind handoff")
    score = float(prev.get("invertibility", 0.0))
    engine.touch("SEMANTIC")
    state.setdefault("telemetry", {})["enriched"] = True
    state["telemetry"]["upstream_score"] = score
    return {
        "status": "PASS",
        "stage": "enrich",
        "upstream_score": score,
        "chained": True,
    }


def test_pipeline_succeeds_with_valid_signatures() -> None:
    sk, vk = generate_keypair()
    eng = CleanRoomVSAEngine(dim=8192)
    orch = CleanRoomOrchestrator(
        engine=eng,
        trusted_verify_keys=[vk],
        require_skill_signature=True,
        fail_fast=True,
    )

    p1 = sign_package(_pkg("episodic_bind"), sk)
    p2 = sign_package(_pkg("semantic_enrich"), sk)

    result = orch.run(
        [
            PipelineStep(package=p1, handler=_bind_handler, name="episodic_bind"),
            PipelineStep(package=p2, handler=_enrich_handler, name="semantic_enrich"),
        ],
        initial_state={"note": "pipeline-memory-1"},
    )

    assert result.status == "PASS", result.error
    assert result.aborted_at is None
    assert len(result.steps) == 2
    assert result.steps[0]["gate_status"] == "PASS"
    assert result.steps[1]["gate_status"] == "PASS"
    assert result.state["last_output"]["chained"] is True
    assert result.state["telemetry"]["enriched"] is True
    assert "EPISODIC" in eng.codebook
    assert eng.verify_jump_start_integrity()
    print("[OK] multi-skill pipeline PASS with valid signatures + state chain")


def test_pipeline_aborts_on_bad_intermediate_signature() -> None:
    sk, vk = generate_keypair()
    eng = CleanRoomVSAEngine(dim=8192)
    orch = CleanRoomOrchestrator(
        engine=eng,
        trusted_verify_keys=[vk],
        require_skill_signature=True,
        fail_fast=True,
    )

    p1 = sign_package(_pkg("episodic_bind"), sk)
    p2 = sign_package(_pkg("semantic_enrich"), sk)
    # Tamper second package after signing
    p2_bad = copy.deepcopy(p2)
    p2_bad["manifest"]["version"] = "9.9.9"

    result = orch.run(
        [
            PipelineStep(package=p1, handler=_bind_handler),
            PipelineStep(package=p2_bad, handler=_enrich_handler),
        ],
        initial_state={"note": "will-abort"},
    )

    assert result.status == "FAIL"
    assert result.aborted_at == 1
    assert len(result.steps) == 2
    assert result.steps[0]["gate_status"] == "PASS"
    assert result.steps[1]["gate_status"] == "FAIL"
    # Second handler must not have run successfully
    assert result.state.get("telemetry", {}).get("enriched") is not True
    print("[OK] pipeline aborts on intermediate signature failure")


def test_pipeline_aborts_on_unsigned_first_skill() -> None:
    _sk, vk = generate_keypair()
    orch = CleanRoomOrchestrator(
        trusted_verify_keys=[vk],
        require_skill_signature=True,
    )
    unsigned = _pkg("episodic_bind")
    signed_second = sign_package(_pkg("semantic_enrich"), _sk)

    result = orch.run(
        [
            PipelineStep(package=unsigned, handler=_bind_handler),
            PipelineStep(package=signed_second, handler=_enrich_handler),
        ]
    )

    assert result.status == "FAIL"
    assert result.aborted_at == 0
    assert len(result.steps) == 1
    print("[OK] pipeline aborts on unsigned first skill")


def test_pipeline_aborts_on_network_flag() -> None:
    sk, vk = generate_keypair()
    orch = CleanRoomOrchestrator(trusted_verify_keys=[vk])
    # sign_package allows constructing dict; gate still rejects network_access
    illegal = _pkg("net_skill", network=True)
    signed_illegal = sign_package(illegal, sk)
    ok = sign_package(_pkg("episodic_bind"), sk)

    result = orch.run(
        [
            PipelineStep(package=ok, handler=_bind_handler),
            PipelineStep(package=signed_illegal, handler=_enrich_handler),
        ]
    )
    assert result.status == "FAIL"
    assert result.aborted_at == 1
    assert "network" in (result.error or "").lower()
    print("[OK] pipeline aborts on network_access violation")


if __name__ == "__main__":
    test_pipeline_succeeds_with_valid_signatures()
    test_pipeline_aborts_on_bad_intermediate_signature()
    test_pipeline_aborts_on_unsigned_first_skill()
    test_pipeline_aborts_on_network_flag()
    print("--- ORCHESTRATOR TESTS PASSED ---")

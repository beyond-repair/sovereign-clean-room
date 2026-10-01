"""End-to-end scenarios using the real gate, ledger, and runtime."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest

from clean_room_ledger import CheckpointStore, CleanRoomLedger, PipelineCheckpoint
from clean_room_z3 import MemSkillZ3Verifier
from episodic_memory import EpisodicMemoryLedger
from memskill import promote_memskill, verify_memskill_package
from memskill_governance_gate import MemSkillGovernanceGate
from memskill_runtime import correspondence, execute_trace
from skill_crypto import generate_keypair, sign_package, verify_package


def _candidate():
    return {
        "skillId": "22222222-2222-4222-8222-222222222222",
        "invertibilityScore": 0.96,
        "maxExecutionMs": 40,
        "networkAccessPermitted": False,
        "verificationHash": "ef" * 32,
        "transitions": [
            {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 4},
            {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 4},
            {"stepIndex": 2, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 4},
        ],
    }


def test_successful_learning_and_invalid_signature(tmp_path, monkeypatch):
    pytest.importorskip("z3")
    pytest.importorskip("pyshacl")
    sk, vk = generate_keypair()
    monkeypatch.setenv("SEEM_SKILL_SIGNING_KEY_HEX", sk)
    shape = Path(__file__).resolve().parents[1] / "shapes" / "mem_skill_shape.ttl"
    gate = MemSkillGovernanceGate(str(shape))
    passed, package, message = gate.evaluate_and_sign(_candidate())
    assert passed, message
    assert verify_package(package, [vk]) is True
    led = CleanRoomLedger(tmp_path / "led")
    led.append(
        "promotion",
        {
            "what": "signed L3",
            "why": "governance pass",
            "evidence": {"message": message[:120]},
            "skill_id": package["ir"]["skillId"],
            "constraints": {"network_access": False},
            "failed": False,
            "changed": {"signature": True},
        },
    )
    assert led.verify_chain()["ok"] is True
    broken = copy.deepcopy(package)
    broken["ir"]["transitions"][2]["operatorSymbol"] = "EXECUTE_PRIMITIVE_TAMPER"
    with pytest.raises(Exception):
        verify_package(broken, [vk])


def test_episode_promote_is_not_a_governance_pass(tmp_path):
    root = tmp_path / "ep"
    ledger = EpisodicMemoryLedger(root)
    ledger.create_and_append("t1", "created", {"title": "learn", "description": "ok"})
    ledger.create_and_append("t1", "completed", {"result": "done"})
    episode = ledger.reconstruct_episode("t1")
    package = promote_memskill(episode)
    assert package["governance_passed"] is False
    assert package["signed"] is False
    assert verify_memskill_package(package) is False


def test_z3_runtime_disagreement_and_restart(tmp_path):
    pytest.importorskip("z3")
    verifier = MemSkillZ3Verifier()
    body = {
        "transitions": [
            {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1},
            {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 1},
            {"stepIndex": 2, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 1},
        ],
        "preconditions": [{"id": "HUMAN_APPROVAL", "dischargedBy": "EXTERNAL"}],
    }
    z_ok, _ = verifier.verify_memskill(body)
    runtime, _ = execute_trace(body, observed_external=["HUMAN_APPROVAL"])
    assert correspondence(z_ok, runtime)["interpretation"] == "conservative_rejection"
    led = CleanRoomLedger(tmp_path / "led")
    led.append("trace", {"what": "runtime safe", "why": "external attestation observed", "failed": False})
    store = CheckpointStore(tmp_path / "ckpt")
    store.save(
        PipelineCheckpoint(
            pipeline_id="restart-1",
            next_index=1,
            status="RUNNING",
            state={"attestation": "HUMAN_APPROVAL"},
            ledger_tip=led.tip_hash,
        )
    )
    restored = store.load("restart-1")
    assert restored.state["attestation"] == "HUMAN_APPROVAL"
    assert restored.ledger_tip == led.tip_hash
    replay = list(led.iter_entries())
    assert replay[0].payload["what"] == "runtime safe"


def test_conflicting_evidence_and_corrupted_skill_paths(tmp_path):
    from memory_lifecycle import LifecycleMemory, MemoryIntegrityError

    mem = LifecycleMemory()
    mem.store("skill", {"status": "current"}, "evidence", {"src": "run"})
    mem.contradict("skill", {"status": "denied"}, "inference", {"src": "other"})
    assert mem.conflicts("skill")
    mem.corrupt(1)
    with pytest.raises(MemoryIntegrityError):
        mem.replay()

#!/usr/bin/env python3
"""Integration tests for CleanRoomDaemon autonomous offline cycles."""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_daemon import CleanRoomDaemon, SovereignTask  # noqa: E402
from clean_room_orchestrator import PipelineStep  # noqa: E402
from clean_room_ledger import CheckpointStore, PipelineCheckpoint  # noqa: E402
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
    }


def _h_bind(engine, gate, state, idx):
    engine.touch("EPISODIC")
    state.setdefault("telemetry", {})["phase"] = "bind"
    return {"stage": "bind", "ok": True}


def _h_enrich(engine, gate, state, idx):
    prev = state.get("last_output") or {}
    if prev.get("stage") != "bind":
        raise RuntimeError("missing handoff")
    engine.touch("SEMANTIC")
    state["telemetry"]["phase"] = "enrich"
    return {"stage": "enrich", "ok": True, "chained": True}


def test_end_to_end_autonomous_cycle() -> None:
    sk, vk = generate_keypair()
    with tempfile.TemporaryDirectory() as tmp:
        daemon = CleanRoomDaemon(tmp, trusted_verify_keys=[vk], persist_engine=True)
        task = SovereignTask(
            task_id="cycle-1",
            description="bind then enrich",
            steps=[
                PipelineStep(package=sign_package(_pkg("bind"), sk), handler=_h_bind),
                PipelineStep(package=sign_package(_pkg("enrich"), sk), handler=_h_enrich),
            ],
            initial_state={"note": "daemon-memory"},
        )
        report = daemon.run_task(task)
        assert report.status == "PASS", report.error
        assert report.steps_executed == 2
        assert report.resumed is False
        chain = daemon.verify_audit_integrity()
        assert chain["ok"] is True, chain
        assert daemon.engine.verify_jump_start_integrity()
        print("[OK] end-to-end autonomous cycle")


def test_mid_execution_crash_recovery() -> None:
    """Simulate crash after step 0: checkpoint RUNNING next_index=1, then resume."""
    sk, vk = generate_keypair()
    with tempfile.TemporaryDirectory() as tmp:
        daemon = CleanRoomDaemon(tmp, trusted_verify_keys=[vk], persist_engine=True)
        p_bind = sign_package(_pkg("bind"), sk)
        p_enrich = sign_package(_pkg("enrich"), sk)
        task = SovereignTask(
            task_id="recover-1",
            steps=[
                PipelineStep(package=p_bind, handler=_h_bind, name="bind"),
                PipelineStep(package=p_enrich, handler=_h_enrich, name="enrich"),
            ],
        )

        # Manual partial progress: run only first step via orchestrator, write checkpoint
        daemon._engine_bootstrap()
        partial = daemon.orchestrator.run(
            [PipelineStep(package=p_bind, handler=_h_bind, name="bind")],
            initial_state={},
        )
        assert partial.status == "PASS"
        daemon.ledger.record_pipeline_start("recover-1", 2)
        daemon.ledger.record_step(
            "recover-1", 0, "bind", "PASS", True,
            telemetry_snapshot=dict(partial.state.get("telemetry") or {}),
        )
        daemon._save_checkpoint(
            "recover-1",
            1,
            "RUNNING",
            partial.state,
            partial.steps,
        )
        daemon._persist_engine()

        # New daemon instance = process restart
        daemon2 = CleanRoomDaemon(tmp, trusted_verify_keys=[vk], persist_engine=True)
        report = daemon2.run_task(task, resume=True)
        assert report.status == "PASS", report.error
        assert report.resumed is True
        assert report.steps_executed == 1  # only remaining enrich
        assert daemon2.verify_audit_integrity()["ok"] is True
        print("[OK] mid-execution crash recovery")


def test_security_violation_aborts() -> None:
    sk, vk = generate_keypair()
    with tempfile.TemporaryDirectory() as tmp:
        daemon = CleanRoomDaemon(tmp, trusted_verify_keys=[vk])
        illegal = sign_package(_pkg("net", network=True), sk)
        task = SovereignTask(
            task_id="sec-1",
            steps=[
                PipelineStep(
                    package=sign_package(_pkg("bind"), sk),
                    handler=_h_bind,
                ),
                PipelineStep(package=illegal, handler=_h_enrich),
            ],
        )
        report = daemon.run_task(task)
        assert report.status == "FAIL"
        assert report.aborted_at == 1
        assert report.error and "network" in report.error.lower()
        assert daemon.verify_audit_integrity()["ok"] is True
        print("[OK] security violation aborts pipeline")


def test_corrupt_checkpoint_refuses_resume() -> None:
    sk, vk = generate_keypair()
    with tempfile.TemporaryDirectory() as tmp:
        daemon = CleanRoomDaemon(tmp, trusted_verify_keys=[vk])
        store = CheckpointStore(Path(tmp) / "checkpoints")
        ckpt = PipelineCheckpoint(
            pipeline_id="bad-1",
            next_index=1,
            status="RUNNING",
            state={},
            completed_steps=[],
        )
        path = store.save(ckpt)
        raw = path.read_text(encoding="utf-8")
        # Break hash without updating checkpoint_hash correctly
        path.write_text(raw.replace('"next_index": 1', '"next_index": 2'), encoding="utf-8")

        task = SovereignTask(
            task_id="bad-1",
            steps=[
                PipelineStep(package=sign_package(_pkg("bind"), sk), handler=_h_bind),
            ],
        )
        try:
            daemon.run_task(task, resume=True)
            raise AssertionError("expected RuntimeError")
        except RuntimeError as e:
            assert "checkpoint" in str(e).lower() or "integrity" in str(e).lower()
        print("[OK] corrupt checkpoint refuses resume")


def test_unsigned_skill_aborts() -> None:
    _sk, vk = generate_keypair()
    with tempfile.TemporaryDirectory() as tmp:
        daemon = CleanRoomDaemon(tmp, trusted_verify_keys=[vk])
        task = SovereignTask(
            task_id="unsigned-1",
            steps=[
                PipelineStep(package=_pkg("bind"), handler=_h_bind),
            ],
        )
        report = daemon.run_task(task)
        assert report.status == "FAIL"
        assert report.aborted_at == 0
        print("[OK] unsigned skill aborts")


if __name__ == "__main__":
    test_end_to_end_autonomous_cycle()
    test_mid_execution_crash_recovery()
    test_security_violation_aborts()
    test_corrupt_checkpoint_refuses_resume()
    test_unsigned_skill_aborts()
    print("--- AGENT DAEMON TESTS PASSED ---")

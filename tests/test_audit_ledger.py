#!/usr/bin/env python3
"""Tests: hash-chain integrity, tamper detection, checkpoint save/load."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_ledger import (  # noqa: E402
    CleanRoomLedger,
    CheckpointStore,
    PipelineCheckpoint,
    GENESIS_HASH,
)
from clean_room_orchestrator import CleanRoomOrchestrator, PipelineStep  # noqa: E402
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _pkg(skill_id: str = "step_a") -> dict:
    return {
        "manifest": {
            "skill_id": skill_id,
            "version": "1.0.0",
            "signature": "UNSIGNED_DEV_PLACEHOLDER",
            "author": "beyond-repair",
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


def test_hash_chain_continuity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        led = CleanRoomLedger(Path(tmp) / "audit")
        e1 = led.append("pipeline_start", {"pipeline_id": "p1", "step_count": 2})
        e2 = led.record_step(
            "p1", 0, "episodic_bind", "PASS", True, output_summary={"ok": True}
        )
        e3 = led.record_pipeline_end("p1", "PASS")

        assert e1.prev_hash == GENESIS_HASH
        assert e2.prev_hash == e1.entry_hash
        assert e3.prev_hash == e2.entry_hash
        assert e3.entry_hash == led.tip_hash

        report = led.verify_chain()
        assert report["ok"] is True, report
        assert report["entries"] == 3
        print("[OK] hash chain continuity")


def test_tamper_detection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        led = CleanRoomLedger(Path(tmp) / "audit")
        led.append("pipeline_start", {"pipeline_id": "p2"})
        led.record_step("p2", 0, "s1", "PASS", True)
        led.record_pipeline_end("p2", "PASS")

        # Tamper middle line in jsonl
        lines = led.ledger_path.read_text(encoding="utf-8").strip().splitlines()
        mid = json.loads(lines[1])
        mid["payload"]["gate_status"] = "TAMPERED"
        lines[1] = json.dumps(mid)
        led.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report = led.verify_chain()
        assert report["ok"] is False
        assert "mismatch" in (report["error"] or "").lower()
        print("[OK] tampering detected")


def test_checkpoint_integrity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = CheckpointStore(Path(tmp) / "ckpt")
        ckpt = PipelineCheckpoint(
            pipeline_id="pipe-42",
            next_index=1,
            status="RUNNING",
            state={"last_output": {"stage": "bind"}, "telemetry": {"x": 1}},
            completed_steps=[{"index": 0, "skill_id": "episodic_bind", "status": "PASS"}],
            ledger_tip="abc123",
        )
        path = store.save(ckpt)
        assert path.is_file()

        loaded = store.load("pipe-42", verify=True)
        assert loaded.next_index == 1
        assert loaded.state["telemetry"]["x"] == 1

        # Tamper file
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["next_index"] = 99
        path.write_text(json.dumps(raw), encoding="utf-8")
        try:
            store.load("pipe-42", verify=True)
            raise AssertionError("expected integrity failure")
        except ValueError as e:
            assert "integrity" in str(e).lower() or "hash" in str(e).lower()
        print("[OK] checkpoint save/load + tamper reject")


def test_orchestrator_ledger_integration() -> None:
    """Pipeline steps recorded; chain verifies after run."""
    sk, vk = generate_keypair()

    def h1(engine, gate, state, idx):
        state.setdefault("telemetry", {})["n"] = 1
        return {"stage": "a", "v": 1}

    def h2(engine, gate, state, idx):
        assert state.get("last_output", {}).get("stage") == "a"
        state["telemetry"]["n"] = 2
        return {"stage": "b", "v": 2}

    with tempfile.TemporaryDirectory() as tmp:
        led = CleanRoomLedger(Path(tmp) / "audit")
        orch = CleanRoomOrchestrator(trusted_verify_keys=[vk])
        p1 = sign_package(_pkg("a"), sk)
        p2 = sign_package(_pkg("b"), sk)

        led.record_pipeline_start("int-1", 2)
        result = orch.run(
            [
                PipelineStep(package=p1, handler=h1, name="a"),
                PipelineStep(package=p2, handler=h2, name="b"),
            ]
        )
        for step in result.steps:
            led.record_step(
                "int-1",
                step["index"],
                step["skill_id"],
                step["gate_status"],
                signature_ok=(step["gate_status"] == "PASS"),
                error=step.get("error"),
                output_summary={"keys": list((step.get("output") or {}).keys())}
                if isinstance(step.get("output"), dict)
                else {},
                telemetry_snapshot=dict(result.state.get("telemetry") or {}),
            )
        led.record_pipeline_end(
            "int-1", result.status, result.aborted_at, result.error
        )

        assert result.status == "PASS"
        report = led.verify_chain()
        assert report["ok"] is True, report
        assert report["entries"] >= 4  # start + 2 steps + end

        # Checkpoint mid-state shape
        store = CheckpointStore(Path(tmp) / "ckpt")
        ckpt = PipelineCheckpoint(
            pipeline_id="int-1",
            next_index=2,
            status=result.status,
            state=result.state,
            completed_steps=result.steps,
            ledger_tip=led.tip_hash,
        )
        store.save(ckpt)
        restored = store.load("int-1")
        assert restored.ledger_tip == led.tip_hash
        print("[OK] orchestrator + ledger + checkpoint integration")


if __name__ == "__main__":
    test_hash_chain_continuity()
    test_tamper_detection()
    test_checkpoint_integrity()
    test_orchestrator_ledger_integration()
    print("--- AUDIT LEDGER TESTS PASSED ---")

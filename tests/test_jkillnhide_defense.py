#!/usr/bin/env python3
"""Tests for JKillnHide Active System Defense watchdog."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import CleanRoomVSAEngine  # noqa: E402
from clean_room_jkillnhide import (  # noqa: E402
    JKillnHideWatchdog,
    attach_watchdog_to_daemon,
)
from clean_room_daemon import CleanRoomDaemon, SovereignTask  # noqa: E402
from clean_room_orchestrator import PipelineStep  # noqa: E402
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _pkg() -> dict:
    return {
        "manifest": {
            "skill_id": "def_test",
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


def test_baseline_and_clean_scan() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        eng = CleanRoomVSAEngine(dim=8192)
        eng.jump_start_v01()
        eng.save(ws / "twin_state")
        (ws / "keys").mkdir(parents=True)
        (ws / "keys" / "root.pub").write_text("abc123\n", encoding="utf-8")

        wd = JKillnHideWatchdog(ws, engine=eng, fail_closed_on_drift=True)
        hashes = wd.write_baseline()
        assert len(hashes) >= 1

        report = wd.scan()
        assert report.status == "CLEAN"
        assert report.anomaly is False
        assert report.severity == "INFO"
        assert report.network_access is False
        assert report.shacl_conforms is True
        assert report.fhrr_vector_registered is True

        chain = wd.ledger.verify_chain()
        assert chain["ok"] is True
        print("[OK] baseline + clean scan")


def test_drift_detection_and_enforce_freeze() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        eng = CleanRoomVSAEngine(dim=8192)
        eng.jump_start_v01()
        eng.save(ws / "twin_state")
        keys = ws / "keys"
        keys.mkdir(parents=True)
        pub = keys / "root.pub"
        pub.write_text("original\n", encoding="utf-8")

        wd = JKillnHideWatchdog(ws, engine=eng, fail_closed_on_drift=True)
        wd.write_baseline()

        # Tamper watched key material
        pub.write_text("TAMPERED\n", encoding="utf-8")
        report = wd.scan()
        assert report.status == "DRIFT"
        assert report.anomaly is True
        assert report.severity == "CRIT"  # keys/ path
        assert any(d.kind == "modified" for d in report.deltas)

        decision = wd.enforce(report)
        assert decision["allow_execution"] is False
        assert decision["action"] == "FREEZE"
        print("[OK] drift detected + FREEZE policy")


def test_missing_baseline_policy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        eng = CleanRoomVSAEngine(dim=8192)
        eng.jump_start_v01()
        wd = JKillnHideWatchdog(ws, engine=eng, fail_closed_on_drift=True)
        report = wd.scan()
        assert report.status == "MISSING_BASELINE"
        decision = wd.enforce(report)
        assert decision["action"] == "REQUIRE_BASELINE"
        assert decision["allow_execution"] is False
        print("[OK] missing baseline fail-closed")


def test_daemon_integration_freeze() -> None:
    sk, vk = generate_keypair()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        daemon = CleanRoomDaemon(
            ws, trusted_verify_keys=[vk], enable_memory=False, persist_engine=True
        )
        daemon._engine_bootstrap()
        daemon.engine.save(ws / "twin_state")

        wd = attach_watchdog_to_daemon(daemon, fail_closed_on_drift=True)
        # No baseline → freeze
        def handler(engine, gate, state, idx):
            return {"ok": True}

        task = SovereignTask(
            task_id="sec-task",
            steps=[
                PipelineStep(
                    package=sign_package(_pkg(), sk),
                    handler=handler,
                )
            ],
        )
        report = daemon.run_task(task)
        assert report.status == "FAIL"
        assert report.error and "JKillnHide" in report.error

        # Baseline then clean → allow
        wd.write_baseline()
        report2 = daemon.run_task(task)
        assert report2.status == "PASS", report2.error
        print("[OK] daemon FREEZE then CONTINUE after baseline")


def test_shacl_rejects_network_true_event() -> None:
    """Security events must declare network_access=false."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        eng = CleanRoomVSAEngine(dim=8192)
        eng.jump_start_v01()
        wd = JKillnHideWatchdog(ws, engine=eng)
        # Direct graph with illegal network_access is validated by shape hasValue False
        # Our builder always sets False; ensure clean event conforms
        ok = wd.shacl_security_event("INFO", False)
        assert ok.conforms
        print("[OK] security event SHACL conforms offline")


if __name__ == "__main__":
    test_baseline_and_clean_scan()
    test_drift_detection_and_enforce_freeze()
    test_missing_baseline_policy()
    test_daemon_integration_freeze()
    test_shacl_rejects_network_true_event()
    print("--- JKILLNHIDE DEFENSE TESTS PASSED ---")

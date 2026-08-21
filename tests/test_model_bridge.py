#!/usr/bin/env python3
"""Tests for LocalModelBridge — offline inference routing + constraints."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_model import (  # noqa: E402
    ContextInjector,
    DeterministicLocalBackend,
    LocalHttpBackend,
    LocalModelBridge,
    assert_loopback_url,
    parse_status_line,
    skill_handler_factory,
)
from clean_room_shacl import ShapeEngine, CONSTITUTIONAL_SHAPES, skill_package_to_graph  # noqa: E402
from clean_room_daemon import CleanRoomDaemon, SovereignTask  # noqa: E402
from clean_room_orchestrator import PipelineStep  # noqa: E402
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _pkg(skill_id: str = "local_model") -> dict:
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


def test_loopback_guard() -> None:
    assert_loopback_url("http://127.0.0.1:8080")
    assert_loopback_url("http://localhost:11434/api")
    try:
        assert_loopback_url("http://example.com:8080")
        raise AssertionError("should reject remote host")
    except PermissionError:
        pass
    try:
        LocalHttpBackend(base_url="http://8.8.8.8:8080")
        raise AssertionError("should reject")
    except PermissionError:
        pass
    print("[OK] loopback-only endpoint guard")


def test_deterministic_prompt_formatting() -> None:
    inj = ContextInjector()
    hits = [{"episode_id": "e1", "similarity": 0.95, "meta": {"k": 1}}]
    shacl = {"conforms": True, "shape_id": "SkillPackageSovereigntyShape", "violations": []}
    req = inj.build("do the thing", memory_hits=hits, shacl_report=shacl)
    assert "## Task" in req.prompt
    assert "do the thing" in req.prompt
    assert "e1" in req.prompt
    assert "0.9500" in req.prompt or "0.95" in req.prompt
    assert "conforms: True" in req.prompt
    assert req.meta.get("network_access") is False
    # Deterministic: same inputs → same prompt
    req2 = inj.build("do the thing", memory_hits=hits, shacl_report=shacl)
    assert req.prompt == req2.prompt
    print("[OK] deterministic prompt formatting")


def test_offline_inference_and_status_parse() -> None:
    bridge = LocalModelBridge(backend=DeterministicLocalBackend())
    out = bridge.reason(
        "summarize local state",
        memory_hits=[{"episode_id": "x", "similarity": 0.99, "meta": {}}],
    )
    assert out["offline"] is True
    assert out["network_access"] is False
    assert out["status"] in ("PASS", "FAIL")
    assert out["shacl_conforms"] is True
    assert parse_status_line(out["text"]) == "PASS"
    print("[OK] offline deterministic inference + SHACL output")


def test_output_fail_closed_without_status() -> None:
    class BadBackend:
        name = "bad"

        def generate(self, request):
            from clean_room_model import InferenceResult

            return InferenceResult(text="no status line here", backend=self.name, offline=True)

    bridge = LocalModelBridge(backend=BadBackend())
    out = bridge.reason("x")
    assert out["status"] == "FAIL"  # fail closed
    print("[OK] missing STATUS fails closed")


def test_daemon_with_model_skill() -> None:
    sk, vk = generate_keypair()
    bridge = LocalModelBridge(backend=DeterministicLocalBackend())
    handler = skill_handler_factory(bridge)

    with tempfile.TemporaryDirectory() as tmp:
        daemon = CleanRoomDaemon(tmp, trusted_verify_keys=[vk], enable_memory=True)
        daemon._engine_bootstrap()
        if daemon.memory:
            daemon.memory.remember("prior local fact about quartz", meta={"k": "v"})

        task = SovereignTask(
            task_id="model-1",
            description="local reason",
            steps=[
                PipelineStep(
                    package=sign_package(_pkg("local_model"), sk),
                    handler=handler,
                    name="local_model",
                )
            ],
            initial_state={
                "note": "prior local fact about quartz",
                "task": "reason offline about prior fact",
            },
            remember_on_pass=True,
        )
        report = daemon.run_task(task)
        assert report.status == "PASS", report.error
        print("[OK] daemon + local model skill")


def test_shacl_package_still_required() -> None:
    eng = ShapeEngine(CONSTITUTIONAL_SHAPES)
    bad = {
        "sovereignty": {"network_access": True},
        "vsa_bindings": {"dimension": 8192},
    }
    report = eng.validate_graph(skill_package_to_graph(bad), "SkillPackageSovereigntyShape")
    assert not report.conforms
    print("[OK] model skills still subject to package SHACL")


if __name__ == "__main__":
    test_loopback_guard()
    test_deterministic_prompt_formatting()
    test_offline_inference_and_status_parse()
    test_output_fail_closed_without_status()
    test_daemon_with_model_skill()
    test_shacl_package_still_required()
    print("--- MODEL BRIDGE TESTS PASSED ---")

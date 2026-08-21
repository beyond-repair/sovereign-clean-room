#!/usr/bin/env python3
"""Tests for Hyperdimensional Episodic Memory Store + daemon integration."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import CleanRoomVSAEngine  # noqa: E402
from clean_room_memory import EpisodicMemoryStore  # noqa: E402
from clean_room_daemon import CleanRoomDaemon, SovereignTask  # noqa: E402
from clean_room_orchestrator import PipelineStep  # noqa: E402
from skill_crypto import generate_keypair, sign_package  # noqa: E402


def _pkg(skill_id: str = "mem_skill") -> dict:
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


def test_remember_and_exact_recall() -> None:
    eng = CleanRoomVSAEngine(dim=8192)
    eng.jump_start_v01()
    with tempfile.TemporaryDirectory() as tmp:
        store = EpisodicMemoryStore(tmp, engine=eng, tau=0.92)
        text = "sovereign offline episodic trace alpha"
        eid = store.remember(text, meta={"tag": "alpha"})
        hits = store.recall(text, top_k=3)
        assert hits, "expected at least one hit"
        assert hits[0].episode_id == eid
        assert hits[0].similarity >= 0.92
        score, ok = store.unbind_probe(eid, text)
        assert ok, score
        print(f"[OK] exact recall sim={hits[0].similarity:.6f} unbind={score:.6f}")


def test_persistence_across_restart() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        eng = CleanRoomVSAEngine(dim=8192)
        eng.jump_start_v01()
        store = EpisodicMemoryStore(tmp, engine=eng)
        text = "multi-session memory beta"
        eid = store.remember(text)

        eng2 = CleanRoomVSAEngine(dim=8192)
        eng2.jump_start_v01()
        store2 = EpisodicMemoryStore(tmp, engine=eng2)
        assert eid in store2.list_episodes()
        hit = store2.best_match(text)
        assert hit is not None
        assert hit.similarity >= 0.92
        print("[OK] persistence across store restart")


def test_unrelated_query_below_tau() -> None:
    eng = CleanRoomVSAEngine(dim=8192)
    eng.jump_start_v01()
    with tempfile.TemporaryDirectory() as tmp:
        store = EpisodicMemoryStore(tmp, engine=eng, tau=0.92)
        store.remember("completely unique phrase about cedar and quartz")
        hits = store.recall("zzzz totally different xy-9 quantum cabbage", top_k=5)
        # Deterministic unrelated strings should not meet τ=0.92 against bound episode
        assert all(h.similarity < 0.92 for h in hits) or len(hits) == 0
        print("[OK] unrelated query does not false-pass tau")


def test_bundle_superposition() -> None:
    eng = CleanRoomVSAEngine(dim=8192)
    eng.jump_start_v01()
    with tempfile.TemporaryDirectory() as tmp:
        store = EpisodicMemoryStore(tmp, engine=eng)
        e1 = store.remember("bundle member one")
        e2 = store.remember("bundle member two")
        bid = store.bundle_episodes([e1, e2])
        assert bid in store.manifest["bundles"]
        print("[OK] holographic bundle created")


def test_daemon_memory_integration() -> None:
    sk, vk = generate_keypair()

    def handler(engine, gate, state, idx):
        # Skill can see prior memory_hits injected by daemon
        hits = state.get("memory_hits") or []
        state.setdefault("telemetry", {})["saw_hits"] = len(hits)
        return {"stage": "work", "hits": len(hits)}

    with tempfile.TemporaryDirectory() as tmp:
        daemon = CleanRoomDaemon(
            tmp,
            trusted_verify_keys=[vk],
            enable_memory=True,
            memory_tau=0.92,
        )
        # Seed memory before task
        assert daemon.memory is not None
        daemon._engine_bootstrap()
        seed_text = "daemon-memory-seed-gamma"
        daemon.memory.remember(seed_text, meta={"seed": True})

        task = SovereignTask(
            task_id="mem-task-1",
            description="use memory",
            steps=[
                PipelineStep(
                    package=sign_package(_pkg("work"), sk),
                    handler=handler,
                )
            ],
            initial_state={"note": seed_text},
            remember_on_pass=True,
        )
        report = daemon.run_task(task)
        assert report.status == "PASS", report.error
        assert report.memory_episode_id is not None

        # New daemon process — recall still works
        daemon2 = CleanRoomDaemon(tmp, trusted_verify_keys=[vk], enable_memory=True)
        daemon2._engine_bootstrap()
        assert daemon2.memory is not None
        hit = daemon2.memory.best_match(seed_text)
        assert hit is not None and hit.similarity >= 0.92
        print("[OK] daemon memory integration + multi-session recall")


if __name__ == "__main__":
    test_remember_and_exact_recall()
    test_persistence_across_restart()
    test_unrelated_query_below_tau()
    test_bundle_superposition()
    test_daemon_memory_integration()
    print("--- MEMORY STORE TESTS PASSED ---")

"""Memory lifecycle: evidence stays distinct from inference."""

from __future__ import annotations

import pytest

from memory_lifecycle import LifecycleMemory, MemoryIntegrityError


def test_lifecycle_does_not_rewrite_history():
    mem = LifecycleMemory()
    prov = {"source": "trial", "observer": "phase0"}
    mem.store("route-a", {"outcome": "fail"}, "evidence", prov, status="failed")
    mem.reinforce("route-a", prov)
    mem.contradict("route-a", {"outcome": "success"}, "inference", {"source": "guess"})
    mem.supersede("route-a", {"outcome": "alternate"}, "evidence", prov)
    current = mem.current("route-a")
    assert current["payload"]["value"]["outcome"] == "alternate"
    history = mem.history("route-a")
    assert [rec["kind"] for rec in history] == ["store", "reinforce", "contradict", "supersede"]
    assert history[0]["payload"]["value"]["outcome"] == "fail"
    assert history[0]["record_class"] == "evidence"
    assert history[2]["record_class"] == "inference"
    assert mem.conflicts("route-a")
    failed = [rec for rec in mem.history("route-a") if rec["payload"].get("status") == "failed" or rec["kind"] == "store"]
    assert failed[0]["payload"]["value"]["outcome"] == "fail"
    mem.invalidate("route-a", prov)
    assert mem.current("route-a") is None
    assert any(rec["kind"] == "invalidate" for rec in mem.history("route-a"))
    replayed = mem.replay()
    assert [rec["seq"] for rec in replayed] == list(range(1, 6))
    mem.corrupt(2)
    with pytest.raises(MemoryIntegrityError):
        mem.verify()

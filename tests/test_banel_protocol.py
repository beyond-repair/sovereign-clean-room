"""BaNEL groups, route-level FRR, Micro-Dream. Not a hypothesis claim."""

from __future__ import annotations

import time

from banel_protocol import RouteSession, delta_frr_curves, frr_at, frr_curve


def _session(group, seed=1, n=40):
    failing = list(range(8))  # 8 of 10 routes fail
    session = RouteSession(n_routes=10, failing=failing, group=group, seed=seed, alpha=1.0)
    session.run(n)
    return session


def test_groups_and_route_level_frr():
    sessions = {g: _session(g) for g in ("A", "B", "C", "D")}
    curves = {g: frr_curve(s.prior_fail_counts, ns=(1, 2)) for g, s in sessions.items()}
    for g, curve in curves.items():
        assert [row["n"] for row in curve] == [1, 2]
        for row in curve:
            assert 0.0 <= row["frr"] <= 1.0
    delta = delta_frr_curves(curves["A"], curves["C"])
    assert [row["n"] for row in delta] == [1, 2]
    # Group D must not attribute the failure to the route that failed.
    for ev in sessions["D"].events:
        assert ev.assigned_to != ev.route
    for ev in sessions["C"].events:
        assert ev.assigned_to == ev.route


def test_repeated_failures_alternative_routes_and_supersession(tmp_path):
    session = RouteSession(n_routes=4, failing=[0], group="C", seed=2)
    session.run(5)
    assert any(s != 0 for s in session.selections) or session.structured_counts()[0] >= 1
    dream = session.dreams[-1]
    assert dream["fabricated"] is False
    assert 0 not in dream["candidates"] or session.structured_counts()[0] == 0
    assert all(c in range(4) for c in dream["candidates"])
    evidence_id = session.events[0].evidence_id
    before = session.structured_counts()[0]
    assert session.supersede_evidence(evidence_id) is True
    assert session.structured_counts()[0] == before - 1
    assert any(ev.evidence_id == evidence_id and ev.superseded for ev in session.events)
    path = tmp_path / "session.json"
    session.save(path)
    loaded = RouteSession.load(path)
    assert loaded.selections == session.selections
    assert loaded.events[0].superseded is True


def test_micro_dream_latency_is_measured():
    session = RouteSession(n_routes=5, failing=[1], group="C", seed=0)
    started = time.perf_counter()
    dream = session.micro_dream()
    elapsed = (time.perf_counter() - started) * 1000.0
    assert dream["latency_ms"] >= 0.0
    assert dream["latency_ms"] < 100.0
    assert elapsed < 100.0
    assert dream["gate"] == "pass"


def test_frr_zero_denominator_and_n0():
    assert frr_at([], 1) != frr_at([], 1)  # NaN
    assert frr_at([0, 0, 1], 0) == 0.0
    assert frr_at([0, 1, 1], 1) == 2 / 3

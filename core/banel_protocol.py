#!/usr/bin/env python3
"""Phase III route simulator for the locked group definitions.

Suppression weights are an implementation choice, not the blank source
equation from the superseded draft. The choice is recorded in the config:

    Group A: uniform, failures discarded
    Group B: weight grows with successes only
    Group C: weight = 1 / (1 + alpha * structured_fail_count)
    Group D: failure events are retained but the count is added to a
             route drawn from the trial RNG, not the route that failed

FRR(n) uses the locked ratio. n is the failure count of the selected
route before that selection. The numerator counts selections whose prior
count equals n (a repeated failed-route selection when n >= 1).
The denominator is every selection in the session.

Micro-Dream proposes only routes already present in the route table and
not currently carrying structured failure evidence. It does not invent
evidence or route identifiers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


@dataclass
class FailureEvent:
    route: int
    assigned_to: int
    superseded: bool = False
    evidence_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route,
            "assigned_to": self.assigned_to,
            "superseded": self.superseded,
            "evidence_id": self.evidence_id,
        }


@dataclass
class RouteSession:
    n_routes: int
    failing: Sequence[int]
    group: str
    alpha: float = 1.0
    seed: int = 0
    successes: List[int] = field(default_factory=list)
    events: List[FailureEvent] = field(default_factory=list)
    selections: List[int] = field(default_factory=list)
    prior_fail_counts: List[int] = field(default_factory=list)
    dreams: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.successes = [0] * self.n_routes
        self._rng = np.random.default_rng(self.seed)
        self.failing_set = set(int(x) for x in self.failing)

    def structured_counts(self) -> List[int]:
        counts = [0] * self.n_routes
        for ev in self.events:
            if ev.superseded:
                continue
            if self.group == "C":
                counts[ev.assigned_to] += 1
            elif self.group == "D":
                counts[ev.assigned_to] += 1
        return counts

    def weights(self) -> np.ndarray:
        counts = self.structured_counts()
        if self.group == "A":
            w = np.ones(self.n_routes, dtype=np.float64)
        elif self.group == "B":
            w = np.asarray([1.0 + s for s in self.successes], dtype=np.float64)
        elif self.group == "C":
            w = np.asarray([1.0 / (1.0 + self.alpha * c) for c in counts], dtype=np.float64)
        elif self.group == "D":
            w = np.asarray([1.0 / (1.0 + self.alpha * c) for c in counts], dtype=np.float64)
        else:
            raise ValueError(f"unknown group {self.group}")
        total = float(w.sum())
        if total <= 0:
            raise RuntimeError("route weights vanished")
        return w / total

    def micro_dream(self) -> Dict[str, Any]:
        """Candidates from current evidence only. Latency is a clock measurement."""
        started = time.perf_counter()
        counts = self.structured_counts()
        evidence_ids = [ev.evidence_id for ev in self.events if not ev.superseded]
        candidates = [i for i in range(self.n_routes) if counts[i] == 0]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        dream = {
            "candidates": candidates,
            "evidence_ids": evidence_ids,
            "fabricated": False,
            "latency_ms": elapsed_ms,
            "gate": "fail" if elapsed_ms > 100.0 else "pass",
        }
        self.dreams.append(dream)
        return dream

    def step(self) -> int:
        probs = self.weights()
        choice = int(self._rng.choice(self.n_routes, p=probs))
        prior = 0
        if self.group in ("C", "D"):
            prior = self.structured_counts()[choice]
        elif self.group == "A":
            prior = 0
        else:
            # Group B does not store failures, so the prior failure count
            # used by FRR is zero. Success memory is not failure evidence.
            prior = 0
        self.selections.append(choice)
        self.prior_fail_counts.append(int(prior))
        if choice in self.failing_set:
            if self.group == "A" or self.group == "B":
                pass
            elif self.group == "C":
                ev = FailureEvent(
                    route=choice,
                    assigned_to=choice,
                    evidence_id=f"fail-{len(self.events)}-route-{choice}",
                )
                self.events.append(ev)
                self.micro_dream()
            elif self.group == "D":
                others = [i for i in range(self.n_routes) if i != choice]
                assigned = int(self._rng.choice(others))
                ev = FailureEvent(
                    route=choice,
                    assigned_to=assigned,
                    evidence_id=f"fail-{len(self.events)}-route-{choice}-to-{assigned}",
                )
                self.events.append(ev)
        else:
            self.successes[choice] += 1
        return choice

    def run(self, n_selections: int) -> None:
        for _ in range(n_selections):
            self.step()

    def supersede_evidence(self, evidence_id: str) -> bool:
        """Keep the event. It no longer contributes to the current count."""
        for ev in self.events:
            if ev.evidence_id == evidence_id and not ev.superseded:
                ev.superseded = True
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_routes": self.n_routes,
            "failing": sorted(self.failing_set),
            "group": self.group,
            "alpha": self.alpha,
            "seed": self.seed,
            "successes": self.successes,
            "events": [ev.to_dict() for ev in self.events],
            "selections": self.selections,
            "prior_fail_counts": self.prior_fail_counts,
        }

    def save(self, path: str) -> None:
        from pathlib import Path
        Path(path).write_text(json.dumps(self.to_dict(), sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "RouteSession":
        from pathlib import Path
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        session = cls(
            n_routes=int(raw["n_routes"]),
            failing=raw["failing"],
            group=str(raw["group"]),
            alpha=float(raw["alpha"]),
            seed=int(raw["seed"]),
        )
        session.successes = list(raw["successes"])
        session.events = [FailureEvent(**ev) for ev in raw["events"]]
        session.selections = list(raw["selections"])
        session.prior_fail_counts = list(raw["prior_fail_counts"])
        return session


def frr_at(prior_counts: Sequence[int], n: int) -> float:
    total = len(prior_counts)
    if total == 0:
        return float("nan")
    if n < 0:
        raise ValueError("n must be non-negative")
    # n == 0 is not a repeated failure. The locked numerator is repeated
    # failed-route selections, so the n == 0 bucket contributes 0.
    if n == 0:
        return 0.0
    hits = sum(1 for c in prior_counts if c == n)
    return hits / total


def frr_curve(prior_counts: Sequence[int], ns: Sequence[int] = (1, 2)) -> List[Dict[str, float]]:
    return [{"n": int(n), "frr": frr_at(prior_counts, int(n))} for n in ns]


def delta_frr_curves(baseline: Sequence[Dict[str, float]], treatment: Sequence[Dict[str, float]]) -> List[Dict[str, float]]:
    out = []
    for b, t in zip(baseline, treatment):
        if int(b["n"]) != int(t["n"]):
            raise ValueError("curve n mismatch")
        out.append({"n": int(b["n"]), "delta_frr": float(b["frr"]) - float(t["frr"])})
    return out

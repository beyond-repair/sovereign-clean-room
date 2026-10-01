#!/usr/bin/env python3
"""Locked Phase I metrics for SEEM validation protocol v1.0.

Normative invertibility, for unit-magnitude phasors:

    I(a, â) = (1/d) * Σ cos(φ_a,j - φ_â,j)

Canonical projection is component-wise phasor projection, not vector L2
normalization. A zero component is a fault, not phase 0.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np


def phasor_project(v: np.ndarray) -> tuple[np.ndarray, int]:
    """Project each component onto the unit circle.

    Returns (projected, fault_count). Faults are components with modulus 0.
    Those positions are left at 0 and must be excluded by the caller.
    """
    z = np.asarray(v, dtype=np.complex128)
    mod = np.abs(z)
    faults = int(np.count_nonzero(mod == 0))
    out = np.zeros_like(z)
    ok = mod != 0
    out[ok] = z[ok] / mod[ok]
    return out, faults


def invertibility(a: np.ndarray, a_hat: np.ndarray) -> float:
    """Locked cosine-sum invertibility. Both inputs must be unit phasors."""
    left = np.asarray(a, dtype=np.complex128)
    right = np.asarray(a_hat, dtype=np.complex128)
    if left.shape != right.shape:
        raise ValueError("invertibility vectors must share a shape")
    if left.size == 0:
        raise ValueError("empty vector")
    phase_delta = np.angle(left) - np.angle(right)
    return float(np.mean(np.cos(phase_delta)))


def retrieval_hit(recovered: np.ndarray, codebook: Sequence[np.ndarray], target_index: int) -> bool:
    """True when argmax_c I(c, recovered) is the target codebook index."""
    scores = [invertibility(codebook[i], recovered) for i in range(len(codebook))]
    chosen = int(np.argmax(scores))
    return chosen == target_index


def k_max(rows: Iterable[dict], i_floor: float = 0.92, acc_floor: float = 0.95) -> int | None:
    """Largest k whose CI lower bounds clear the locked floors.

    Each row needs keys: k, mean_I_ci_low, accuracy_ci_low.
    Returns None when no k qualifies. Does not invent a zero.
    """
    ok = [
        int(row["k"])
        for row in rows
        if row["mean_I_ci_low"] >= i_floor and row["accuracy_ci_low"] >= acc_floor
    ]
    return max(ok) if ok else None


def scaling_ratio(k_max_control: int | None, k_max_primary: int | None) -> float | None:
    """R_d = k_max(16384) / k_max(8192). None if either capacity is undefined."""
    if not k_max_control or not k_max_primary:
        return None
    return k_max_control / k_max_primary


def frr(repeated_failed_route_selections: int, total_route_selections: int) -> float:
    if total_route_selections < 0 or repeated_failed_route_selections < 0:
        raise ValueError("counts must be non-negative")
    if repeated_failed_route_selections > total_route_selections:
        raise ValueError("repeated selections cannot exceed total selections")
    if total_route_selections == 0:
        return math.nan
    return repeated_failed_route_selections / total_route_selections


def delta_frr(baseline: float, treatment: float) -> float:
    return baseline - treatment

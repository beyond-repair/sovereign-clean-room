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
    bad = (~np.isfinite(mod)) | (mod == 0)
    faults = int(np.count_nonzero(bad))
    out = np.zeros_like(z)
    ok = ~bad
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


def retrieval_decision(
    recovered: np.ndarray, codebook: Sequence[np.ndarray], target_index: int
) -> dict:
    """Argmax retrieval and the hit bit are separate fields.

    The best similarity is recorded so a high score cannot be mistaken for a hit.
    """
    scores = [invertibility(codebook[i], recovered) for i in range(len(codebook))]
    chosen = int(np.argmax(scores))
    return {
        "chosen_index": chosen,
        "retrieval_hit": chosen == target_index,
        "best_I": float(scores[chosen]),
        "target_I": float(scores[target_index]),
    }


def _log_binom_pmf(k: int, n: int, p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0, 1)")
    return (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log(1.0 - p)
    )


def _logsumexp(terms: list[float]) -> float:
    if not terms:
        return float("-inf")
    top = max(terms)
    return top + math.log(sum(math.exp(t - top) for t in terms))


def binomial_cdf(k: int, n: int, p: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    terms = [_log_binom_pmf(i, n, p) for i in range(k + 1)]
    return math.exp(_logsumexp(terms))


def binomial_sf(k: int, n: int, p: float) -> float:
    """P(X >= k)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    terms = [_log_binom_pmf(i, n, p) for i in range(k, n + 1)]
    return math.exp(_logsumexp(terms))


def clopper_pearson(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float] | None:
    """Exact Clopper-Pearson interval via binomial tail inversion.

    lower solves P(X >= successes) = alpha/2.
    upper solves P(X <= successes) = alpha/2.
    """
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("invalid binomial counts")
    if n == 0:
        return None
    tail = alpha / 2.0
    if successes == 0:
        lower = 0.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if binomial_sf(successes, n, mid) > tail:
                hi = mid
            else:
                lo = mid
        lower = 0.5 * (lo + hi)
    if successes == n:
        upper = 1.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            # CDF decreases in p. A CDF above the tail means p is still too small.
            if mid <= 0.0 or mid >= 1.0:
                break
            if binomial_cdf(successes, n, mid) > tail:
                lo = mid
            else:
                hi = mid
        upper = 0.5 * (lo + hi)
    return float(lower), float(upper)


def bootstrap_mean_ci(
    values: Sequence[float],
    seed: int,
    resamples: int = 10000,
) -> tuple[float, float, float] | None:
    """Percentile bootstrap of the mean. None when values is empty."""
    sample = np.asarray(list(values), dtype=np.float64)
    if sample.size == 0:
        return None
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, sample.size, size=(resamples, sample.size))
    means = sample[draws].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(sample.mean()), float(low), float(high)


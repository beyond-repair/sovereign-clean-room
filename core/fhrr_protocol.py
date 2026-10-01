#!/usr/bin/env python3
"""Phase I FHRR runner for SEEM validation protocol v1.0.

This is the locked measurement path. It does not use vector L2 normalization.
The constitution runtime in clean_room_vsa.py remains a unit-hypersphere
algebra and is a different substrate. Benchmark cells must be produced here.

Binding: component-wise complex multiply of unit phasors.
Noise: v' = v + gamma * sum_{j=1}^{N_noise} n_j
Projection: benchmark_metrics.phasor_project. Zero magnitude is a fault.
Invertibility: benchmark_metrics.invertibility.
Retrieval: argmax I, with retrieval_hit recorded separately.

N_noise defaults to 1 because the locked protocol names the sum but does not
fix its length. The value is part of the configuration hash.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from benchmark_metrics import (
    bootstrap_mean_ci,
    clopper_pearson,
    invertibility,
    k_max,
    phasor_project,
    scaling_ratio,
)

PROTOCOL = "SEEM-VALIDATION-v1.0"
T_MAX = 7


def config_sha256(config: Dict[str, Any]) -> str:
    blob = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def sample_phases(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    """phi in (-pi, pi]. Uniform on the circle, exact -pi mapped to pi."""
    u = rng.random((n, d))
    phases = u * (2.0 * math.pi) - math.pi
    phases = np.where(phases <= -math.pi, math.pi, phases)
    return phases


def sample_codebook(m: int, d: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    phases = sample_phases(m, d, rng)
    codebook = np.exp(1j * phases).astype(np.complex128)
    return codebook


def bind_factors(factors: np.ndarray) -> np.ndarray:
    """factors shape (k, d), unit phasors. Component-wise product, no L2."""
    out = np.ones(factors.shape[1], dtype=np.complex128)
    for row in factors:
        out = out * row
    return out


def _argmax_index(codebook: np.ndarray, probe: np.ndarray) -> int:
    scores = np.real(codebook @ np.conjugate(probe)) / codebook.shape[1]
    return int(np.argmax(scores))


def _codebook_cleanup(codebook: np.ndarray, decoded: np.ndarray) -> tuple[np.ndarray, int]:
    """Soft cleanup A Aᴴ then component-wise phasor projection.

    Returns (estimate, fault_count). A zero component is a fault, not phase 0.
    """
    coeffs = codebook.conj() @ decoded
    recon = coeffs @ codebook
    projected, faults = phasor_project(recon)
    return projected, int(faults)


def resonator(
    projected: np.ndarray,
    codebook: np.ndarray,
    k: int,
    rng: np.random.Generator,
    t_max: int = T_MAX,
) -> tuple[list, int, bool, int]:
    """Blind factor resonator. Binding is commutative, so slots are unordered.

    Each factor estimate is initialized to an independent random unit phasor
    from rng, not to a true factor. The update is sequential:
    decode with the other estimates, soft-project through the codebook, then
    phasor-project. Stops when the argmax tuple repeats, else at t_max.

    Returns (estimates, iterations, converged, projection_faults).
    """
    d = codebook.shape[1]
    phases = sample_phases(k, d, rng)
    estimates = [np.exp(1j * phases[i]) for i in range(k)]
    faults = 0
    prev = None
    used = t_max
    converged = False
    for t in range(1, t_max + 1):
        for i in range(k):
            decoded = projected.copy()
            for j in range(k):
                if j == i:
                    continue
                decoded = decoded * np.conjugate(estimates[j])
            cleaned, step_faults = _codebook_cleanup(codebook, decoded)
            faults += step_faults
            if step_faults:
                continue
            estimates[i] = cleaned
        winners = tuple(_argmax_index(codebook, estimates[i]) for i in range(k))
        if winners == prev:
            used = t
            converged = True
            break
        prev = winners
    return estimates, used, converged, faults


def run_trial(
    codebook: np.ndarray,
    k: int,
    gamma: float,
    n_noise: int,
    rng: np.random.Generator,
    t_max: int = T_MAX,
) -> Dict[str, Any]:
    m, d = codebook.shape
    true_idx = rng.choice(m, size=k, replace=False).astype(np.int64)
    bound = bind_factors(codebook[true_idx])
    if gamma == 0 or n_noise == 0:
        noisy = bound
    else:
        pool = np.setdiff1d(np.arange(m), true_idx, assume_unique=False)
        if len(pool) < n_noise:
            raise ValueError("codebook too small for N_noise unbound vectors")
        noise_idx = rng.choice(pool, size=n_noise, replace=False)
        noisy = bound + float(gamma) * codebook[noise_idx].sum(axis=0)
    projected, faults = phasor_project(noisy)
    if faults:
        return {
            "projection_faults": int(faults),
            "excluded": True,
            "I": None,
            "retrieval_hit": None,
            "iterations": None,
            "converged": False,
        }
    estimates, used, converged, res_faults = resonator(projected, codebook, k, rng, t_max=t_max)
    if res_faults:
        return {
            "projection_faults": int(faults + res_faults),
            "excluded": True,
            "I": None,
            "retrieval_hit": None,
            "iterations": None,
            "converged": False,
        }
    target = int(true_idx[0])
    # Commutative binding has no slot identity. Align the recovered estimate
    # to the designated factor by invertibility, then retrieve separately.
    slot_scores = [invertibility(codebook[target], estimates[i]) for i in range(k)]
    slot = int(np.argmax(slot_scores))
    recovered = estimates[slot]
    score = float(slot_scores[slot])
    chosen = _argmax_index(codebook, recovered)
    return {
        "projection_faults": 0,
        "excluded": False,
        "I": score,
        "retrieval_hit": bool(chosen == target),
        "chosen_index": chosen,
        "target_index": target,
        "aligned_slot": slot,
        "iterations": int(used),
        "converged": bool(converged),
    }


def run_cell(
    *,
    d: int,
    k: int,
    gamma: float,
    n_trials: int,
    codebook_seed: int,
    trial_seed: int,
    m: int = 1000,
    n_noise: int = 1,
    t_max: int = T_MAX,
    bootstrap_seed: int = 20260930,
    bootstrap_resamples: int = 10000,
    git_sha: str = "",
) -> Dict[str, Any]:
    config = {
        "protocol": PROTOCOL,
        "d": int(d),
        "k": int(k),
        "gamma": float(gamma),
        "n_trials": int(n_trials),
        "m": int(m),
        "n_noise": int(n_noise),
        "t_max": int(t_max),
        "codebook_seed": int(codebook_seed),
        "trial_seed": int(trial_seed),
        "bootstrap_seed": int(bootstrap_seed),
        "bootstrap_resamples": int(bootstrap_resamples),
        "binding": "component_wise_complex_multiply",
        "projection": "phasor_project",
        "invertibility": "cosine_sum",
        "phase_interval": "(-pi, pi]",
        "resonator_init": "random_unit_phasors_sequential_soft_cleanup",
    }
    digest = config_sha256(config)
    if n_trials <= 0:
        return _envelope(
            config, digest, git_sha, status="not_run", notes="n_trials <= 0",
            trials_completed=0,
        )
    codebook = sample_codebook(m, d, codebook_seed)
    # One stream so a repeated call with the same seeds matches bitwise
    # for the recorded summary. Trial i is a spawned generator.
    parent = np.random.SeedSequence(trial_seed)
    children = parent.spawn(n_trials)
    rows: List[Dict[str, Any]] = []
    faults = 0
    for child in children:
        rng = np.random.default_rng(child)
        row = run_trial(codebook, k, gamma, n_noise, rng, t_max=t_max)
        faults += int(row["projection_faults"])
        rows.append(row)
    usable_I = [r["I"] for r in rows if not r["excluded"]]
    hits = [1 if r["retrieval_hit"] else 0 for r in rows if not r["excluded"]]
    iters = [r["iterations"] for r in rows if not r["excluded"]]
    mean_pack = bootstrap_mean_ci(usable_I, seed=bootstrap_seed, resamples=bootstrap_resamples) if usable_I else None
    acc = (sum(hits) / len(hits)) if hits else None
    cp = clopper_pearson(sum(hits), len(hits)) if hits else None
    median_t = float(np.median(np.asarray(iters, dtype=np.float64))) if iters else None
    full = int(n_trials) == 10000 and int(m) == 1000 and int(d) in (8192, 16384)
    status = "measured" if full else "partial"
    return _envelope(
        config,
        digest,
        git_sha,
        status=status,
        notes=(
            "prefix of the locked grid; N or M or d is not the full protocol cell"
            if status == "partial"
            else "full protocol cell"
        ),
        trials_completed=len(rows),
        mean_I=None if mean_pack is None else mean_pack[0],
        mean_I_ci95=None if mean_pack is None else [mean_pack[1], mean_pack[2]],
        retrieval_accuracy=None if acc is None else float(acc),
        retrieval_accuracy_ci95=None if cp is None else [cp[0], cp[1]],
        median_T=median_t,
        projection_faults=faults,
        usable=len(usable_I),
        trial_rows=rows,
    )


def _envelope(
    config: Dict[str, Any],
    digest: str,
    git_sha: str,
    *,
    status: str,
    notes: str,
    trials_completed: int,
    mean_I: Optional[float] = None,
    mean_I_ci95: Optional[List[float]] = None,
    retrieval_accuracy: Optional[float] = None,
    retrieval_accuracy_ci95: Optional[List[float]] = None,
    median_T: Optional[float] = None,
    projection_faults: int = 0,
    usable: int = 0,
    trial_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    ci_low = None if not mean_I_ci95 else mean_I_ci95[0]
    acc_low = None if not retrieval_accuracy_ci95 else retrieval_accuracy_ci95[0]
    return {
        "protocol": PROTOCOL,
        "status": status,
        "claim_class": "measured_result" if status in ("measured", "partial") and trials_completed else "measured_result",
        "git_sha": git_sha,
        "seed_record": {
            "codebook_seed": int(config["codebook_seed"]),
            "trial_seed": int(config["trial_seed"]),
            "config_sha256": digest,
            "bootstrap_seed": int(config["bootstrap_seed"]),
        },
        "phase": "I",
        "d": int(config["d"]),
        "k": int(config["k"]),
        "gamma": float(config["gamma"]),
        "n_trials": int(config["n_trials"]),
        "trials_completed": int(trials_completed),
        "usable_trials": int(usable),
        "mean_I": mean_I,
        "mean_I_ci95": mean_I_ci95,
        "mean_I_ci_low": ci_low,
        "retrieval_accuracy": retrieval_accuracy,
        "retrieval_accuracy_ci95": retrieval_accuracy_ci95,
        "accuracy_ci_low": acc_low,
        "median_T": median_T,
        "projection_faults": int(projection_faults),
        "k_max": None,
        "R_d": None,
        "notes": notes,
        "configuration": config,
        "trials": trial_rows or [],
    }


def capacities_from_cells(cells: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """k_max per (d, gamma) and R_d at matched gamma. Undefined stays None."""
    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for cell in cells:
        if cell.get("status") not in ("measured", "partial"):
            continue
        if cell.get("mean_I_ci_low") is None or cell.get("accuracy_ci_low") is None:
            continue
        key = (cell["d"], cell["gamma"])
        grouped.setdefault(key, []).append(
            {
                "k": cell["k"],
                "mean_I_ci_low": cell["mean_I_ci_low"],
                "accuracy_ci_low": cell["accuracy_ci_low"],
            }
        )
    out: Dict[str, Any] = {"k_max": {}, "R_d": {}}
    found = {}
    for (d, gamma), rows in grouped.items():
        value = k_max(rows)
        found[(d, gamma)] = value
        out["k_max"][f"d={d},gamma={gamma}"] = value
    gammas = {g for (_d, g) in found}
    for gamma in sorted(gammas):
        out["R_d"][str(gamma)] = scaling_ratio(found.get((16384, gamma)), found.get((8192, gamma)))
    return out

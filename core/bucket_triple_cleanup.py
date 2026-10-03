#!/usr/bin/env python3
"""Bucket-triple cleanup, with no absolute score gate.

Off the locked Phase I path. Does not modify resonator(), run_trial()'s
default, CONSTITUTION_v1.3.md, or results/execution_record.json.

Named assumption: s is one component-wise product of three distinct codebook
phasors. gamma = 0, so the product is exact.

One trial at T_max = 7 spends the budget as follows.

1. One hash. Codewords are partitioned into B equal buckets. The bucket
   vector is the linear sum of its codewords and is not phasor-projected.
   Every unordered triple of distinct buckets is scored by

       I = (1/d) sum_j cos(phase(s_j * conj(v_b,j) * conj(v_g,j) * conj(v_d,j))).

   A zero modulus is a projection fault, never phase 0. The argmax triple
   is kept. There is no absolute score threshold and no rehash.

2. If a step remains, the 5^3 codeword triples with one codeword from each
   winning bucket are scored by the locked cosine-sum against s. The
   maximizer initializes cleanup. It is not a retrieval.

3. Each remaining step is one pass of the ordinary resonator update,
   restricted to the 15 codewords in the winning buckets: sequential
   unbind, soft cleanup A A^H, then component-wise phasor projection.
   The same early stop as resonator() applies (repeated argmax tuple).
   Phasor projection is used here and at readout, not on bucket sums.

Retrieval is recorded only after at least one cleanup pass. retrieval_hit
is true when the three readout symbols are the three generators up to
order, in the shared codebook. A winning bucket set that merely contains
the generators is not a hit.

The per-trial I used for the mean is the mean of the three factor-wise
cosine-sums under the slot permutation that maximizes that mean. It is
computed on the cleanup estimates, not replaced by the symbol, and it is
kept when the symbol is wrong. The designated-factor cosine-sum (locked
run_trial alignment) is recorded separately and is not the pass metric.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from benchmark_metrics import (
    bootstrap_mean_ci,
    clopper_pearson,
    invertibility,
    phasor_project,
)
from bucket_triple import (
    _bucket_sums,
    _partition,
    exact_codeword_scan,
    rank_triples,
)
from fhrr_protocol import (
    T_MAX,
    _argmax_index,
    _codebook_cleanup,
    bind_factors,
    sample_codebook,
)

CODEBOOK_SEED = 20260930
TRIAL_SEED = 20261003
BOOTSTRAP_SEED = 20260930
BOOTSTRAP_B = 10000
I_FLOOR = 0.92
ACC_FLOOR = 0.95
PROCEDURE_ID = "bucket_cleanup_no_absolute_gate_v1"

MEAN_I_DEFINITION = (
    "mean_post_cleanup_I averages, over every usable trial, the per-trial "
    "post-cleanup I. A trial is unusable only when a projection fault fired; "
    "faulted trials are dropped, not filled in. On a usable trial, I is the "
    "mean of the three factor-wise cosine-sums I=(1/d) sum cos(delta phi) "
    "under the slot permutation that maximizes that mean. Each term compares "
    "a true generator phasor to the aligned cleanup estimate. A wrong readout "
    "symbol does not drop the trial, zero it, or replace it with the bucket "
    "score or the hit bit. mean_I_hits_only averages that same I over "
    "retrieval hits only and is not the pass metric. I_designated is the "
    "locked single-factor alignment (designated generator vs best slot) and "
    "is not the pass metric either. retrieval_hit is the three-symbol set "
    "match after cleanup, not bucket containment."
)


def _as_float_list(values: Sequence[float]) -> List[float]:
    return [float(v) for v in values]


def aligned_factor_I(
    truth: Sequence[np.ndarray],
    estimates: Sequence[np.ndarray],
) -> Dict[str, Any]:
    """Best-permutation mean cosine-sum, plus the locked designated-factor I.

    Neither value is conditioned on the readout symbol.
    """
    if len(truth) != 3 or len(estimates) != 3:
        raise ValueError("aligned_factor_I is the k=3 case")
    best_mean = -np.inf
    best_vals: Optional[List[float]] = None
    best_perm: Optional[Tuple[int, int, int]] = None
    for perm in itertools.permutations(range(3)):
        vals = [invertibility(truth[t], estimates[perm[t]]) for t in range(3)]
        mean = float(np.mean(vals))
        if mean > best_mean:
            best_mean = mean
            best_vals = [float(v) for v in vals]
            best_perm = perm  # type: ignore[assignment]
    if best_perm is None or best_vals is None:
        raise RuntimeError("no alignment")
    designated = [invertibility(truth[0], estimates[i]) for i in range(3)]
    slot = int(np.argmax(designated))
    return {
        "I": float(best_mean),
        "I_components": best_vals,
        "alignment_perm": [int(p) for p in best_perm],
        "I_designated": float(designated[slot]),
        "designated_slot": slot,
    }


def retrieval_set_hit(recovered: Sequence[int], true_idx: Sequence[int]) -> bool:
    """True when recovered symbols are the generators, order ignored.

    Duplicate readouts are not a hit. Containment of buckets is not consulted.
    """
    got = [int(x) for x in recovered]
    if len(got) != 3 or len(set(got)) != 3:
        return False
    return set(got) == {int(x) for x in true_idx}


def phasor_cleanup_on_subcodebook(
    s: np.ndarray,
    subcode: np.ndarray,
    init_local: Sequence[int],
    t_max: int,
) -> Dict[str, Any]:
    """Ordinary sequential phasor cleanup, codebook restricted to `subcode`.

    Init is the supplied local indices, not resonator()'s random phasors.
    The update map is fhrr_protocol._codebook_cleanup (A A^H then
    phasor_project). Early stop matches resonator(): the argmax tuple
    repeated. A zero component is a fault, not phase 0; that slot is left
    unchanged for the step, and the fault is counted.
    """
    if len(init_local) != 3:
        raise ValueError("k=3 cleanup")
    if t_max < 0:
        raise ValueError("t_max")
    sub_conj = np.conjugate(subcode)
    estimates = [np.array(subcode[int(i)], copy=True) for i in init_local]
    faults = 0
    prev: Optional[Tuple[int, int, int]] = None
    winners = tuple(int(i) for i in init_local)
    used = 0
    for t in range(1, int(t_max) + 1):
        for i in range(3):
            decoded = np.array(s, copy=True)
            for j in range(3):
                if j == i:
                    continue
                decoded = decoded * np.conjugate(estimates[j])
            cleaned, step_faults = _codebook_cleanup(subcode, decoded, sub_conj)
            faults += int(step_faults)
            if step_faults:
                continue
            estimates[i] = cleaned
        winners = tuple(_argmax_index(subcode, estimates[i]) for i in range(3))
        used = t
        if winners == prev:
            break
        prev = winners
    return {
        "estimates": estimates,
        "iterations": int(used),
        "projection_faults": int(faults),
        "winners_local": [int(w) for w in winners],
    }


def _subcode_from_buckets(
    codebook: np.ndarray,
    assignment: np.ndarray,
    buckets: Sequence[int],
) -> Tuple[np.ndarray, np.ndarray]:
    groups = [np.flatnonzero(assignment == int(b)) for b in buckets]
    if any(len(g) == 0 for g in groups):
        raise ValueError("empty winning bucket")
    global_idx = np.concatenate(groups).astype(np.int64)
    return codebook[global_idx], global_idx


def run_bucket_cleanup_trial(
    codebook: np.ndarray,
    rng_entropy_children: Sequence[Any],
    *,
    bucket_size: int = 5,
    k: int = 3,
    t_max: int = T_MAX,
    topk: int = 8,
) -> Dict[str, Any]:
    """One cleanup trial. No absolute score gate.

    children[0] draws the three generators. children[1] draws the single
    hash. Later children are unused: cleanup is determined by the scan.
    """
    if k != 3:
        raise ValueError("this procedure is the k=3 bucket triple")
    m, _d = codebook.shape
    if m % bucket_size != 0:
        raise ValueError("M must be divisible by the bucket size")
    n_buckets = m // bucket_size
    gen_rng = np.random.default_rng(rng_entropy_children[0])
    true_idx = gen_rng.choice(m, size=k, replace=False).astype(np.int64)
    bound = bind_factors(codebook[true_idx])
    projected, faults = phasor_project(bound)
    if faults:
        return _empty(true_idx, faults=int(faults), reason="bind_projection")
    s = projected
    hash_rng = np.random.default_rng(rng_entropy_children[1])
    assignment = _partition(m, bucket_size, hash_rng)
    try:
        sums = _bucket_sums(codebook, assignment, n_buckets)
    except ZeroDivisionError:
        return _empty(true_idx, faults=1, reason="bucket_sum")
    modulus = np.abs(sums)
    if not np.all(np.isfinite(modulus)) or np.any(modulus == 0):
        return _empty(true_idx, faults=1, reason="bucket_sum_modulus")
    # Guard: a phasor projection would put every modulus at 1.
    if bool(np.all(np.isclose(modulus, 1.0))):
        raise RuntimeError("bucket sums are unit phasors; projection leaked into the sum")
    gen_buckets = assignment[true_idx]
    distinct = {int(b) for b in gen_buckets}
    collision = len(distinct) < 3
    try:
        ranked = rank_triples(sums, s, [int(b) for b in gen_buckets], topk=topk)
    except ZeroDivisionError:
        return _empty(true_idx, faults=1, reason="bucket_score")
    steps = 1
    win_set = {int(b) for b in ranked["winner_buckets"]}
    contains = all(int(assignment[int(i)]) in win_set for i in true_idx)
    base = {
        "projection_faults": 0,
        "excluded": False,
        "generator_indices": [int(x) for x in true_idx],
        "collision": bool(collision),
        "generator_buckets": [int(b) for b in gen_buckets],
        "winner_buckets": [int(b) for b in ranked["winner_buckets"]],
        "winner_contains_all_generators": bool(contains),
        "winner_I": float(ranked["winner_I"]),
        "best_impostor_I": float(ranked["best_impostor_I"]),
        "generator_I": None if ranked["generator_I"] is None else float(ranked["generator_I"]),
        "gap": None if ranked["gap"] is None else float(ranked["gap"]),
        "n_hashes": 1,
        "rehash_used": False,
        "absolute_score_gate": False,
        "full_scan_fallbacks": 1 if ranked.get("used_full_scan") else 0,
        "n_bucket_triples_scored": int(ranked["n_scored"]),
        "bucket_sum_modulus_median": float(np.median(modulus)),
    }
    if steps >= t_max:
        return _no_retrieval(base, steps=steps, scan=None, reason="budget_after_hash")
    scanned = exact_codeword_scan(codebook, s, assignment, ranked["winner_buckets"])
    steps += 1
    scan_codewords = [int(c) for c in scanned["codewords"]]
    scan_hit = retrieval_set_hit(scan_codewords, true_idx)
    if steps >= t_max:
        row = _no_retrieval(
            base,
            steps=steps,
            scan=scanned,
            reason="budget_after_scan",
        )
        row["scan_set_matches_generators"] = bool(scan_hit)
        return row
    sub, global_idx = _subcode_from_buckets(codebook, assignment, ranked["winner_buckets"])
    locate = {int(g): i for i, g in enumerate(global_idx.tolist())}
    try:
        init_local = [locate[c] for c in scan_codewords]
    except KeyError as exc:
        raise RuntimeError("scan codeword missing from its bucket") from exc
    cleanup_budget = int(t_max) - steps
    cleaned = phasor_cleanup_on_subcodebook(s, sub, init_local, cleanup_budget)
    steps += int(cleaned["iterations"])
    if cleaned["projection_faults"]:
        row = _empty(true_idx, faults=int(cleaned["projection_faults"]), reason="cleanup_projection")
        row.update(
            {
                "collision": bool(collision),
                "generator_buckets": base["generator_buckets"],
                "winner_buckets": base["winner_buckets"],
                "winner_contains_all_generators": bool(contains),
                "winner_I": base["winner_I"],
                "best_impostor_I": base["best_impostor_I"],
                "generator_I": base["generator_I"],
                "gap": base["gap"],
                "n_hashes": 1,
                "rehash_used": False,
                "steps_used": int(steps),
                "cleanup_iterations": int(cleaned["iterations"]),
                "scan_performed": True,
                "recovery_performed": False,
                "retrieval_hit": None,
                "I": None,
                "I_designated": None,
            }
        )
        return row
    winners_local = cleaned["winners_local"]
    recovered = [int(global_idx[w]) for w in winners_local]
    full_book = [_argmax_index(codebook, est) for est in cleaned["estimates"]]
    truth = [codebook[int(i)] for i in true_idx]
    scored = aligned_factor_I(truth, cleaned["estimates"])
    hit = retrieval_set_hit(recovered, true_idx)
    row = dict(base)
    row.update(
        {
            "steps_used": int(steps),
            "cleanup_iterations": int(cleaned["iterations"]),
            "scan_performed": True,
            "n_codeword_triples_scored": int(bucket_size) ** 3,
            "scan_codewords": scan_codewords,
            "scan_I_vs_s": float(scanned["I_vs_s"]),
            "scan_set_matches_generators": bool(scan_hit),
            "recovery_performed": True,
            "retrieval_hit": bool(hit),
            "I": float(scored["I"]),
            "I_components": _as_float_list(scored["I_components"]),
            "alignment_perm": list(scored["alignment_perm"]),
            "I_designated": float(scored["I_designated"]),
            "designated_slot": int(scored["designated_slot"]),
            "recovered_codewords": recovered,
            "full_codebook_argmax": [int(x) for x in full_book],
            "full_codebook_set_hit": bool(retrieval_set_hit(full_book, true_idx)),
            "cleanup_codebook_size": int(sub.shape[0]),
        }
    )
    return row


def _empty(true_idx: np.ndarray, *, faults: int, reason: str) -> Dict[str, Any]:
    return {
        "projection_faults": int(faults),
        "excluded": True,
        "exclude_reason": reason,
        "generator_indices": [int(x) for x in true_idx],
        "collision": None,
        "winner_contains_all_generators": None,
        "winner_I": None,
        "best_impostor_I": None,
        "generator_I": None,
        "gap": None,
        "n_hashes": 0,
        "rehash_used": False,
        "absolute_score_gate": False,
        "steps_used": 0,
        "cleanup_iterations": 0,
        "scan_performed": False,
        "recovery_performed": False,
        "retrieval_hit": None,
        "I": None,
        "I_designated": None,
    }


def _no_retrieval(
    base: Dict[str, Any],
    *,
    steps: int,
    scan: Optional[Dict[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    """Hash (and maybe the 125-scan) ran, but cleanup did not. Not a hit.

    I is null. Containment is left as recorded and is not copied into
    retrieval_hit.
    """
    row = dict(base)
    row.update(
        {
            "steps_used": int(steps),
            "cleanup_iterations": 0,
            "scan_performed": scan is not None,
            "recovery_performed": False,
            "retrieval_hit": False,
            "I": None,
            "I_designated": None,
            "no_retrieval_reason": reason,
        }
    )
    if scan is not None:
        row["scan_codewords"] = [int(c) for c in scan["codewords"]]
        row["scan_I_vs_s"] = float(scan["I_vs_s"])
        row["n_codeword_triples_scored"] = None
    return row


def _trial_sequences(trial_seed: int, n_trials: int, t_max: int) -> List[List[Any]]:
    out = []
    for i in range(n_trials):
        parent = np.random.SeedSequence([int(trial_seed), int(i)])
        out.append(list(parent.spawn(1 + int(t_max))))
    return out


def _git_sha(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _quantile_summary(values: List[float]) -> Dict[str, Any]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return {"n": 0}
    qs = np.quantile(arr, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=0)),
        "min": float(arr.min()),
        "p05": float(qs[0]),
        "p25": float(qs[1]),
        "p50": float(qs[2]),
        "p75": float(qs[3]),
        "p95": float(qs[4]),
        "max": float(arr.max()),
    }


def _summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    usable = [r for r in rows if not r.get("excluded")]
    # Retrieval is defined on usable trials. A trial that never cleaned up
    # has retrieval_hit False and I null; it counts against accuracy and is
    # listed in n_without_I. It is not given a stand-in I.
    hits = [1 if r.get("retrieval_hit") else 0 for r in usable]
    n = len(hits)
    successes = int(sum(hits))
    acc = None if n == 0 else successes / n
    cp = None if n == 0 else clopper_pearson(successes, n)
    recovered = [r for r in usable if r.get("recovery_performed") and r.get("I") is not None]
    # Primary mean: every usable trial that has a real post-cleanup I.
    # Usable trials without cleanup have no I and the mean is then undefined,
    # so a budget that skips cleanup cannot clear the floor by imputation.
    all_have_I = n > 0 and len(recovered) == n
    values = [float(r["I"]) for r in recovered] if all_have_I else []
    boot = bootstrap_mean_ci(values, BOOTSTRAP_SEED, BOOTSTRAP_B) if all_have_I else None
    hit_values = [float(r["I"]) for r in recovered if r.get("retrieval_hit")]
    hit_mean = None if not hit_values else float(np.mean(hit_values))
    des_values = [float(r["I_designated"]) for r in recovered if r.get("I_designated") is not None]
    des_boot = (
        bootstrap_mean_ci(des_values, BOOTSTRAP_SEED, BOOTSTRAP_B)
        if all_have_I and len(des_values) == n
        else None
    )
    steps = [int(r["steps_used"]) for r in usable if r.get("steps_used") is not None]
    cleanup_iters = [int(r.get("cleanup_iterations") or 0) for r in usable]
    median_T = None if not steps else float(np.median(np.asarray(steps, dtype=np.float64)))
    median_cleanup = (
        None if not cleanup_iters else float(np.median(np.asarray(cleanup_iters, dtype=np.float64)))
    )
    gaps = [float(r["gap"]) for r in usable if r.get("gap") is not None]
    contains = [
        1 if r.get("winner_contains_all_generators") else 0
        for r in usable
        if r.get("winner_contains_all_generators") is not None
    ]
    faults = sum(int(r.get("projection_faults") or 0) for r in rows)
    full_hits = sum(1 for r in usable if r.get("full_codebook_set_hit"))
    scan_hits = sum(1 for r in usable if r.get("scan_set_matches_generators"))
    collisions = sum(1 for r in usable if r.get("collision"))
    acc_low = None if cp is None else cp[0]
    i_low = None if boot is None else boot[1]
    floors_met = (
        acc_low is not None
        and i_low is not None
        and acc_low >= ACC_FLOOR
        and i_low >= I_FLOOR
    )
    step_counts: Dict[str, int] = {}
    for s in steps:
        step_counts[str(s)] = step_counts.get(str(s), 0) + 1
    return {
        "n": n,
        "hits": successes,
        "retrieval_accuracy": acc,
        "retrieval_accuracy_ci95": None if cp is None else [cp[0], cp[1]],
        "accuracy_ci_low": acc_low,
        "mean_post_cleanup_I": None if boot is None else boot[0],
        "mean_post_cleanup_I_ci95": None if boot is None else [boot[1], boot[2]],
        "mean_post_cleanup_I_ci_low": i_low,
        "mean_I_defined": bool(all_have_I),
        "n_with_I": len(recovered) if all_have_I else len(recovered),
        "n_without_I": int(n - len([r for r in usable if r.get("I") is not None])),
        "mean_I_hits_only": hit_mean,
        "n_hits_with_I": len(hit_values),
        "I_distribution": _quantile_summary(values),
        "mean_I_designated": None if des_boot is None else des_boot[0],
        "mean_I_designated_ci95": None if des_boot is None else [des_boot[1], des_boot[2]],
        "median_T": median_T,
        "median_cleanup_iterations": median_cleanup,
        "steps_used_counts": step_counts,
        "floors_met": bool(floors_met),
        "status": "pass" if floors_met else "not_a_pass",
        "gap_distribution": _gap_summary(gaps),
        "collision_count": int(collisions),
        "trials_containing_generators": int(sum(contains)),
        "winner_contains_rate": None if not contains else float(np.mean(contains)),
        "projection_faults": int(faults),
        "scan_set_match_count": int(scan_hits),
        "full_codebook_set_hit_count": int(full_hits),
        "full_scan_fallbacks": int(sum(int(r.get("full_scan_fallbacks") or 0) for r in rows)),
    }


def _gap_summary(gaps: List[float]) -> Dict[str, Any]:
    base = _quantile_summary(gaps)
    if not gaps:
        return base
    arr = np.asarray(gaps, dtype=np.float64)
    base["n_negative"] = int(np.sum(arr < 0))
    base["n_positive"] = int(np.sum(arr > 0))
    base["n_zero"] = int(np.sum(arr == 0))
    return base


def _envelope(
    rows: List[Dict[str, Any]],
    *,
    n_target: int,
    git_sha: str,
    seconds_per_trial_first: Optional[float],
    elapsed_s: float,
    d: int,
    m: int,
    bucket_size: int,
) -> Dict[str, Any]:
    summary = _summarize(rows)
    finished = len(rows)
    return {
        "label": "adl_bucket_triple_cleanup",
        "procedure_id": PROCEDURE_ID,
        "claim_class": "measured_result",
        "status": summary["status"],
        "floors_met": summary["floors_met"],
        "floors": {"mean_I_ci_low": I_FLOOR, "accuracy_ci_low": ACC_FLOOR},
        "pass_rule": (
            "status is pass only if the lower Clopper-Pearson bound of retrieval "
            "accuracy is >= 0.95 and the lower percentile-bootstrap bound of "
            "mean_post_cleanup_I is >= 0.92. Otherwise status is not_a_pass. "
            "Bucket containment is not a hit and is not a pass. There is no "
            "absolute score gate."
        ),
        "mean_I_definition": MEAN_I_DEFINITION,
        "git_sha": git_sha,
        "network_access": False,
        "off_locked_path": True,
        "seed_record": {
            "codebook_seed": CODEBOOK_SEED,
            "trial_seed": TRIAL_SEED,
            "trial_seed_scheme": "SeedSequence([trial_seed, trial_index]).spawn(1+T_max); child 0 generators, child 1 the single hash; later children unused",
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_resamples": BOOTSTRAP_B,
            "bootstrap": "percentile bootstrap of the mean, quantiles 0.025 and 0.975",
        },
        "configuration": {
            "d": int(d),
            "M": int(m),
            "B": int(m // bucket_size),
            "bucket_size": int(bucket_size),
            "k": 3,
            "gamma": 0.0,
            "t_max": T_MAX,
            "absolute_score_gate": False,
            "score_threshold": None,
            "assumption": "s is one component-wise product of three distinct codebook phasors",
            "bucket_vector": "linear sum of codewords, not phasor-projected",
            "bucket_score": "(1/d) sum cos(phase(s * conj(v_b) * conj(v_g) * conj(v_d)))",
            "triple_enumeration": "unordered distinct buckets; one hash; argmax; no rehash",
            "step_2": "score 5^3 one-from-each-bucket codeword triples by locked cosine-sum vs s; initializer only",
            "cleanup": (
                "remaining steps are resonator updates on the 15 codewords only: "
                "sequential unbind, A A^H, phasor_project; early stop on repeated argmax tuple"
            ),
            "retrieval_hit": "set of three cleanup readouts equals the generator set; shared codebook; not containment",
            "I": "mean of three permutation-aligned factor cosine-sums on the cleanup estimates",
            "n_target": int(n_target),
        },
        "n": int(finished),
        "n_target": int(n_target),
        "usable_trials": summary["n"],
        "hits": summary["hits"],
        "retrieval_accuracy": summary["retrieval_accuracy"],
        "retrieval_accuracy_ci95": summary["retrieval_accuracy_ci95"],
        "accuracy_ci_low": summary["accuracy_ci_low"],
        "mean_post_cleanup_I": summary["mean_post_cleanup_I"],
        "mean_post_cleanup_I_ci95": summary["mean_post_cleanup_I_ci95"],
        "mean_post_cleanup_I_ci_low": summary["mean_post_cleanup_I_ci_low"],
        "mean_I_defined": summary["mean_I_defined"],
        "n_with_I": summary["n_with_I"],
        "n_without_I": summary["n_without_I"],
        "mean_I_hits_only": summary["mean_I_hits_only"],
        "n_hits_with_I": summary["n_hits_with_I"],
        "I_distribution": summary["I_distribution"],
        "mean_I_designated": summary["mean_I_designated"],
        "mean_I_designated_ci95": summary["mean_I_designated_ci95"],
        "median_T": summary["median_T"],
        "median_cleanup_iterations": summary["median_cleanup_iterations"],
        "steps_used_counts": summary["steps_used_counts"],
        "projection_faults": summary["projection_faults"],
        "trials_containing_generators": summary["trials_containing_generators"],
        "winner_contains_rate": summary["winner_contains_rate"],
        "gap_distribution": summary["gap_distribution"],
        "collision_count": summary["collision_count"],
        "scan_set_match_count": summary["scan_set_match_count"],
        "full_codebook_set_hit_count": summary["full_codebook_set_hit_count"],
        "full_scan_fallbacks": summary["full_scan_fallbacks"],
        "seconds_first_trial": seconds_per_trial_first,
        "elapsed_s": elapsed_s,
        "trial_seconds_sum": float(sum(float(r.get("seconds") or 0.0) for r in rows)),
        "trials": rows,
    }


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _first_seconds(rows: List[Dict[str, Any]]) -> Optional[float]:
    if not rows:
        return None
    return rows[0].get("seconds")


def self_check() -> None:
    """Small-d checks: no 0.7 gate, retrieval only after cleanup, I not imputed."""
    from bucket_triple import _literal_scores

    rng = np.random.default_rng(0)
    m, d, bucket_size = 30, 256, 5
    phases = rng.uniform(-np.pi, np.pi, size=(m, d))
    codebook = np.exp(1j * phases)
    # Known generators in three different buckets under the identity partition.
    true = np.array([0, 5, 10])
    s, faults = phasor_project(bind_factors(codebook[true]))
    if faults:
        raise AssertionError("bind fault")
    assignment = (np.arange(m) // bucket_size).astype(np.int32)
    sums = _bucket_sums(codebook, assignment, m // bucket_size)
    manual_sum = codebook[assignment == 0].sum(axis=0)
    if not np.allclose(sums[0], manual_sum):
        raise AssertionError("bucket vector is not the linear sum")
    if np.all(np.isclose(np.abs(sums[0]), 1.0)):
        raise AssertionError("bucket sum was phasor-projected")
    true_I = float(_literal_scores(s, sums, np.array([[0, 1, 2]], dtype=np.int32))[0])
    if true_I >= 0.7:
        raise AssertionError(f"fixture bucket score cleared 0.7: {true_I}")
    # Cleanup is invoked on these buckets even though the absolute score is below 0.7.
    scanned = exact_codeword_scan(codebook, s, assignment, [0, 1, 2])
    if set(scanned["codewords"]) != {0, 5, 10}:
        raise AssertionError(f"scan missed generators: {scanned}")
    if abs(float(scanned["I_vs_s"]) - 1.0) > 1e-9:
        raise AssertionError("true product must score 1")
    sub, global_idx = _subcode_from_buckets(codebook, assignment, [0, 1, 2])
    locate = {int(g): i for i, g in enumerate(global_idx.tolist())}
    init_local = [locate[c] for c in scanned["codewords"]]
    cleaned = phasor_cleanup_on_subcodebook(s, sub, init_local, 5)
    if cleaned["projection_faults"]:
        raise AssertionError("cleanup fault")
    recovered = [int(global_idx[w]) for w in cleaned["winners_local"]]
    if not retrieval_set_hit(recovered, true):
        raise AssertionError(f"cleanup readout {recovered}")
    # Containment is not the hit bit.
    if retrieval_set_hit([0, 1, 2], true):
        raise AssertionError("unrelated indices must not hit")
    if retrieval_set_hit([0, 5, 5], true):
        raise AssertionError("duplicate readout must not hit")
    truth = [codebook[i] for i in true]
    scored = aligned_factor_I(truth, cleaned["estimates"])
    if scored["I"] < 0.9:
        raise AssertionError(f"post-cleanup I too low: {scored['I']}")
    # Wrong symbols still contribute their cosine, not a hidden zero.
    wrong = [codebook[1], codebook[2], codebook[3]]
    wrong_scores = aligned_factor_I(truth, wrong)
    manual = []
    for perm in itertools.permutations(range(3)):
        manual.append(float(np.mean([invertibility(truth[t], wrong[perm[t]]) for t in range(3)])))
    if abs(wrong_scores["I"] - max(manual)) > 1e-12:
        raise AssertionError("I was not the aligned cosine-sum")
    if wrong_scores["I"] == 0.0:
        raise AssertionError("cosine happened to be 0; pick another fixture")
    # Constant phase offset: symbol can still match while I is cos(theta), not 1.
    theta = 0.3
    shifted = [row * np.exp(1j * theta) for row in truth]
    shift_scores = aligned_factor_I(truth, shifted)
    if abs(shift_scores["I"] - float(np.cos(theta))) > 1e-9:
        raise AssertionError(f"phase offset I {shift_scores['I']} != cos(theta)")
    # End-to-end: t_max=2 scans but does not retrieve, even if buckets contain.
    parent = np.random.SeedSequence([20261003, 0])
    short = run_bucket_cleanup_trial(
        codebook, list(parent.spawn(1 + 7)), bucket_size=5, t_max=2, topk=4
    )
    if short["n_hashes"] != 1 or short["rehash_used"] or short["absolute_score_gate"]:
        raise AssertionError("hash budget")
    if short["cleanup_iterations"] != 0 or short["recovery_performed"]:
        raise AssertionError("cleanup ran inside the scan step")
    if short["retrieval_hit"] or short["I"] is not None:
        raise AssertionError("retrieval recorded before cleanup")
    # Same generators/hash, full budget. Find a seed whose buckets contain.
    found = False
    for i in range(40):
        kids = list(np.random.SeedSequence([123, i]).spawn(1 + 7))
        row = run_bucket_cleanup_trial(codebook, kids, bucket_size=5, t_max=7, topk=4)
        if row["excluded"]:
            raise AssertionError("unexpected fault")
        if row["winner_I"] >= 0.7:
            raise AssertionError("small instance cleared 0.7; gate would not be tested")
        if not row["winner_contains_all_generators"]:
            if row["retrieval_hit"]:
                raise AssertionError("hit without the generators in the winning buckets")
            continue
        if row["collision"]:
            # Two generators in one bucket can still be contained. The 125-scan
            # cannot list both, so this is not the recovery fixture.
            continue
        found = True
        if not row["recovery_performed"] or not row["retrieval_hit"]:
            raise AssertionError(f"contained but not recovered: {row['recovered_codewords']}")
        if row["I"] is None or row["I"] < 0.9:
            raise AssertionError(f"I missing or low: {row['I']}")
        if row["n_hashes"] != 1 or row["steps_used"] > 7 or row["steps_used"] < 3:
            raise AssertionError(f"steps {row['steps_used']}")
        if row["cleanup_codebook_size"] != 15:
            raise AssertionError("cleanup book")
        # Miss path on a book that excludes the generators: I stays numeric.
        break
    if not found:
        raise AssertionError("no containing trial in 40 draws")
    decoy = codebook[np.array([1, 2, 3, 4, 6])]
    # Pad decoy to 15 rows so the cleanup map is well-defined, none of them true.
    pad_idx = [1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 1, 2, 3]
    decoy_book = codebook[np.array(pad_idx)]
    # Distinct-enough init inside the decoy book.
    miss = phasor_cleanup_on_subcodebook(s, decoy_book, [0, 1, 2], 5)
    miss_idx = [int(pad_idx[w]) for w in miss["winners_local"]]
    if retrieval_set_hit(miss_idx, true):
        raise AssertionError("decoy book retrieved the generators")
    miss_I = aligned_factor_I(truth, miss["estimates"])["I"]
    if not np.isfinite(miss_I):
        raise AssertionError("non-finite I on a miss")
    # t_max=1 never turns containment into a hit.
    bare = run_bucket_cleanup_trial(
        codebook, list(np.random.SeedSequence([123, 0]).spawn(1 + 7)), bucket_size=5, t_max=1, topk=4
    )
    if bare["retrieval_hit"] or bare["I"] is not None or bare["recovery_performed"]:
        raise AssertionError("hash-only trial recorded a retrieval")
    _ = decoy


def run_cleanup(
    *,
    n_target: int,
    out: Path,
    root: Path,
    resume: bool = True,
    d: int = 8192,
    m: int = 1000,
    bucket_size: int = 5,
) -> Dict[str, Any]:
    git_sha = _git_sha(root)
    codebook = sample_codebook(m, d, CODEBOOK_SEED)
    sequences = _trial_sequences(TRIAL_SEED, n_target, T_MAX)
    rows: List[Dict[str, Any]] = []
    if resume and out.exists():
        prior = json.loads(out.read_text(encoding="utf-8"))
        if (
            prior.get("procedure_id") == PROCEDURE_ID
            and prior.get("seed_record", {}).get("trial_seed") == TRIAL_SEED
            and prior.get("seed_record", {}).get("codebook_seed") == CODEBOOK_SEED
            and prior.get("configuration", {}).get("d") == d
            and prior.get("configuration", {}).get("M") == m
            and prior.get("configuration", {}).get("absolute_score_gate") is False
        ):
            rows = list(prior.get("trials") or [])
            if len(rows) > n_target:
                rows = rows[:n_target]
    t0 = time.perf_counter()
    for i in range(len(rows), n_target):
        ts = time.perf_counter()
        row = run_bucket_cleanup_trial(
            codebook, sequences[i], bucket_size=bucket_size, k=3, t_max=T_MAX
        )
        row["trial_index"] = i
        row["trial_seed"] = [TRIAL_SEED, i]
        dt = time.perf_counter() - ts
        row["seconds"] = dt
        rows.append(row)
        payload = _envelope(
            rows,
            n_target=n_target,
            git_sha=git_sha,
            seconds_per_trial_first=_first_seconds(rows),
            elapsed_s=time.perf_counter() - t0,
            d=d,
            m=m,
            bucket_size=bucket_size,
        )
        _write(out, payload)
        print(
            f"trial {i} {dt:.2f}s winner_I={row.get('winner_I')} "
            f"contains={row.get('winner_contains_all_generators')} gap={row.get('gap')} "
            f"hit={row.get('retrieval_hit')} I={row.get('I')} "
            f"steps={row.get('steps_used')} cleanup={row.get('cleanup_iterations')} "
            f"scan_match={row.get('scan_set_matches_generators')}",
            flush=True,
        )
    payload = _envelope(
        rows,
        n_target=n_target,
        git_sha=git_sha,
        seconds_per_trial_first=_first_seconds(rows),
        elapsed_s=time.perf_counter() - t0,
        d=d,
        m=m,
        bucket_size=bucket_size,
    )
    _write(out, payload)
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Bucket-triple cleanup, no absolute score gate")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/workspace/sovereign-clean-room/results/bucket_triple_cleanup.json"),
    )
    parser.add_argument("--skip-self-check", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if not args.skip_self_check:
        t0 = time.perf_counter()
        self_check()
        print(f"self_check ok {time.perf_counter() - t0:.2f}s", flush=True)
    root = Path("/workspace/sovereign-clean-room")
    payload = run_cleanup(
        n_target=args.n,
        out=args.out,
        root=root,
        resume=not args.no_resume,
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "n": payload["n"],
                "hits": payload["hits"],
                "floors_met": payload["floors_met"],
                "retrieval_accuracy": payload["retrieval_accuracy"],
                "retrieval_accuracy_ci95": payload["retrieval_accuracy_ci95"],
                "mean_post_cleanup_I": payload["mean_post_cleanup_I"],
                "mean_post_cleanup_I_ci95": payload["mean_post_cleanup_I_ci95"],
                "mean_I_hits_only": payload["mean_I_hits_only"],
                "median_T": payload["median_T"],
                "projection_faults": payload["projection_faults"],
                "trials_containing_generators": payload["trials_containing_generators"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Adl bucket-triple falsifier. Off the locked Phase I path.

Named assumption: s is ONE component-wise product of three distinct codebook
phasors. This module does not change resonator(), run_trial()'s default, or
results/execution_record.json.

Hash M codewords into B equal buckets. A bucket vector is the linear sum of
its codewords and is not phasor-projected. Every unordered triple of distinct
buckets is scored by

    I = (1/d) sum_j cos(phase(s_j * conj(v_b,j) * conj(v_g,j) * conj(v_d,j))).

A zero component is a projection fault, never phase 0. The score is invariant
to permuting the three buckets, so unordered triples are the same statistic
as ordered distinct triples. Magnitudes cancel when every component is
nonzero, so a component-wise phasor of a bucket sum is used only as a search
key for that phase; reported I values are recomputed from the raw sums with
the formula above.

Within T <= 7, a hash counts as one step. If the winning score is below
0.7, the next step is an independent rehash instead of cleanup. Once a
winner clears 0.7 and a step remains, one exact scan enumerates codeword
triples with one codeword from each winning bucket and keeps the maximizer
of the locked cosine-sum against s.
"""

from __future__ import annotations

import itertools
import json
import math
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
from fhrr_protocol import T_MAX, bind_factors, sample_codebook

THRESHOLD = 0.7
CODEBOOK_SEED = 20260930
TRIAL_SEED = 20261002
BOOTSTRAP_SEED = 20260930
BOOTSTRAP_B = 10000
I_FLOOR = 0.92
ACC_FLOOR = 0.95


def _literal_scores(
    s: np.ndarray,
    sums: np.ndarray,
    triples: np.ndarray,
    chunk: int = 128,
) -> np.ndarray:
    """I for triples (n, 3) from raw bucket sums. Faults raise."""
    n = int(triples.shape[0])
    out = np.empty(n, dtype=np.float64)
    d = int(s.shape[0])
    for start in range(0, n, chunk):
        sel = triples[start : start + chunk]
        z = (
            s
            * np.conjugate(sums[sel[:, 0]])
            * np.conjugate(sums[sel[:, 1]])
            * np.conjugate(sums[sel[:, 2]])
        )
        mag = np.abs(z)
        if not np.all(np.isfinite(mag)) or np.any(mag == 0):
            raise ZeroDivisionError("bucket-product component has modulus 0")
        # cos(phase(z)) = Re(z/|z|). Equal on every nonzero component; angle()
        # is not used, so a zero modulus cannot collapse to phase 0.
        out[start : start + sel.shape[0]] = np.mean(z.real / mag, axis=1)
    return out


def _partition(m: int, bucket_size: int, rng: np.random.Generator) -> np.ndarray:
    if m % bucket_size != 0:
        raise ValueError("M must be divisible by the bucket size")
    perm = rng.permutation(m)
    assignment = np.empty(m, dtype=np.int32)
    assignment[perm] = np.arange(m, dtype=np.int32) // np.int32(bucket_size)
    return assignment


def _bucket_sums(codebook: np.ndarray, assignment: np.ndarray, n_buckets: int) -> np.ndarray:
    """Linear sum of codeword rows in each bucket. Not phasor-projected."""
    m, d = codebook.shape
    sums = np.zeros((n_buckets, d), dtype=np.complex128)
    np.add.at(sums, assignment, codebook)
    return sums


_TRIU: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}


def _triu(m: int) -> Tuple[np.ndarray, np.ndarray]:
    cached = _TRIU.get(m)
    if cached is None:
        cached = np.triu_indices(m, 1)
        _TRIU[m] = cached
    return cached


def screen_triples(
    sums: np.ndarray,
    s: np.ndarray,
    *,
    topk: int = 8,
) -> Dict[str, Any]:
    """Float32 phase screen. Reported scores are not taken from this pass.

    Returns candidate triples, per-chunk float32 cutoffs, and the float32
    winner. Bucket sums are not replaced; only a temporary component-wise
    unit phasor is built to evaluate the phase score's search key.
    """
    mag = np.abs(sums)
    if not np.all(np.isfinite(mag)) or np.any(mag == 0):
        raise ZeroDivisionError("bucket sum component has modulus 0")
    # Search key only. cos(phase(.)) does not depend on these magnitudes.
    q = np.conjugate(sums / mag).astype(np.complex64, copy=False)
    s32 = np.asarray(s, dtype=np.complex64)
    n_buckets, d = q.shape
    cand_idx: List[np.ndarray] = []
    cand_f32: List[np.ndarray] = []
    cutoffs: List[float] = []
    n_scored = 0
    inv_d = np.float32(1.0 / d)
    for b in range(n_buckets - 2):
        rest = q[b + 1 :]
        x = rest * (s32 * q[b])
        gram = x @ rest.T
        m = gram.shape[0]
        iu, ju = _triu(m)
        vals = gram.real[iu, ju] * inv_d
        n_scored += int(vals.size)
        k = min(topk, int(vals.size))
        if k == int(vals.size):
            pick = np.arange(k)
            cutoff = -math.inf
        else:
            part = np.argpartition(vals, -k)
            pick = part[-k:]
            cutoff = float(vals[part[:-k]].max())
        cutoffs.append(cutoff)
        gs = iu[pick] + (b + 1)
        ds = ju[pick] + (b + 1)
        trips = np.empty((k, 3), dtype=np.int32)
        trips[:, 0] = b
        trips[:, 1] = gs
        trips[:, 2] = ds
        cand_idx.append(trips)
        cand_f32.append(np.asarray(vals[pick], dtype=np.float64))
    triples = np.concatenate(cand_idx, axis=0)
    f32 = np.concatenate(cand_f32, axis=0)
    return {
        "triples": triples,
        "f32": f32,
        "max_excluded_f32": float(max(cutoffs) if cutoffs else -math.inf),
        "n_scored": n_scored,
    }


def _unique_rows(triples: np.ndarray, scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    order = np.lexsort((triples[:, 2], triples[:, 1], triples[:, 0], -scores))
    t = triples[order]
    s = scores[order]
    if len(t) == 0:
        return t, s
    change = np.any(t[1:] != t[:-1], axis=1)
    keep = np.empty(len(t), dtype=bool)
    keep[0] = True
    keep[1:] = change
    return t[keep], s[keep]


def rank_triples(
    sums: np.ndarray,
    s: np.ndarray,
    generator_buckets: Optional[Sequence[int]],
    *,
    topk: int = 8,
) -> Dict[str, Any]:
    """Argmax triple, best impostor, and the generator triple.

    generator_buckets lists the bucket id of each generator (length 3, with
    repeats when two generators share a bucket), or None in unit tests that
    only check the argmax. An impostor is a triple that does not contain
    every generator. When the generators occupy three distinct buckets there
    is one such generator triple and gap = generator I - best impostor I.
    A collision has no single generator triple, so gap is null. Reported I
    values are the literal cosine-of-phase scores. The float32 screen only
    proposes candidates; if its exclusion bound can still hide a higher
    triple, this falls back to a full float64 scan.
    """
    screened = screen_triples(sums, s, topk=topk)
    triples = screened["triples"]
    f32 = screened["f32"]
    f64 = _literal_scores(s, sums, triples)
    err = float(np.max(np.abs(f64 - f32))) if len(f64) else 0.0
    n_buckets = int(sums.shape[0])
    gset: Optional[set] = None
    gen_trip = None
    if generator_buckets is not None:
        gset = {int(x) for x in generator_buckets}
        if len(gset) == 3:
            gen_trip = tuple(sorted(gset))
    pool_t = [tuple(int(x) for x in row) for row in triples]
    pool_s = [float(v) for v in f64]
    if gen_trip is not None:
        pool_t.append(gen_trip)
        pool_s.append(float(_literal_scores(s, sums, np.array([gen_trip], dtype=np.int32))[0]))
    elif gset is not None and len(gset) in (1, 2):
        cover = _covering_triples(n_buckets, gset)
        cover_s = _literal_scores(s, sums, cover)
        for i in range(len(cover)):
            pool_t.append(tuple(int(x) for x in cover[i]))
            pool_s.append(float(cover_s[i]))
    best: Dict[Tuple[int, int, int], float] = {}
    for trip, val in zip(pool_t, pool_s):
        prev = best.get(trip)
        if prev is None or val > prev:
            best[trip] = val
    if not best:
        raise RuntimeError("no bucket triples")

    def covers(trip: Tuple[int, int, int]) -> bool:
        if gset is None:
            return False
        return gset.issubset(trip)

    winner = max(best.items(), key=lambda kv: kv[1])[0]
    winner_I = float(best[winner])
    impostors = {t: v for t, v in best.items() if not covers(t)}
    if not impostors:
        raise RuntimeError("no impostor triple in the candidate set")
    impostor_I = float(max(impostors.values()))
    gen_I = None if gen_trip is None else float(best[gen_trip])
    pad = 1e-3
    bound = float(screened["max_excluded_f32"]) + err + pad
    certified = winner_I > bound and impostor_I > bound
    if gen_I is not None and gen_I > winner_I + 1e-12:
        certified = False
    used_full = False
    if not certified:
        used_full = True
        winner, winner_I, impostor_I, gen_I = _full_rank(sums, s, gen_trip, gset)
    gap = None if gen_I is None else float(gen_I - impostor_I)
    if gset is None:
        contains = False
    elif gen_trip is not None:
        contains = winner == gen_trip
    else:
        contains = gset.issubset(winner)
    return {
        "winner_buckets": list(winner),
        "winner_I": float(winner_I),
        "best_impostor_I": float(impostor_I),
        "generator_I": None if gen_I is None else float(gen_I),
        "gap": gap,
        "winner_contains_all_generators": bool(contains),
        "n_scored": int(screened["n_scored"]),
        "screen_max_abs_error": float(err),
        "used_full_scan": bool(used_full),
    }


def _covering_triples(n_buckets: int, gset: set) -> np.ndarray:
    g = sorted(gset)
    rows = []
    if len(g) == 2:
        a, b = g
        for c in range(n_buckets):
            if c != a and c != b:
                rows.append(tuple(sorted((a, b, c))))
    elif len(g) == 1:
        (a,) = g
        others = [i for i in range(n_buckets) if i != a]
        for b, c in itertools.combinations(others, 2):
            rows.append(tuple(sorted((a, b, c))))
    else:
        raise ValueError("covering enumeration is for collisions")
    return np.asarray(rows, dtype=np.int32)


def _full_rank(
    sums: np.ndarray,
    s: np.ndarray,
    gen_trip: Optional[Tuple[int, int, int]],
    gset: Optional[set],
) -> Tuple[Tuple[int, int, int], float, float, Optional[float]]:
    """Float64 phase-identity scan, then literal scores for the recorded I."""
    mag = np.abs(sums)
    if not np.all(np.isfinite(mag)) or np.any(mag == 0):
        raise ZeroDivisionError("bucket sum component has modulus 0")
    q = np.conjugate(sums / mag)
    n_buckets, d = q.shape
    best_I = -math.inf
    best: Tuple[int, int, int] = (0, 1, 2)
    best_imp_I = -math.inf
    best_imp: Tuple[int, int, int] = (0, 1, 2)
    g_list = [] if gset is None else sorted(gset)
    for b in range(n_buckets - 2):
        rest = q[b + 1 :]
        gram = ((rest * (s * q[b])) @ rest.T).real
        m = gram.shape[0]
        iu, ju = _triu(m)
        vals = gram[iu, ju] / d
        gs = iu + (b + 1)
        ds = ju + (b + 1)
        j = int(np.argmax(vals))
        if float(vals[j]) > best_I:
            best_I = float(vals[j])
            best = (b, int(gs[j]), int(ds[j]))
        if len(g_list) == 3:
            cover = (b == g_list[0]) & (gs == g_list[1]) & (ds == g_list[2])
        elif len(g_list) == 2:
            a, c = g_list
            present = (np.full(vals.shape, b) == a) + (gs == a) + (ds == a)
            present += (np.full(vals.shape, b) == c) + (gs == c) + (ds == c)
            cover = present == 2
        elif len(g_list) == 1:
            a = g_list[0]
            cover = (np.full(vals.shape, b) == a) | (gs == a) | (ds == a)
        else:
            cover = np.zeros(vals.shape, dtype=bool)
        if np.any(~cover):
            k = int(np.argmax(np.where(cover, -np.inf, vals)))
            if float(vals[k]) > best_imp_I:
                best_imp_I = float(vals[k])
                best_imp = (b, int(gs[k]), int(ds[k]))
    pool = [best]
    if best_imp not in pool:
        pool.append(best_imp)
    if gen_trip is not None and gen_trip not in pool:
        pool.append(gen_trip)
    lit_vals = _literal_scores(s, sums, np.asarray(pool, dtype=np.int32))
    lit = {pool[i]: float(lit_vals[i]) for i in range(len(pool))}
    winner = max(lit.items(), key=lambda kv: kv[1])[0]
    gen_I = None if gen_trip is None else lit[gen_trip]
    return winner, float(lit[winner]), float(lit[best_imp]), None if gen_I is None else float(gen_I)


def exact_codeword_scan(
    codebook: np.ndarray,
    s: np.ndarray,
    assignment: np.ndarray,
    buckets: Sequence[int],
) -> Dict[str, Any]:
    """One step: best one-from-each-bucket codeword triple under locked I vs s."""
    members = [np.flatnonzero(assignment == int(b)) for b in buckets]
    if any(len(m) == 0 for m in members):
        raise ValueError("empty winning bucket")
    best_I = -math.inf
    best: Tuple[int, int, int] = (int(members[0][0]), int(members[1][0]), int(members[2][0]))
    for i, j, k in itertools.product(*members):
        prod = codebook[i] * codebook[j] * codebook[k]
        val = invertibility(s, prod)
        if val > best_I:
            best_I = float(val)
            best = (int(i), int(j), int(k))
    return {"codewords": list(best), "I_vs_s": float(best_I)}


def _retrieve(
    codebook: np.ndarray,
    true_idx: np.ndarray,
    recovered_idx: Sequence[int],
) -> Dict[str, Any]:
    """Locked designated-factor I and retrieval_hit. Same rule as run_trial."""
    estimates = [codebook[int(i)] for i in recovered_idx]
    target = int(true_idx[0])
    slot_scores = [invertibility(codebook[target], est) for est in estimates]
    slot = int(np.argmax(slot_scores))
    recovered = estimates[slot]
    d = codebook.shape[1]
    scores = np.real(codebook @ np.conjugate(recovered)) / d
    chosen = int(np.argmax(scores))
    # Matched factor-wise I over the 6 permutations. Diagnostic, not the cell I.
    truth = [codebook[int(i)] for i in true_idx]
    best_mean = -math.inf
    for perm in itertools.permutations(range(3)):
        vals = [invertibility(truth[t], estimates[perm[t]]) for t in range(3)]
        best_mean = max(best_mean, float(np.mean(vals)))
    return {
        "I": float(slot_scores[slot]),
        "retrieval_hit": bool(chosen == target),
        "chosen_index": chosen,
        "target_index": target,
        "aligned_slot": slot,
        "recovered_codewords": [int(i) for i in recovered_idx],
        "matched_factor_I_mean": float(best_mean),
    }


def run_bucket_trial(
    codebook: np.ndarray,
    rng_entropy_children: Sequence[Any],
    *,
    bucket_size: int = 5,
    k: int = 3,
    t_max: int = T_MAX,
    threshold: float = THRESHOLD,
    topk: int = 8,
) -> Dict[str, Any]:
    """One falsifier trial.

    children[0] draws the three generators. children[1 + attempt] draws an
    independent bucket hash. gamma is 0: s is exactly the product.
    """
    if k != 3:
        raise ValueError("this falsifier is the k=3 bucket triple")
    m, d = codebook.shape
    n_buckets = m // bucket_size
    gen_rng = np.random.default_rng(rng_entropy_children[0])
    true_idx = gen_rng.choice(m, size=k, replace=False).astype(np.int64)
    bound = bind_factors(codebook[true_idx])
    projected, faults = phasor_project(bound)
    if faults:
        return {
            "projection_faults": int(faults),
            "excluded": True,
            "generator_indices": [int(x) for x in true_idx],
            "collision": None,
            "winner_contains_all_generators": None,
            "winner_I": None,
            "best_impostor_I": None,
            "generator_I": None,
            "gap": None,
            "rehash_used": False,
            "n_hashes": 0,
            "steps_used": 0,
            "recovery_performed": False,
            "retrieval_hit": None,
            "I": None,
            "threshold_cleared": False,
        }
    s = projected
    steps = 0
    n_hashes = 0
    rehash_used = False
    last: Optional[Dict[str, Any]] = None
    max_winner_I = -math.inf
    full_scans = 0
    screen_err = 0.0
    while steps < t_max:
        need_hash = last is None or float(last["winner_I"]) < threshold
        if need_hash:
            if n_hashes > 0:
                rehash_used = True
            hash_rng = np.random.default_rng(rng_entropy_children[1 + n_hashes])
            assignment = _partition(m, bucket_size, hash_rng)
            try:
                sums = _bucket_sums(codebook, assignment, n_buckets)
                buckets = assignment[true_idx]
                distinct = sorted({int(b) for b in buckets})
                collision = len(distinct) < 3
                ranked = rank_triples(sums, s, [int(b) for b in buckets], topk=topk)
            except ZeroDivisionError:
                return {
                    "projection_faults": 1,
                    "excluded": True,
                    "generator_indices": [int(x) for x in true_idx],
                    "collision": None,
                    "winner_contains_all_generators": None,
                    "winner_I": None,
                    "best_impostor_I": None,
                    "generator_I": None,
                    "gap": None,
                    "rehash_used": rehash_used,
                    "n_hashes": n_hashes,
                    "steps_used": steps,
                    "recovery_performed": False,
                    "retrieval_hit": None,
                    "I": None,
                    "threshold_cleared": False,
                }
            n_hashes += 1
            steps += 1
            if ranked.get("used_full_scan"):
                full_scans += 1
            screen_err = max(screen_err, float(ranked["screen_max_abs_error"]))
            win_set = set(int(b) for b in ranked["winner_buckets"])
            contains = all(int(assignment[int(i)]) in win_set for i in true_idx)
            last = {
                "assignment": assignment,
                "sums": sums,
                "collision": bool(collision),
                "generator_buckets": [int(b) for b in buckets],
                "winner_buckets": ranked["winner_buckets"],
                "winner_contains_all_generators": bool(contains),
                "winner_I": ranked["winner_I"],
                "best_impostor_I": ranked["best_impostor_I"],
                "generator_I": ranked["generator_I"],
                "gap": ranked["gap"],
                "n_scored": ranked["n_scored"],
            }
            max_winner_I = max(max_winner_I, float(ranked["winner_I"]))
            continue
        scanned = exact_codeword_scan(
            codebook, s, last["assignment"], last["winner_buckets"]
        )
        retrieved = _retrieve(codebook, true_idx, scanned["codewords"])
        steps += 1
        return _finish(
            true_idx,
            last,
            steps=steps,
            n_hashes=n_hashes,
            rehash_used=rehash_used,
            max_winner_I=max_winner_I,
            full_scans=full_scans,
            screen_err=screen_err,
            recovery=retrieved,
            scan_I=scanned["I_vs_s"],
            threshold=threshold,
        )
    assert last is not None
    return _finish(
        true_idx,
        last,
        steps=steps,
        n_hashes=n_hashes,
        rehash_used=rehash_used,
        max_winner_I=max_winner_I,
        full_scans=full_scans,
        screen_err=screen_err,
        recovery=None,
        scan_I=None,
        threshold=threshold,
    )


def _finish(
    true_idx: np.ndarray,
    last: Dict[str, Any],
    *,
    steps: int,
    n_hashes: int,
    rehash_used: bool,
    max_winner_I: float,
    full_scans: int,
    screen_err: float,
    recovery: Optional[Dict[str, Any]],
    scan_I: Optional[float],
    threshold: float,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "projection_faults": 0,
        "excluded": False,
        "generator_indices": [int(x) for x in true_idx],
        "collision": bool(last["collision"]),
        "generator_buckets": list(last["generator_buckets"]),
        "winner_buckets": list(last["winner_buckets"]),
        "winner_contains_all_generators": bool(last["winner_contains_all_generators"]),
        "winner_I": float(last["winner_I"]),
        "best_impostor_I": float(last["best_impostor_I"]),
        "generator_I": last["generator_I"],
        "gap": last["gap"],
        "rehash_used": bool(rehash_used),
        "n_hashes": int(n_hashes),
        "steps_used": int(steps),
        "max_winner_I_across_hashes": float(max_winner_I),
        "threshold": float(threshold),
        "threshold_cleared": bool(max_winner_I >= threshold),
        "n_bucket_triples_scored_last_hash": int(last["n_scored"]),
        "full_scan_fallbacks": int(full_scans),
        "screen_max_abs_error": float(screen_err),
        "recovery_performed": recovery is not None,
        "retrieval_hit": False if recovery is None else bool(recovery["retrieval_hit"]),
        "I": None if recovery is None else float(recovery["I"]),
    }
    if recovery is not None:
        row["chosen_index"] = recovery["chosen_index"]
        row["target_index"] = recovery["target_index"]
        row["aligned_slot"] = recovery["aligned_slot"]
        row["recovered_codewords"] = recovery["recovered_codewords"]
        row["matched_factor_I_mean"] = recovery["matched_factor_I_mean"]
        row["exact_scan_I_vs_s"] = float(scan_I) if scan_I is not None else None
    return row


def _trial_sequences(trial_seed: int, n_trials: int, t_max: int) -> List[List[Any]]:
    """Per trial: spawn(1 + t_max) children. Hash attempt a uses child 1+a."""
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


def _summarize(rows: List[Dict[str, Any]], *, bootstrap_seed: int) -> Dict[str, Any]:
    usable = [r for r in rows if not r.get("excluded")]
    hits = [1 if r.get("retrieval_hit") else 0 for r in usable]
    n = len(hits)
    successes = int(sum(hits))
    acc = None if n == 0 else successes / n
    cp = None if n == 0 else clopper_pearson(successes, n)
    recovered_I = [float(r["I"]) for r in usable if r.get("I") is not None]
    # Mean I is defined only when every usable trial recovered factors.
    # Imputing a value for a trial that never ran cleanup would invent a score.
    complete_I = len(recovered_I) == n and n > 0
    boot = bootstrap_mean_ci(recovered_I, bootstrap_seed, BOOTSTRAP_B) if complete_I else None
    gaps = [float(r["gap"]) for r in usable if r.get("gap") is not None]
    gap_arr = np.asarray(gaps, dtype=np.float64)
    if gap_arr.size:
        qs = np.quantile(gap_arr, [0.05, 0.25, 0.5, 0.75, 0.95])
        gap_summary = {
            "n": int(gap_arr.size),
            "mean": float(gap_arr.mean()),
            "std": float(gap_arr.std(ddof=0)),
            "min": float(gap_arr.min()),
            "p05": float(qs[0]),
            "p25": float(qs[1]),
            "p50": float(qs[2]),
            "p75": float(qs[3]),
            "p95": float(qs[4]),
            "max": float(gap_arr.max()),
            "n_negative": int(np.sum(gap_arr < 0)),
            "n_positive": int(np.sum(gap_arr > 0)),
            "n_zero": int(np.sum(gap_arr == 0)),
        }
    else:
        gap_summary = {"n": 0}
    contains = [
        1 if r.get("winner_contains_all_generators") else 0
        for r in usable
        if r.get("winner_contains_all_generators") is not None
    ]
    collisions = sum(1 for r in usable if r.get("collision"))
    rehashes = sum(1 for r in usable if r.get("rehash_used"))
    extra_hashes = sum(max(0, int(r.get("n_hashes") or 0) - 1) for r in usable)
    full_scans = sum(int(r.get("full_scan_fallbacks") or 0) for r in rows)
    faults = sum(int(r.get("projection_faults") or 0) for r in rows)
    winner_Is = [float(r["winner_I"]) for r in usable if r.get("winner_I") is not None]
    acc_low = None if cp is None else cp[0]
    i_low = None if boot is None else boot[1]
    floors_met = (
        acc_low is not None
        and i_low is not None
        and acc_low >= ACC_FLOOR
        and i_low >= I_FLOOR
        and n >= 100
    )
    return {
        "n": n,
        "successes": successes,
        "retrieval_accuracy": acc,
        "retrieval_accuracy_ci95": None if cp is None else [cp[0], cp[1]],
        "accuracy_ci_low": acc_low,
        "mean_I": None if boot is None else boot[0],
        "mean_I_ci95": None if boot is None else [boot[1], boot[2]],
        "mean_I_ci_low": i_low,
        "mean_I_defined": bool(complete_I),
        "n_recovered": len(recovered_I),
        "floors_met": bool(floors_met),
        "status": "pass" if floors_met else "not_a_pass",
        "gap_distribution": gap_summary,
        "collision_count": int(collisions),
        "rehash_trial_count": int(rehashes),
        "rehash_extra_hash_count": int(extra_hashes),
        "winner_contains_count": int(sum(contains)),
        "winner_contains_rate": None if not contains else float(np.mean(contains)),
        "full_scan_fallbacks": int(full_scans),
        "projection_faults": int(faults),
        "winner_I_mean": None if not winner_Is else float(np.mean(winner_Is)),
        "winner_I_max": None if not winner_Is else float(np.max(winner_Is)),
    }


def _envelope(
    rows: List[Dict[str, Any]],
    *,
    n_target: int,
    git_sha: str,
    seconds_per_trial_first: Optional[float],
    elapsed_s: float,
) -> Dict[str, Any]:
    summary = _summarize(rows, bootstrap_seed=BOOTSTRAP_SEED)
    n = summary["n"] + sum(1 for r in rows if r.get("excluded"))
    # n reported to the parent is the number of trials actually finished,
    # including projection-fault exclusions. Usable n is summary["n"].
    finished = len(rows)
    return {
        "label": "adl_bucket_triple_falsifier",
        "claim_class": "measured_result",
        "status": summary["status"],
        "floors_met": summary["floors_met"],
        "floors": {"mean_I_ci_low": I_FLOOR, "accuracy_ci_low": ACC_FLOOR},
        "small_n_is_not_a_pass": True,
        "pass_rule": (
            "status is pass only if n_finished>=100 and the lower Clopper-Pearson "
            "accuracy bound is >= 0.95 and the lower bootstrap bound of mean I is "
            ">= 0.92. Mean I is the locked designated-factor cosine-sum on trials "
            "that recovered factors, and only when every usable trial recovered. "
            "Otherwise mean I is null and the floors are not met. Small n is not a pass."
        ),
        "git_sha": git_sha,
        "network_access": False,
        "off_locked_path": True,
        "seed_record": {
            "codebook_seed": CODEBOOK_SEED,
            "trial_seed": TRIAL_SEED,
            "trial_seed_scheme": "SeedSequence([trial_seed, trial_index]).spawn(1+T_max)",
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_resamples": BOOTSTRAP_B,
        },
        "configuration": {
            "d": 8192,
            "M": 1000,
            "B": 200,
            "bucket_size": 5,
            "k": 3,
            "gamma": 0.0,
            "t_max": T_MAX,
            "score_threshold": THRESHOLD,
            "assumption": "s is one component-wise product of three distinct codebook phasors",
            "bucket_vector": "linear sum of codewords, not phasor-projected",
            "score": "(1/d) sum cos(phase(s * conj(v_b) * conj(v_g) * conj(v_d)))",
            "triple_enumeration": "unordered distinct buckets; score is permutation-invariant",
            "recovery": "one exact scan, one codeword from each winning bucket, if winner I>=0.7 and a step remains",
            "rehash": "while winner I<0.7 and steps remain, the next step is an independent rehash",
            "retrieval_I": "locked designated-factor cosine-sum, benchmark_metrics.invertibility",
            "n_target": int(n_target),
        },
        "n": int(finished),
        "n_target": int(n_target),
        "usable_trials": summary["n"],
        "mean_I": summary["mean_I"],
        "mean_I_ci95": summary["mean_I_ci95"],
        "mean_I_ci_low": summary["mean_I_ci_low"],
        "mean_I_defined": summary["mean_I_defined"],
        "n_recovered": summary["n_recovered"],
        "retrieval_accuracy": summary["retrieval_accuracy"],
        "retrieval_accuracy_ci95": summary["retrieval_accuracy_ci95"],
        "accuracy_ci_low": summary["accuracy_ci_low"],
        "gap_distribution": summary["gap_distribution"],
        "collision_count": summary["collision_count"],
        "rehash_trial_count": summary["rehash_trial_count"],
        "rehash_extra_hash_count": summary["rehash_extra_hash_count"],
        "winner_contains_count": summary["winner_contains_count"],
        "winner_contains_rate": summary["winner_contains_rate"],
        "winner_I_mean": summary["winner_I_mean"],
        "winner_I_max": summary["winner_I_max"],
        "full_scan_fallbacks": summary["full_scan_fallbacks"],
        "projection_faults": summary["projection_faults"],
        "seconds_first_trial": seconds_per_trial_first,
        "elapsed_s": elapsed_s,
        "trials": rows,
    }


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def self_check() -> None:
    """Brute-force the statistic on a tiny instance, and a bucket-size-1 recovery."""
    rng = np.random.default_rng(0)
    m, d, bucket_size = 30, 64, 3
    phases = rng.uniform(-math.pi, math.pi, size=(m, d))
    codebook = np.exp(1j * phases)
    true = np.array([1, 4, 9])
    s = bind_factors(codebook[true])
    assignment = _partition(m, bucket_size, np.random.default_rng(1))
    sums = _bucket_sums(codebook, assignment, m // bucket_size)
    buckets = [int(x) for x in assignment[true]]
    # Brute literal scores.
    b_count = sums.shape[0]
    best = -math.inf
    best_t = None
    gen = tuple(sorted(buckets)) if len(set(buckets)) == 3 else None
    best_imp = -math.inf
    n = 0
    for trip in itertools.combinations(range(b_count), 3):
        val = float(_literal_scores(s, sums, np.array([trip], dtype=np.int32))[0])
        n += 1
        if val > best:
            best = val
            best_t = trip
        if gen is not None and trip != gen and val > best_imp:
            best_imp = val
    ranked = rank_triples(sums, s, None if gen is None else list(gen), topk=8)
    if ranked["n_scored"] != n:
        raise AssertionError(f"scored {ranked['n_scored']} != C({b_count},3)={n}")
    if tuple(ranked["winner_buckets"]) != best_t:
        raise AssertionError(f"winner {ranked['winner_buckets']} != {best_t}")
    if abs(ranked["winner_I"] - best) > 1e-9:
        raise AssertionError(f"winner I {ranked['winner_I']} != {best}")
    if gen is not None:
        if abs(ranked["best_impostor_I"] - best_imp) > 1e-9:
            raise AssertionError("impostor mismatch")
        if abs(float(ranked["generator_I"]) - float(
            _literal_scores(s, sums, np.array([gen], dtype=np.int32))[0]
        )) > 1e-12:
            raise AssertionError("generator I mismatch")
    # Zero magnitude is a fault, not phase 0.
    bad = sums.copy()
    bad[0, 0] = 0
    try:
        _literal_scores(s, bad, np.array([[0, 1, 2]], dtype=np.int32))
    except ZeroDivisionError:
        pass
    else:
        raise AssertionError("zero component was not a fault")
    # Bucket size 1: the true triple scores 1 and clears 0.7 in one hash + scan.
    m2, d2 = 12, 32
    code2 = np.exp(1j * rng.uniform(-math.pi, math.pi, size=(m2, d2)))
    parent = np.random.SeedSequence([7, 0])
    # Force generators by replacing child 0's draw: call run with a custom path
    # through a deterministic seed and then check threshold logic via size-1
    # where EVERY triple of the true buckets scores 1 if those buckets are the
    # codewords themselves. Use run_bucket_trial and require a hit whenever the
    # first hash isolates the three generators, which size 1 always does.
    row = run_bucket_trial(
        code2,
        list(parent.spawn(1 + 7)),
        bucket_size=1,
        t_max=7,
        threshold=0.7,
        topk=16,
    )
    if row["excluded"]:
        raise AssertionError("size-1 trial faulted")
    if not row["threshold_cleared"] or row["rehash_used"]:
        raise AssertionError(f"size-1 should clear 0.7 without rehash: {row['winner_I']}")
    if not row["retrieval_hit"] or abs(float(row["I"]) - 1.0) > 1e-9:
        raise AssertionError(f"size-1 retrieval failed: {row}")
    if row["steps_used"] != 2:
        raise AssertionError(f"expected hash+scan, steps={row['steps_used']}")
    # High threshold burns the budget on rehashes and does not invent a hit.
    row2 = run_bucket_trial(
        code2,
        list(np.random.SeedSequence([7, 1]).spawn(1 + 7)),
        bucket_size=1,
        t_max=7,
        threshold=1.01,
        topk=16,
    )
    if row2["retrieval_hit"] or row2["I"] is not None or row2["n_hashes"] != 7:
        raise AssertionError(f"threshold gate failed: {row2}")
    if not row2["rehash_used"]:
        raise AssertionError("rehash flag")


def run_falsifier(
    *,
    n_target: int,
    out: Path,
    root: Path,
    resume: bool = True,
) -> Dict[str, Any]:
    git_sha = _git_sha(root)
    codebook = sample_codebook(1000, 8192, CODEBOOK_SEED)
    sequences = _trial_sequences(TRIAL_SEED, n_target, T_MAX)
    rows: List[Dict[str, Any]] = []
    if resume and out.exists():
        prior = json.loads(out.read_text(encoding="utf-8"))
        if (
            prior.get("seed_record", {}).get("trial_seed") == TRIAL_SEED
            and prior.get("seed_record", {}).get("codebook_seed") == CODEBOOK_SEED
            and prior.get("configuration", {}).get("d") == 8192
        ):
            rows = list(prior.get("trials") or [])
            if len(rows) > n_target:
                rows = rows[:n_target]
    t0 = time.perf_counter()
    first_s = None
    for i in range(len(rows), n_target):
        ts = time.perf_counter()
        row = run_bucket_trial(codebook, sequences[i], bucket_size=5, k=3, t_max=T_MAX)
        row["trial_index"] = i
        row["trial_seed"] = [TRIAL_SEED, i]
        dt = time.perf_counter() - ts
        row["seconds"] = dt
        if first_s is None and i == 0:
            first_s = dt
        elif first_s is None:
            first_s = prior_first(out)
        rows.append(row)
        payload = _envelope(
            rows,
            n_target=n_target,
            git_sha=git_sha,
            seconds_per_trial_first=first_s if i == 0 or len(rows) == 1 else _first_seconds(rows),
            elapsed_s=time.perf_counter() - t0,
        )
        _write(out, payload)
        print(
            f"trial {i} {dt:.2f}s winner_I={row['winner_I']} contains={row['winner_contains_all_generators']} "
            f"gap={row['gap']} rehash={row['rehash_used']} hit={row['retrieval_hit']} "
            f"fallbacks={row['full_scan_fallbacks']}",
            flush=True,
        )
    payload = _envelope(
        rows,
        n_target=n_target,
        git_sha=git_sha,
        seconds_per_trial_first=_first_seconds(rows),
        elapsed_s=time.perf_counter() - t0,
    )
    _write(out, payload)
    return payload


def _first_seconds(rows: List[Dict[str, Any]]) -> Optional[float]:
    if not rows:
        return None
    return rows[0].get("seconds")


def prior_first(out: Path) -> Optional[float]:
    return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run Adl's bucket-triple falsifier")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/workspace/sovereign-clean-room/results/bucket_triple_falsifier.json"),
    )
    parser.add_argument("--skip-self-check", action="store_true")
    args = parser.parse_args()
    if not args.skip_self_check:
        t0 = time.perf_counter()
        self_check()
        print(f"self_check ok {time.perf_counter() - t0:.2f}s", flush=True)
    root = Path("/workspace/sovereign-clean-room")
    payload = run_falsifier(n_target=args.n, out=args.out, root=root, resume=True)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "n": payload["n"],
                "floors_met": payload["floors_met"],
                "mean_I": payload["mean_I"],
                "accuracy": payload["retrieval_accuracy"],
                "accuracy_ci_low": payload["accuracy_ci_low"],
                "winner_contains_rate": payload["winner_contains_rate"],
                "winner_I_max": payload["winner_I_max"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

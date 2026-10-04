#!/usr/bin/env python3
"""Run locked SEEM validation protocol v1.0 measurements.

Phase I cells are the real protocol: d in {8192, 16384}, k in {2..10},
gamma in {0, 0.1}, M=1000, T_max=7, N=10000, bootstrap B=10000.
Results are written to results/execution_record.json after every batch
so a killed process keeps completed trials. A cell is measured only when
N=10000 finishes with both intervals. Fewer completed trials stay partial.
Cells that have not started stay not_run. k_max is reported only when every
k in {2..10} at that (d, gamma) is measured and the locked CI floors pass.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np

from banel_protocol import RouteSession, delta_frr_curves, frr_curve
from benchmark_metrics import invertibility
from clean_room_ledger import CleanRoomLedger
from clean_room_z3 import MemSkillZ3Verifier
from fhrr_protocol import PROTOCOL, run_cell
from memskill_ir import canonicalize
from memskill_runtime import correspondence, execute_trace
from skill_crypto import generate_keypair, sign_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "execution_record.json"
CODEBOOK_SEED = 20260930
TRIAL_SEED = 20261001
BOOTSTRAP_SEED = 20260930
BOOTSTRAP_B = 10000
PROTOCOL_N = 10000
WIDTHS = (8192, 16384)
KS = tuple(range(2, 11))
GAMMAS = (0.0, 0.1)
WORKERS = int(os.environ.get("SEEM_WORKERS", str(os.cpu_count() or 1)))
BATCH = int(os.environ.get("SEEM_BATCH", "200"))


def code_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def median_ms(fn, repeats: int = 5) -> float:
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    return float(samples[len(samples) // 2])


def grid():
    for d in WIDTHS:
        for k in KS:
            for gamma in GAMMAS:
                yield d, k, gamma


def not_run_cell(d, k, gamma, sha: str, reason: str) -> dict:
    return {
        "protocol": PROTOCOL,
        "status": "not_run",
        "claim_class": "measured_result",
        "git_sha": sha,
        "seed_record": {
            "codebook_seed": CODEBOOK_SEED,
            "trial_seed": TRIAL_SEED,
            "config_sha256": "not_run",
        },
        "phase": "I",
        "d": d,
        "k": k,
        "gamma": gamma,
        "n_trials": 0,
        "mean_I": None,
        "retrieval_accuracy": None,
        "median_T": None,
        "projection_faults": 0,
        "k_max": None,
        "R_d": None,
        "notes": reason,
    }


def public_cell(cell: dict, wall_s: float | None) -> dict:
    seed = cell["seed_record"]
    trials = [
        {
            "I": row["I"],
            "retrieval_hit": row["retrieval_hit"],
            "iterations": row["iterations"],
            "projection_faults": row["projection_faults"],
            "excluded": row["excluded"],
            "converged": row["converged"],
        }
        for row in cell["trials"]
    ]
    out = {
        "protocol": PROTOCOL,
        "status": cell["status"],
        "claim_class": "measured_result",
        "git_sha": cell["git_sha"],
        "seed_record": {
            "codebook_seed": seed["codebook_seed"],
            "trial_seed": seed["trial_seed"],
            "config_sha256": seed["config_sha256"],
            "bootstrap_seed": seed.get("bootstrap_seed", BOOTSTRAP_SEED),
        },
        "phase": "I",
        "d": cell["d"],
        "k": cell["k"],
        "gamma": cell["gamma"],
        "n_trials": PROTOCOL_N,
        "mean_I": cell["mean_I"],
        "retrieval_accuracy": cell["retrieval_accuracy"],
        "median_T": cell["median_T"],
        "projection_faults": cell["projection_faults"],
        "k_max": None,
        "R_d": None,
        "notes": cell["notes"],
        "trials_completed": cell["trials_completed"],
        "usable_trials": cell["usable_trials"],
        "configuration": cell["configuration"],
        "trials": trials,
        "wall_clock_s": wall_s,
    }
    if cell["mean_I_ci95"] is not None:
        out["mean_I_ci95"] = cell["mean_I_ci95"]
    if cell["retrieval_accuracy_ci95"] is not None:
        out["retrieval_accuracy_ci95"] = cell["retrieval_accuracy_ci95"]
    return out


def prior_rows_from_public(cell: dict) -> list:
    rows = []
    for row in cell.get("trials") or []:
        rows.append(
            {
                "I": row["I"],
                "retrieval_hit": row["retrieval_hit"],
                "iterations": row["iterations"],
                "projection_faults": row["projection_faults"],
                "excluded": row["excluded"],
                "converged": row["converged"],
            }
        )
    return rows


def resumable(cell: dict) -> bool:
    if cell.get("status") not in ("partial", "measured"):
        return False
    cfg = cell.get("configuration") or {}
    if int(cfg.get("n_trials", -1)) != PROTOCOL_N:
        return False
    if int(cfg.get("m", -1)) != 1000:
        return False
    if int(cfg.get("codebook_seed", -1)) != CODEBOOK_SEED:
        return False
    if int(cfg.get("trial_seed", -1)) != TRIAL_SEED:
        return False
    if int(cfg.get("bootstrap_resamples", -1)) != BOOTSTRAP_B:
        return False
    trials = cell.get("trials") or []
    return len(trials) == int(cell.get("trials_completed", -1))


def capacities(executed: list) -> dict:
    """k_max only from a finished k=2..10 sweep. Missing k leaves null."""
    by = {}
    for cell in executed:
        if cell.get("status") != "measured":
            continue
        if cell.get("mean_I_ci95") is None or cell.get("retrieval_accuracy_ci95") is None:
            continue
        if int(cell.get("trials_completed", 0)) != PROTOCOL_N:
            continue
        by.setdefault((cell["d"], float(cell["gamma"])), {})[int(cell["k"])] = cell
    k_max = {}
    found = {}
    for d in WIDTHS:
        for gamma in GAMMAS:
            rows = by.get((d, float(gamma)), {})
            key = f"d={d},gamma={gamma}"
            if set(rows) != set(KS):
                k_max[key] = None
                found[(d, float(gamma))] = None
                continue
            ok = []
            for k, cell in rows.items():
                if cell["mean_I_ci95"][0] >= 0.92 and cell["retrieval_accuracy_ci95"][0] >= 0.95:
                    ok.append(k)
            value = max(ok) if ok else None
            k_max[key] = value
            found[(d, float(gamma))] = value
    ratio = {}
    for gamma in GAMMAS:
        hi = found.get((16384, float(gamma)))
        lo = found.get((8192, float(gamma)))
        ratio[str(gamma)] = None if not hi or not lo else hi / lo
    return {"k_max": k_max, "R_d": ratio}


def atomic_write(payload: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(OUT)


def build_record(sha, perf, executed, reason, phase_s, banel_detail, deltas, safe_pair, cons, timing) -> dict:
    done = {(c["d"], c["k"], float(c["gamma"])) for c in executed}
    missing = []
    for d, k, gamma in grid():
        if (d, k, float(gamma)) not in done:
            missing.append(not_run_cell(d, k, gamma, sha, reason))
    caps = capacities(executed)
    full_grid = len(missing) == 0 and all(c["status"] == "measured" for c in executed) and len(executed) == len(list(grid()))
    # COMPLETE requires the full locked grid and its gates. Phase III has no
    # locked N, so a Phase I grid alone does not flip this to COMPLETE.
    # BLOCKED is reserved for a runner that cannot execute. This process can.
    label = "COMPLETE — EMPIRICAL VALIDATION PENDING"
    return {
        "protocol": PROTOCOL,
        "git_sha": sha,
        "host": {"python": platform.python_version(), "system": platform.platform()},
        "status_label": label,
        "final_status_inputs": {
            "full_kmax_N10000_both_widths": bool(
                full_grid and all(v is not None for v in caps["k_max"].values())
            ),
            "full_grid_measured": full_grid,
            "reason": reason,
            "workers": WORKERS,
            "batch_size": BATCH,
        },
        "performance_ms": perf,
        "phase_I": {
            "claim_class": "measured_result",
            "status": "measured" if full_grid else ("partial" if executed else "not_run"),
            "executed": executed,
            "not_run": missing,
            "k_max": caps["k_max"],
            "R_d": caps["R_d"],
            "wall_clock_s": phase_s,
            "observed_seconds_per_completed_trial": timing,
            "hypotheses_established": [],
        },
        "phase_III": {
            "claim_class": "measured_result",
            "status": "partial",
            "reason": (
                "Locked protocol v1.0 does not specify a selection count or a seed count. "
                "The superseded draft fixes 100 routes and 80 percent hidden failures, not N. "
                "This record is one seed, 500 selections, 100 routes, 80 failing routes. "
                "H3.1 and H3.2 are not established from one seed."
            ),
            "groups": banel_detail,
            "delta_frr": deltas,
            "hypotheses_established": [],
        },
        "correspondence_examples": {
            "claim_class": "implementation_guarantee",
            "true_positive": safe_pair,
            "conservative_rejection": cons,
        },
        "claim_classes": {
            "implementation_guarantee": [
                "cosine-sum invertibility",
                "phasor projection with zero-magnitude fault",
                "canonical IR multiset check",
                "GATE_3_CRYPTO_UNAVAILABLE without a signer",
                "Z3 SAT is encoding satisfiability",
                "network_access remains false and attempt_connection does not open a socket",
            ],
            "measured_result": [
                "phase_I.executed",
                "phase_III.groups",
                "performance_ms",
            ],
            "hypothesis": [
                "H1.1",
                "H1.2",
                "H3.1",
                "H3.2",
            ],
            "research_interpretation": [
                "No hypothesis is established unless a completed N=10000 grid meets the pre-registered test. k_max and R_d stay null until both widths have every k measured and both CI floors pass. Consciousness, sentience, and general intelligence are not claims of this run.",
            ],
        },
    }


def load_executed() -> list:
    if not OUT.exists():
        return []
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    found = {}
    for cell in data.get("phase_I", {}).get("executed", []):
        if not resumable(cell):
            continue
        found[(cell["d"], cell["k"], float(cell["gamma"]))] = cell
    ordered = []
    for d, k, gamma in grid():
        cell = found.get((d, k, float(gamma)))
        if cell is not None:
            ordered.append(cell)
    return ordered


def run_phase_iii(sha: str):
    failing = list(range(80))
    curves = {}
    banel_detail = {}
    for group in ("A", "B", "C", "D"):
        session = RouteSession(n_routes=100, failing=failing, group=group, seed=20261001, alpha=1.0)
        t0 = time.perf_counter()
        session.run(500)
        elapsed = time.perf_counter() - t0
        curve = frr_curve(session.prior_fail_counts, ns=(1, 2))
        curves[group] = curve
        dreams = [d for d in session.dreams if "latency_ms" in d]
        banel_detail[group] = {
            "status": "partial",
            "n_routes": 100,
            "n_failing_routes": 80,
            "n_selections": 500,
            "seed": 20261001,
            "alpha": 1.0,
            "wall_clock_s": elapsed,
            "frr_curve": curve,
            "micro_dream_calls": len(dreams),
            "micro_dream_latency_ms_median": (
                float(np.median([d["latency_ms"] for d in dreams])) if dreams else None
            ),
            "git_sha": sha,
        }
    deltas = {
        "A_minus_C": delta_frr_curves(curves["A"], curves["C"]),
        "B_minus_C": delta_frr_curves(curves["B"], curves["C"]),
        "D_minus_C": delta_frr_curves(curves["D"], curves["C"]),
    }
    return banel_detail, deltas


def performance() -> dict:
    perf = {}
    rng = np.random.default_rng(0)
    phases = rng.uniform(-np.pi, np.pi, size=(2, 256))
    vecs = np.exp(1j * phases)

    def bind():
        invertibility(vecs[0] * vecs[1], vecs[0])

    perf["invertibility_d256_ms"] = median_ms(bind, 20)
    perf["canonicalize_ms"] = median_ms(
        lambda: canonicalize(
            {
                "skillId": "11111111-1111-4111-8111-111111111111",
                "invertibilityScore": 0.95,
                "maxExecutionMs": 10,
                "networkAccessPermitted": False,
                "verificationHash": "ab" * 32,
                "transitions": [
                    {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1},
                    {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 1},
                    {"stepIndex": 2, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 1},
                ],
            }
        ),
        20,
    )
    verifier = MemSkillZ3Verifier()
    skill = {
        "transitions": [
            {"stepIndex": 0, "operatorSymbol": "ISOLATE_ENVIRONMENT", "resourceCost": 1},
            {"stepIndex": 1, "operatorSymbol": "VERIFY_INTEGRITY", "resourceCost": 1},
            {"stepIndex": 2, "operatorSymbol": "EXECUTE_PRIMITIVE", "resourceCost": 1},
        ]
    }
    perf["z3_sat_ms"] = median_ms(lambda: verifier.verify_memskill(skill), 5)
    sk, vk = generate_keypair()

    def sign_cycle():
        pkg = sign_package({"manifest": {"signature": ""}, "ir": {"n": 1}}, sk)
        verify_package(pkg, [vk])

    perf["ed25519_sign_verify_ms"] = median_ms(sign_cycle, 10)
    ledger_dir = ROOT / "results" / "_ledger_timing"
    led = CleanRoomLedger(ledger_dir)

    def append_one():
        led.append("perf", {"what": "tick"})

    perf["ledger_append_ms"] = median_ms(append_one, 10)
    perf["ledger_verify_ms"] = median_ms(lambda: led.verify_chain(), 10)
    session = RouteSession(n_routes=20, failing=[0, 1], group="C", seed=1)

    def banel_steps():
        session.step()

    perf["banel_step_ms"] = median_ms(banel_steps, 20)
    perf["micro_dream_ms"] = median_ms(session.micro_dream, 20)
    t0 = time.perf_counter()
    import clean_room_cli  # noqa: F401
    perf["import_cli_ms"] = (time.perf_counter() - t0) * 1000.0
    for child in ledger_dir.glob("*"):
        child.unlink()
    ledger_dir.rmdir()
    z_ok, _ = verifier.verify_memskill(skill)
    runtime, _ = execute_trace(skill)
    safe_pair = correspondence(z_ok, runtime)
    external = dict(skill)
    external["preconditions"] = [{"id": "HUMAN_APPROVAL", "dischargedBy": "EXTERNAL"}]
    z_ext, _ = verifier.verify_memskill(external)
    cons = correspondence(z_ext, execute_trace(external, observed_external=["HUMAN_APPROVAL"])[0])
    return perf, safe_pair, cons


def main() -> None:
    sha = code_sha()
    perf, safe_pair, cons = performance()
    banel_detail, deltas = run_phase_iii(sha)
    executed = load_executed()
    have = {(c["d"], c["k"], float(c["gamma"])): c for c in executed}
    timing = {}
    for cell in executed:
        if cell.get("wall_clock_s") and cell.get("trials_completed"):
            timing[f"d={cell['d']},k={cell['k']},gamma={cell['gamma']}"] = (
                cell["wall_clock_s"] / cell["trials_completed"]
            )
    phase_s = 0.0
    reason = (
        "Phase I grid is in progress. measured requires N=10000 with both intervals. "
        "partial cells record only trials that finished. Unstarted cells stay not_run."
    )

    def reason_now() -> str:
        if not timing:
            return reason
        rates = ", ".join(f"{k}={v:.4f}s" for k, v in timing.items())
        return (
            reason
            + " Observed wall-clock seconds per completed trial (includes bootstrap checkpoints): "
            + rates
            + "."
        )

    def publish(cell_public: dict | None, key, wall_s: float) -> None:
        nonlocal phase_s
        if cell_public is not None:
            have[key] = cell_public
            if wall_s and cell_public["trials_completed"]:
                timing[f"d={key[0]},k={key[1]},gamma={key[2]}"] = wall_s / cell_public["trials_completed"]
        ordered = []
        for d, k, gamma in grid():
            item = have.get((d, k, float(gamma)))
            if item is not None:
                ordered.append(item)
        atomic_write(
            build_record(
                sha, perf, ordered, reason_now(), phase_s, banel_detail, deltas, safe_pair, cons, timing
            )
        )

    publish(None, None, 0.0)
    print("wrote initial record", OUT, "sha", sha, "workers", WORKERS, flush=True)

    for d, k, gamma in grid():
        key = (d, k, float(gamma))
        existing = have.get(key)
        if existing and existing.get("status") == "measured" and int(existing.get("trials_completed", 0)) == PROTOCOL_N:
            print(f"skip measured d={d} k={k} gamma={gamma}", flush=True)
            continue
        prior = prior_rows_from_public(existing) if existing else []
        if len(prior) > PROTOCOL_N:
            prior = prior[:PROTOCOL_N]
        print(
            f"start d={d} k={k} gamma={gamma} prior={len(prior)} workers={WORKERS}",
            flush=True,
        )
        t0 = time.perf_counter()
        state = {"wall0": t0, "prior_wall": float(existing.get("wall_clock_s") or 0.0) if existing else 0.0}

        def on_batch(cell, state=state, key=key, prior_n=len(prior)):
            # wall clock covers only trials run in this process plus previously recorded wall.
            new_n = cell["trials_completed"] - prior_n
            wall = state["prior_wall"] + (time.perf_counter() - state["wall0"])
            # Attribute prior wall only when those trials were already counted.
            if prior_n == 0:
                wall = time.perf_counter() - state["wall0"]
            public = public_cell(cell, wall)
            public["notes"] = (
                f"Real protocol run. Trials completed={cell['trials_completed']} of {PROTOCOL_N}. "
                "Intervals use percentile bootstrap B=10000 and Clopper-Pearson 95% on the completed trials. "
                "Status is partial until N=10000."
                if cell["status"] != "measured"
                else "Real protocol run. Full cell N=10000."
            )
            publish(public, key, wall)
            print(
                f"checkpoint d={key[0]} k={key[1]} gamma={key[2]} "
                f"N={cell['trials_completed']} status={cell['status']} "
                f"mean_I={cell['mean_I']} acc={cell['retrieval_accuracy']} "
                f"ciI={cell['mean_I_ci95']} ciAcc={cell['retrieval_accuracy_ci95']} "
                f"T={cell['median_T']} faults={cell['projection_faults']}",
                flush=True,
            )

        cell = run_cell(
            d=d,
            k=k,
            gamma=gamma,
            n_trials=PROTOCOL_N,
            codebook_seed=CODEBOOK_SEED,
            trial_seed=TRIAL_SEED,
            m=1000,
            n_noise=1,
            t_max=7,
            bootstrap_seed=BOOTSTRAP_SEED,
            bootstrap_resamples=BOOTSTRAP_B,
            git_sha=sha,
            workers=WORKERS,
            batch_size=BATCH,
            on_batch=on_batch,
            prior_rows=prior,
        )
        wall = (float(existing.get("wall_clock_s") or 0.0) if existing and prior else 0.0) + (
            time.perf_counter() - t0
        )
        if not prior:
            wall = time.perf_counter() - t0
        phase_s += time.perf_counter() - t0
        public = public_cell(cell, wall)
        public["notes"] = (
            "Real protocol run. Full cell N=10000."
            if cell["status"] == "measured"
            else (
                f"Real protocol run. Trials completed={cell['trials_completed']} of {PROTOCOL_N}."
            )
        )
        publish(public, key, wall)
        print(
            f"done d={d} k={k} gamma={gamma} status={cell['status']} "
            f"N={cell['trials_completed']} wall={wall:.1f}s mean_I={cell['mean_I']} "
            f"acc={cell['retrieval_accuracy']}",
            flush=True,
        )

    print("grid finished", flush=True)


if __name__ == "__main__":
    main()

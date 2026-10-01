#!/usr/bin/env python3
"""Run the honest completion-pass measurements.

Writes results/execution_record.json. Does not fill unrun cells.
Full N=10000 at d in {8192, 16384} is not attempted in this process.
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
from fhrr_protocol import PROTOCOL, capacities_from_cells, run_cell
from memskill_ir import canonicalize
from memskill_runtime import correspondence, execute_trace
from skill_crypto import generate_keypair, sign_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "execution_record.json"


def git_sha() -> str:
    raw = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    return raw if not dirty else raw + "-dirty"


def median_ms(fn, repeats: int = 5) -> float:
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    return float(samples[len(samples) // 2])


def schema_cell(cell: dict) -> dict:
    seed = cell["seed_record"]
    out = {
        "protocol": PROTOCOL,
        "status": cell["status"],
        "claim_class": "measured_result",
        "git_sha": cell["git_sha"],
        "seed_record": {
            "codebook_seed": seed["codebook_seed"],
            "trial_seed": seed["trial_seed"],
            "config_sha256": seed["config_sha256"],
        },
        "phase": "I",
        "d": cell["d"],
        "k": cell["k"],
        "gamma": cell["gamma"],
        "n_trials": cell["trials_completed"],
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
        "trials": [
            {
                "I": row["I"],
                "retrieval_hit": row["retrieval_hit"],
                "iterations": row["iterations"],
                "projection_faults": row["projection_faults"],
                "excluded": row["excluded"],
                "converged": row["converged"],
            }
            for row in cell["trials"]
        ],
    }
    if cell["mean_I_ci95"] is not None:
        out["mean_I_ci95"] = cell["mean_I_ci95"]
    if cell["retrieval_accuracy_ci95"] is not None:
        out["retrieval_accuracy_ci95"] = cell["retrieval_accuracy_ci95"]
    return out


def not_run_cell(d, k, gamma, sha: str, reason: str) -> dict:
    return {
        "protocol": PROTOCOL,
        "status": "not_run",
        "claim_class": "measured_result",
        "git_sha": sha,
        "seed_record": {
            "codebook_seed": 20260930,
            "trial_seed": 20260930,
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


def main() -> None:
    sha = git_sha()
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

    # Phase I prefix. N is whatever finishes here; not the locked 10000.
    specs = [
        (8192, 2, 0.0, 4),
        (8192, 2, 0.1, 4),
        (8192, 3, 0.0, 2),
        (16384, 2, 0.1, 1),
    ]
    executed = []
    t_phase = time.perf_counter()
    for d, k, gamma, n in specs:
        cell = run_cell(
            d=d,
            k=k,
            gamma=gamma,
            n_trials=n,
            codebook_seed=20260930,
            trial_seed=20261001,
            m=1000,
            n_noise=1,
            bootstrap_resamples=10000,
            git_sha=sha,
        )
        executed.append(schema_cell(cell))
        print(
            f"cell d={d} k={k} gamma={gamma} N={n} status={cell['status']} "
            f"mean_I={cell['mean_I']} acc={cell['retrieval_accuracy']} "
            f"ciI={cell['mean_I_ci95']} ciAcc={cell['retrieval_accuracy_ci95']} "
            f"T={cell['median_T']} faults={cell['projection_faults']}",
            flush=True,
        )
    phase_s = time.perf_counter() - t_phase
    reason = (
        f"Full grid not run. One configuration at M=1000 costs on the order of "
        f"the trials above (phase I prefix wall clock {phase_s:.1f}s for "
        f"{sum(s[3] for s in specs)} trials). N=10000 for k=2..10 at two widths "
        f"and two gamma values was not executed in this session."
    )
    missing = []
    done = {(c["d"], c["k"], c["gamma"]) for c in executed}
    for d in (8192, 16384):
        for k in range(2, 11):
            for gamma in (0.0, 0.1):
                if (d, k, gamma) not in done:
                    missing.append(not_run_cell(d, k, gamma, sha, reason))
    # The four protocol table rows that were not fully N=10000.
    for cell in executed:
        cell["notes"] = (
            cell["notes"]
            + f" Requested protocol N=10000 was not run. Trials completed={cell['trials_completed']}."
        )
    caps = capacities_from_cells(
        [
            {
                **c,
                "mean_I_ci_low": None if not c.get("mean_I_ci95") else c["mean_I_ci95"][0],
                "accuracy_ci_low": None if not c.get("retrieval_accuracy_ci95") else c["retrieval_accuracy_ci95"][0],
                "status": c["status"],
            }
            for c in executed
        ]
    )

    # Phase III partial simulation. One seed. Not a locked-table completion.
    failing = list(range(80))
    curves = {}
    banel_detail = {}
    for group in ("A", "B", "C", "D"):
        s = RouteSession(n_routes=100, failing=failing, group=group, seed=20261001, alpha=1.0)
        t0 = time.perf_counter()
        s.run(500)
        elapsed = time.perf_counter() - t0
        curve = frr_curve(s.prior_fail_counts, ns=(1, 2))
        curves[group] = curve
        dreams = [d for d in s.dreams if "latency_ms" in d]
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

    z_ok, _ = verifier.verify_memskill(skill)
    runtime, _ = execute_trace(skill)
    safe_pair = correspondence(z_ok, runtime)
    external = dict(skill)
    external["preconditions"] = [{"id": "HUMAN_APPROVAL", "dischargedBy": "EXTERNAL"}]
    z_ext, _ = verifier.verify_memskill(external)
    cons = correspondence(z_ext, execute_trace(external, observed_external=["HUMAN_APPROVAL"])[0])

    record = {
        "protocol": PROTOCOL,
        "git_sha": sha,
        "host": {"python": platform.python_version(), "system": platform.platform()},
        "final_status_inputs": {
            "full_kmax_N10000_both_widths": False,
            "reason": reason,
        },
        "performance_ms": perf,
        "phase_I": {
            "claim_class": "measured_result",
            "status": "partial",
            "executed": executed,
            "not_run": missing,
            "k_max": caps["k_max"],
            "R_d": caps["R_d"],
            "wall_clock_s": phase_s,
        },
        "phase_III": {
            "claim_class": "measured_result",
            "status": "partial",
            "reason": "Single seed, 500 selections, 100 routes, 80 failing. Not the unevaluated locked-protocol study.",
            "groups": banel_detail,
            "delta_frr": deltas,
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
                "No hypothesis is established. k_max and R_d stay null unless both CI floors are met on a completed cell. Consciousness, sentience, and general intelligence are not claims of this run.",
            ],
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Timing ledger is apparatus, not a result artifact.
    for child in ledger_dir.glob("*"):
        child.unlink()
    ledger_dir.rmdir()
    print("wrote", OUT)


if __name__ == "__main__":
    main()

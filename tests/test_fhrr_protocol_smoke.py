"""Smoke the locked FHRR path. This is not a k_max measurement."""

from __future__ import annotations

import math

import numpy as np

from benchmark_metrics import invertibility, phasor_project
from fhrr_protocol import bind_factors, run_cell, sample_codebook

# Actions run 37214635678: trial 0 I differed by one displayed ulp.
# Actions run 37215706600: trial 1 I was 0.13736740691312202 vs 0.1373674069131221.
# Bound is representation drift, not a measurement claim.
_I_REL = 1e-12
_I_ABS = 1e-12


def test_codebook_is_unit_phasors_on_protocol_interval():
    codebook = sample_codebook(4, 16, 7)
    assert np.allclose(np.abs(codebook), 1.0)
    phases = np.angle(codebook)
    assert np.all(phases > -np.pi)
    assert np.all(phases <= np.pi)


def test_binding_has_no_l2_normalization():
    codebook = sample_codebook(3, 8, 1)
    bound = bind_factors(codebook[:2])
    assert np.allclose(np.abs(bound), 1.0)
    # L2 norm of a unit-phasor vector is sqrt(d), not 1.
    assert abs(float(np.linalg.norm(bound)) - math.sqrt(bound.size)) < 1e-8


def test_zero_component_is_projection_fault_not_phase_zero():
    v = np.ones(4, dtype=np.complex128)
    v[2] = 0
    out, faults = phasor_project(v)
    assert faults == 1
    assert out[2] == 0
    assert out[2] != 1  # phase 0 would be the real unit


def test_smoke_runner_is_deterministic_and_separates_hit_from_similarity():
    cell = run_cell(
        d=32, k=2, gamma=0.0, n_trials=2, codebook_seed=4, trial_seed=8,
        m=6, bootstrap_resamples=30, git_sha="smoke",
    )
    again = run_cell(
        d=32, k=2, gamma=0.0, n_trials=2, codebook_seed=4, trial_seed=8,
        m=6, bootstrap_resamples=30, git_sha="smoke",
    )
    assert cell["status"] == "partial"
    assert cell["n_trials"] == 2
    assert cell["k_max"] is None
    assert cell["trials"] == again["trials"]
    assert cell["trials"][0]["I"] == again["trials"][0]["I"]
    for row in cell["trials"]:
        if row["excluded"]:
            continue
        assert "retrieval_hit" in row and "I" in row
        # The two fields exist independently; do not derive one from the other.
        assert isinstance(row["retrieval_hit"], bool)
        assert isinstance(row["I"], float)


def test_identical_phasors_invertibility_one():
    codebook = sample_codebook(1, 16, 3)
    assert invertibility(codebook[0], codebook[0]) == 1.0


def test_parallel_workers_match_serial_prefix():
    kwargs = dict(
        d=48, k=2, gamma=0.0, n_trials=4, codebook_seed=3, trial_seed=9,
        m=8, bootstrap_resamples=20, git_sha="t",
    )
    serial = run_cell(**kwargs, workers=1)
    parallel = run_cell(**kwargs, workers=2)
    assert serial["trials"] == parallel["trials"]
    resumed = run_cell(**kwargs, workers=2, prior_rows=list(serial["trials"][:2]))
    assert resumed["trials"] == serial["trials"]
    assert resumed["status"] == "partial"


def test_locked_runner_trials_stay_bit_identical_without_variant():
    cell = run_cell(
        d=32, k=2, gamma=0.0, n_trials=2, codebook_seed=4, trial_seed=8,
        m=6, bootstrap_resamples=30, git_sha="smoke",
    )
    assert cell["seed_record"]["config_sha256"] == (
        "bcf87c53eef84d8384944ba651e4ef9c36c28582996558ce6c252e3540dce387"
    )
    assert "resonator_variant" not in cell["configuration"]
    assert math.isclose(cell["trials"][0]["I"], -0.35418412185270204, rel_tol=_I_REL, abs_tol=_I_ABS)
    assert cell["trials"][0]["iterations"] == 3
    assert math.isclose(cell["trials"][1]["I"], 0.1373674069131221, rel_tol=_I_REL, abs_tol=_I_ABS)
    assert cell["trials"][1]["iterations"] == 4
    assert cell["trials"][1]["retrieval_hit"] is True


def test_superposition_variant_is_not_a_locked_cell_and_uses_full_tmax():
    cell = run_cell(
        d=32, k=2, gamma=0.0, n_trials=2, codebook_seed=4, trial_seed=8,
        m=6, bootstrap_resamples=30, git_sha="smoke",
        variant="codebook_superposition",
    )
    again = run_cell(
        d=32, k=2, gamma=0.0, n_trials=2, codebook_seed=4, trial_seed=8,
        m=6, bootstrap_resamples=30, git_sha="smoke",
        variant="codebook_superposition", workers=2,
    )
    assert cell["status"] == "partial"
    assert cell["configuration"]["resonator_variant"] == "codebook_superposition"
    assert cell["configuration"]["m"] == 6
    assert cell["configuration"]["t_max"] == 7
    assert "Not a locked-grid cell" in cell["notes"]
    assert cell["seed_record"]["config_sha256"] != (
        "bcf87c53eef84d8384944ba651e4ef9c36c28582996558ce6c252e3540dce387"
    )
    assert cell["trials"] == again["trials"]
    for row in cell["trials"]:
        assert row["excluded"] is False
        assert row["iterations"] == 7

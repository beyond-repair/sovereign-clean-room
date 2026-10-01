"""Smoke the locked FHRR path. This is not a k_max measurement."""

from __future__ import annotations

import numpy as np

from benchmark_metrics import invertibility, phasor_project
from fhrr_protocol import bind_factors, run_cell, sample_codebook


def test_codebook_is_unit_phasors_on_protocol_interval():
    codebook = sample_codebook(4, 16, 7)
    assert np.allclose(np.abs(codebook), 1.0)
    phases = np.angle(codebook)
    assert np.all(phases > -np.pi)
    assert np.all(phases <= np.pi)


def test_binding_has_no_l2_normalization():
    import math
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

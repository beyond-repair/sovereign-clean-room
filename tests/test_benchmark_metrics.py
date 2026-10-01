"""Locked metric tests. No measured capacity claim."""

from __future__ import annotations

import numpy as np

from benchmark_metrics import clopper_pearson, invertibility, k_max, phasor_project, scaling_ratio


def test_identical_phasors_have_invertibility_one():
    rng = np.random.default_rng(0)
    phase = rng.uniform(-np.pi, np.pi, size=64)
    a = np.exp(1j * phase)
    assert invertibility(a, a) == 1.0


def test_phasor_project_restores_unit_magnitude_and_counts_zeros():
    v = np.array([2 + 0j, 0j, -3 + 4j], dtype=np.complex128)
    out, faults = phasor_project(v)
    assert faults == 1
    assert out[1] == 0
    assert np.isclose(np.abs(out[0]), 1.0)
    assert np.isclose(np.abs(out[2]), 1.0)
    assert np.isclose(out[0].real, 1.0)


def test_k_max_uses_ci_floors_and_does_not_invent_zero():
    rows = [
        {"k": 4, "mean_I_ci_low": 0.93, "accuracy_ci_low": 0.96},
        {"k": 6, "mean_I_ci_low": 0.91, "accuracy_ci_low": 0.99},
    ]
    assert k_max(rows) == 4
    assert k_max([{"k": 2, "mean_I_ci_low": 0.5, "accuracy_ci_low": 0.5}]) is None


def test_scaling_ratio_undefined_when_capacity_missing():
    assert scaling_ratio(8, 6) == 8 / 6
    assert scaling_ratio(None, 6) is None


def test_clopper_pearson_matches_known_beta_quantile():
    # 95 successes in 100 trials. Lower 95% bound is Beta(0.025; 95, 6).
    lower, upper = clopper_pearson(95, 100)
    assert abs(lower - 0.8871650888945373) < 1e-5
    assert abs(upper - 0.9835678391399704) < 1e-5
    assert clopper_pearson(0, 0) is None

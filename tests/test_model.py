"""Tests for the QALY model. Run with `uv run pytest`."""
from __future__ import annotations

import numpy as np
import pytest

from msqaly.distributions import implied_median, sample
from msqaly.model import _spearman, discounted_qale, driver_sensitivity, load_params, run

PARAMS = load_params()


# --- parameter file integrity ------------------------------------------------

def test_allocation_shares_sum_to_one():
    shares = [a["allocation_share"] for a in PARAMS["archetypes"].values()]
    assert pytest.approx(sum(shares), abs=1e-9) == 1.0


def test_every_archetype_has_a_source():
    for key, a in PARAMS["archetypes"].items():
        assert a.get("source"), f"{key} missing source"
        assert "label" in a and "allocation_share" in a and "method" in a


def test_methods_are_known():
    known = {"cost_per_qaly", "cost_per_life", "cost_per_qaly_derived_chc"}
    for a in PARAMS["archetypes"].values():
        assert a["method"] in known


# --- distribution sampling ---------------------------------------------------

def test_lognormal_ci_recovers_percentiles():
    rng = np.random.default_rng(1)
    draws = sample({"dist": "lognormal_ci", "low": 1e4, "high": 1e5}, 400_000, rng)
    assert np.percentile(draws, 5) == pytest.approx(1e4, rel=0.04)
    assert np.percentile(draws, 95) == pytest.approx(1e5, rel=0.04)


def test_loguniform_bounds_and_positivity():
    rng = np.random.default_rng(2)
    draws = sample({"dist": "loguniform", "low": 100, "high": 300}, 50_000, rng)
    assert draws.min() >= 100 and draws.max() <= 300


def test_scalar_spec_is_fixed():
    rng = np.random.default_rng(3)
    draws = sample(42.0, 10, rng)
    assert np.all(draws == 42.0)


def test_implied_median_loguniform_is_geometric_mean():
    assert implied_median({"dist": "loguniform", "low": 100, "high": 400}) == pytest.approx(200.0)


# --- discounted QALE ---------------------------------------------------------

def test_discounted_qale_zero_rate_is_simple_product():
    out = discounted_qale(np.array([20.0]), np.array([0.8]), rate=0.0)
    assert out[0] == pytest.approx(16.0)


def test_discounted_qale_is_below_undiscounted():
    yrs, util = np.array([25.0]), np.array([0.8])
    assert discounted_qale(yrs, util, 0.03)[0] < discounted_qale(yrs, util, 0.0)[0]


def test_discounted_qale_known_value():
    # u*(1-(1.03)^-25)/0.03 with u=0.75 -> ~13.06
    out = discounted_qale(np.array([25.0]), np.array([0.75]), 0.03)
    assert out[0] == pytest.approx(13.06, abs=0.1)


# --- end-to-end model --------------------------------------------------------

def test_run_is_reproducible():
    a = run(PARAMS, n=20_000, seed=7).total_qalys
    b = run(PARAMS, n=20_000, seed=7).total_qalys
    assert np.array_equal(a, b)


def test_total_qalys_positive_and_plausible():
    res = run(PARAMS, n=50_000, seed=0)
    s = res.summary()["total_qalys"]
    assert s["p05"] > 0
    # Sanity envelope: comfortably between 10k and 5M QALYs.
    assert 1e4 < s["median"] < 5e6
    assert s["p05"] < s["median"] < s["p95"]


def test_doubling_giving_doubles_qalys():
    base = run(PARAMS, n=40_000, seed=11)
    p2 = {**PARAMS, "meta": {**PARAMS["meta"], "total_giving_usd": 2 * PARAMS["meta"]["total_giving_usd"]}}
    dbl = run(p2, n=40_000, seed=11)
    ratio = np.mean(dbl.total_qalys) / np.mean(base.total_qalys)
    assert ratio == pytest.approx(2.0, rel=0.02)


def test_per_archetype_sums_to_total():
    res = run(PARAMS, n=10_000, seed=3)
    stacked = np.sum([v for v in res.per_archetype.values()], axis=0)
    assert np.allclose(stacked, res.total_qalys)


def test_frontier_is_far_above_estimate():
    res = run(PARAMS, n=20_000, seed=5)
    # Global-health frontier should be orders of magnitude more QALYs/dollar.
    assert np.median(res.frontier_qalys) > 50 * np.median(res.total_qalys)


def test_health_access_cost_per_qaly_is_reasonable():
    # Derived from causal mortality estimates -> should land in a sane band.
    res = run(PARAMS, n=50_000, seed=9)
    cpq = res.cost_per_qaly["Health - insurance & access"]
    assert 5_000 < np.median(cpq) < 150_000


def test_cost_per_qaly_floor_is_respected():
    res = run(PARAMS, n=20_000, seed=4)
    floor = PARAMS["meta"]["cost_per_qaly_floor_usd"]
    for cpq in res.cost_per_qaly.values():
        assert cpq.min() >= floor - 1e-6


# --- sensitivity -------------------------------------------------------------

def test_spearman_perfect_monotonic():
    x = np.linspace(0, 1, 500)
    assert _spearman(x, x ** 3) == pytest.approx(1.0, abs=1e-6)
    assert _spearman(x, -x ** 3) == pytest.approx(-1.0, abs=1e-6)


def test_sensitivity_signs_are_intuitive():
    res = run(PARAMS, n=60_000, seed=8)
    drivers = dict(driver_sensitivity(res))
    # Realization scales everything up -> strong positive driver.
    assert drivers["Realization factor (global)"] > 0.2
    # A higher $/QALY means less cost-effective -> negative correlation.
    neg = [v for k, v in drivers.items() if k.startswith("$/QALY")]
    assert min(neg) < 0 and max(neg) <= 0.05

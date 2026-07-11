"""Tests for the QALY model. Run with `uv run pytest`."""
from __future__ import annotations

import numpy as np
import pytest

from msqaly.cli import (
    _dollar,
    _fmt,
    inject_results,
    make_figure,
    readme_block,
    summary_markdown,
)
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
    known = {"cost_per_qaly", "cost_per_life", "cost_per_life_year"}
    for a in PARAMS["archetypes"].values():
        assert a["method"] in known


def test_giving_total_derived_from_tranches():
    meta = PARAMS["meta"]
    nominal = sum(t["nominal_usd"] for t in meta["giving_tranches"])
    real = sum(
        t["nominal_usd"] * meta["cpi_target"] / t["cpi"] for t in meta["giving_tranches"]
    )
    assert meta["total_giving_nominal_usd"] == pytest.approx(nominal)
    assert meta["total_giving_usd"] == pytest.approx(real)
    # Nominal matches the reported ~$26.3B cumulative; real-2026 sits above it.
    assert nominal == pytest.approx(26.3934e9, rel=0.001)
    assert 28e9 < real < 32e9
    assert real > nominal


def test_chc_life_years_are_converted_to_qalys():
    # cpq = cost_per_life_year / utility, so the median $/QALY must exceed the
    # median $/life-year (utility < 1). Regression for the unit-slip bug.
    res = run(PARAMS, n=50_000, seed=9)
    cpq = res.cost_per_qaly["Health - community health centers"]
    spec = PARAMS["archetypes"]["health_chc"]["cost_per_life_year_usd"]
    median_cply = implied_median(spec)
    assert np.median(cpq) > median_cply
    assert 80_000 < np.median(cpq) < 140_000


def test_write_refuses_custom_params(tmp_path):
    from msqaly.cli import main as cli_main

    with pytest.raises(SystemExit):
        cli_main(["--params", str(tmp_path / "x.yaml"), "--write"])


def test_every_archetype_has_a_valid_evidence_tier():
    tiers = PARAMS["evidence_tiers"]
    for key, a in PARAMS["archetypes"].items():
        assert "causal_credibility" in a, f"{key} missing causal_credibility"
        assert a["causal_credibility"] in tiers, f"{key} cites unknown tier"
        assert a.get("identification"), f"{key} missing identification note"


def test_evidence_tiers_are_ordered_by_credibility():
    t = PARAMS["evidence_tiers"]
    assert (t["randomized"]["mean"] > t["strong_quasi"]["mean"]
            > t["moderate_quasi"]["mean"] > t["observational"]["mean"]
            > t["assumption"]["mean"])
    # projection sits between assumption and observational, not on the main chain
    assert t["assumption"]["mean"] < t["projection"]["mean"] < t["observational"]["mean"]


def test_frontier_is_single_qaly_equivalent_parameter():
    conversions = PARAMS["conversions"]
    assert "frontier_cost_per_qaly_usd" in conversions
    assert "frontier_cost_per_daly_usd" not in conversions
    assert "daly_to_qaly_factor" not in conversions


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


def test_beta_sampling_bounds_and_mean():
    rng = np.random.default_rng(6)
    draws = sample({"dist": "beta", "mean": 0.22, "concentration": 6}, 200_000, rng)
    assert draws.min() >= 0.0 and draws.max() <= 1.0
    assert draws.mean() == pytest.approx(0.22, abs=0.01)


# --- discounted QALE ---------------------------------------------------------

def test_discounted_qale_zero_rate_is_simple_product():
    out = discounted_qale(np.array([20.0]), np.array([0.8]), rate=0.0)
    assert out[0] == pytest.approx(16.0)


def test_discounted_qale_is_below_undiscounted():
    yrs, util = np.array([25.0]), np.array([0.8])
    assert discounted_qale(yrs, util, 0.03)[0] < discounted_qale(yrs, util, 0.0)[0]


def test_discounted_qale_known_value():
    # u*(1-(1.03)^-25)/0.03 * (1.03)^0.5 with u=0.75 -> ~13.25 (half-cycle)
    out = discounted_qale(np.array([25.0]), np.array([0.75]), 0.03)
    assert out[0] == pytest.approx(13.25, abs=0.1)


def test_half_cycle_correction_raises_ordinary_annuity():
    yrs, util = np.array([25.0]), np.array([0.75])
    half = discounted_qale(yrs, util, 0.03)[0]
    ordinary = util[0] * (1 - 1.03 ** -25) / 0.03
    assert half == pytest.approx(ordinary * 1.03 ** 0.5, rel=1e-9)


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
    meta2 = {**PARAMS["meta"], "total_giving_usd": 2 * PARAMS["meta"]["total_giving_usd"]}
    p2 = {**PARAMS, "meta": meta2}
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


def test_frontier_is_handicapped_not_raw():
    # The frontier counterfactual is discounted by realization * (RCT-grade)
    # credibility, so it must sit below the raw giving / frontier_cpq value.
    res = run(PARAMS, n=40_000, seed=5)
    raw = res.total_giving / implied_median(
        PARAMS["conversions"]["frontier_cost_per_qaly_usd"]
    )
    assert np.median(res.frontier_qalys) < raw


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
    # Realization scales everything up -> positive driver.
    assert drivers["Realization factor (global)"] > 0.05
    # A higher $/QALY means less cost-effective -> negative correlation.
    neg = [v for k, v in drivers.items() if k.startswith("$/QALY")]
    assert min(neg) < 0 and max(neg) <= 0.05
    # Higher credibility keeps more of the effect -> positive correlation.
    pos = [v for k, v in drivers.items() if k.startswith("Credibility")]
    assert max(pos) > 0.05 and min(pos) >= -0.05


# --- causal credibility ------------------------------------------------------

def test_credibility_in_unit_interval():
    res = run(PARAMS, n=20_000, seed=2)
    for cred in res.credibility.values():
        assert cred.min() >= 0.0 and cred.max() <= 1.0


def test_weak_evidence_is_shrunk_below_strong():
    res = run(PARAMS, n=60_000, seed=1)
    arts = np.median(res.credibility["Arts & culture"])          # assumption tier
    mental = np.median(res.credibility["Health - mental & behavioral"])  # randomized
    assert arts < 0.2 < mental


def test_credibility_reduces_the_estimate():
    # If every tier were near-certain, the total would be strictly larger.
    base = run(PARAMS, n=40_000, seed=0)
    certain_tiers = {k: {"mean": 0.99, "concentration": 400}
                     for k in PARAMS["evidence_tiers"]}
    p2 = {**PARAMS, "evidence_tiers": certain_tiers}
    high = run(p2, n=40_000, seed=0)
    assert np.median(high.total_qalys) > 1.3 * np.median(base.total_qalys)


# --- formatting & output layer ----------------------------------------------

def test_fmt_rounds_across_unit_boundaries():
    assert _fmt(197_000) == "197k"
    assert _fmt(999_400) == "999k"
    assert _fmt(999_999) == "1.00M"      # regression: must not be '1000k'
    assert _fmt(1_850_000) == "1.85M"


def test_dollar_rounds_across_unit_boundaries():
    assert _dollar(999_400) == "$999k"
    assert _dollar(999_999) == "$1.0M"   # not '$1000k'
    assert _dollar(999_999_999) == "$1.0B"  # not '$1000M'
    assert _dollar(26_300_000_000) == "$26.3B"


def test_readme_block_uses_dynamic_figures_not_hardcoded():
    res = run(PARAMS, n=5_000, seed=0)
    block = readme_block(res, PARAMS)
    assert _dollar(res.total_giving) in block          # giving derived from params
    assert "$80/QALY" not in block                     # stale literal removed
    fc = implied_median(PARAMS["conversions"]["frontier_cost_per_qaly_usd"])
    assert _dollar(fc) in block                         # frontier derived from params


def test_summary_markdown_has_all_archetypes_and_credibility():
    res = run(PARAMS, n=3_000, seed=0)
    md = summary_markdown(res, PARAMS)
    assert "QALYs" in md and "Credibility" in md and "Evidence" in md
    for a in PARAMS["archetypes"].values():
        assert a["label"] in md


def test_inject_results_roundtrips_and_handles_missing_markers():
    text = "head\n<!-- RESULTS:START -->\nOLD\n<!-- RESULTS:END -->\ntail"
    out = inject_results(text, "NEW BLOCK")
    assert out is not None
    assert "NEW BLOCK" in out and "OLD" not in out
    assert out.startswith("head") and out.endswith("tail")
    assert inject_results("no markers here", "X") is None


def test_make_figure_writes_a_file(tmp_path):
    res = run(PARAMS, n=2_000, seed=0)
    p = tmp_path / "fig.png"
    make_figure(res, PARAMS, p)
    assert p.exists() and p.stat().st_size > 0


def test_write_refuses_no_figure():
    from msqaly.cli import main as cli_main

    with pytest.raises(SystemExit):
        cli_main(["--write", "--no-figure"])


def test_frontier_rescales_with_discount_rate():
    # The frontier prior is denominated at 3%; at a higher rate the child QALE
    # shrinks, the frontier's $/QALY rises, and frontier QALYs fall (holding
    # everything else at the same seed).
    base = run(PARAMS, n=30_000, seed=12)
    meta7 = {**PARAMS["meta"], "discount_rate": 0.07}
    hi = run({**PARAMS, "meta": meta7}, n=30_000, seed=12)
    assert np.median(hi.frontier_qalys) < 0.75 * np.median(base.frontier_qalys)
    # And at the reference rate the rescale is a no-op relative to the raw prior.
    raw = base.total_giving / implied_median(
        PARAMS["conversions"]["frontier_cost_per_qaly_usd"]
    )
    assert np.median(base.frontier_qalys) < raw


def test_spearman_handles_ties_with_midranks():
    # A constant vector must have zero correlation with anything, and heavy
    # ties must not produce spurious argsort-order correlation.
    rng = np.random.default_rng(3)
    y = rng.normal(size=4001)
    const = np.ones(4001)
    assert _spearman(const, y) == pytest.approx(0.0, abs=1e-12)
    ties = np.repeat(np.arange(13), 4001 // 13 + 1)[:4001].astype(float)
    rng.shuffle(ties)
    assert abs(_spearman(ties, y)) < 0.05

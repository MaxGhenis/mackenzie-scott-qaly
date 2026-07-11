"""The allocation centers in parameters.yaml must match the Yield Giving
derivation exactly — the YAML cannot silently drift from the data."""

import pytest

from msqaly.allocation import PASSTHROUGH, SPLIT_HEALTH, derive_shares, load_inputs
from msqaly.model import load_params


@pytest.fixture(scope="module")
def derived():
    return derive_shares()


def test_parameters_match_derivation(derived):
    shares, _ = derived
    params = load_params()
    for key, arch in params["archetypes"].items():
        assert arch["allocation_share"] == pytest.approx(shares[key], abs=1e-9), (
            f"{key}: parameters.yaml has {arch['allocation_share']}, "
            f"derivation gives {shares[key]} — rerun "
            "`uv run python -m msqaly.allocation` and update parameters.yaml"
        )


def test_shares_sum_to_one(derived):
    shares, _ = derived
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-12)


def test_every_leaf_maps_to_a_real_archetype():
    _, leaves, mapping = load_inputs()
    params = load_params()
    valid = set(params["archetypes"]) | {PASSTHROUGH, SPLIT_HEALTH}
    labels = {leaf["label"] for leaf in leaves.values()}
    assert labels <= set(mapping), sorted(labels - set(mapping))
    for label, target in mapping.items():
        assert target in valid, f"{label!r} maps to unknown target {target!r}"


def test_coverage_is_what_the_docs_claim(derived):
    _, stats = derived
    # ~two-thirds of the $26.39B nominal total carries disclosed amounts.
    assert 0.60 < stats["disclosed_usd"] / 26.39e9 < 0.72
    assert stats["n_gifts"] > 2700
    assert stats["n_disclosed"] > 2000


def test_imputation_accounts_for_the_full_ledger(derived):
    _, stats = derived
    # Disclosed + imputed dollars reproduce the announced totals (the 2019
    # gifts pool into the 2019-2021 window, whose residual absorbs them).
    assert stats["disclosed_usd"] + stats["imputed_usd"] == pytest.approx(
        26.39e9, rel=0.005
    )
    assert stats["n_undisclosed"] == 676


def test_gift_revenue_elasticity_is_sane(derived):
    _, stats = derived
    # Log-log slope of gift size on pre-gift 990 revenue, fit on disclosed
    # pairs. Positive, sub-linear-to-linear, with real explanatory power.
    assert 0.3 < stats["elasticity"] < 1.3
    assert stats["elasticity_r2"] > 0.15
    assert stats["n_calibration"] > 800
    # Most undisclosed gifts should carry a real revenue weight, not the
    # median fallback (non-US recipients lack 990s).
    assert stats["n_revenue_fallback"] / stats["n_undisclosed"] < 0.45


def test_disclosed_only_variant_still_works(derived):
    shares_no_impute, stats = derive_shares(impute=False)
    assert sum(shares_no_impute.values()) == pytest.approx(1.0, abs=1e-12)
    assert "imputed_usd" not in stats

"""Tests for the typed-units / dollar-vintage validation layer."""
from __future__ import annotations

import copy

import pytest

from msqaly.model import load_params
from msqaly.validate import DOLLAR_UNITS, ParamValidationError, validate_params

PARAMS = load_params()  # load_params itself validates; failure here fails the suite


def test_committed_file_validates():
    assert validate_params(PARAMS) is PARAMS


def test_every_dollar_spec_declares_base_year_matching_meta():
    base = PARAMS["meta"]["base_year"]

    def walk(node):
        if isinstance(node, dict):
            if node.get("unit") in DOLLAR_UNITS:
                assert node.get("dollars_base_year") == base, node
            for v in node.values():
                walk(v)

    walk(PARAMS)


def test_missing_unit_raises():
    p = copy.deepcopy(PARAMS)
    del p["conversions"]["vqaly_usd"]["unit"]
    with pytest.raises(ParamValidationError, match="missing required `unit`"):
        validate_params(p)


def test_wrong_unit_raises_with_conversion_guidance():
    # The original frontier bug: a per-DALY figure in a per-QALY slot.
    p = copy.deepcopy(PARAMS)
    p["conversions"]["frontier_cost_per_qaly_usd"]["unit"] = "usd_per_life"
    with pytest.raises(ParamValidationError, match="denominated in 'usd_per_qaly'"):
        validate_params(p)


def test_unknown_unit_raises():
    p = copy.deepcopy(PARAMS)
    p["conversions"]["frontier_cost_per_qaly_usd"]["unit"] = "usd_per_daly"
    with pytest.raises(ParamValidationError, match="unknown unit"):
        validate_params(p)


def test_stale_dollar_vintage_raises_with_inflation_guidance():
    # The original Medicaid bug: 2007-dollar figures used as current.
    p = copy.deepcopy(PARAMS)
    p["archetypes"]["health_coverage"]["cost_per_life_usd"]["dollars_base_year"] = 2007
    with pytest.raises(ParamValidationError, match="Inflate the figure to 2026 dollars"):
        validate_params(p)


def test_missing_base_year_raises():
    p = copy.deepcopy(PARAMS)
    del p["archetypes"]["health_mental"]["cost_per_qaly_usd"]["dollars_base_year"]
    with pytest.raises(ParamValidationError, match="dollars_base_year"):
        validate_params(p)


def test_unknown_method_raises():
    p = copy.deepcopy(PARAMS)
    p["archetypes"]["health_mental"]["method"] = "cost_per_widget"
    with pytest.raises(ParamValidationError, match="unknown method"):
        validate_params(p)


def test_extra_metadata_keys_do_not_break_sampling():
    # unit/dollars_base_year ride along in the spec dicts; samplers ignore them.
    import numpy as np

    from msqaly.distributions import sample

    rng = np.random.default_rng(0)
    spec = PARAMS["archetypes"]["health_mental"]["cost_per_qaly_usd"]
    draws = sample(spec, 1000, rng)
    assert draws.min() > 0

"""Malformed numerical inputs fail before they can contaminate model/export data."""

import copy

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from msqaly.model import load_params, run
from msqaly.validate import ParamValidationError, validate_params

PARAMS = load_params()
NUMERIC_PATHS = [
    ("meta", "cpi_target"), ("meta", "discount_rate"),
    ("meta", "cost_per_qaly_floor_usd"), ("meta", "giving_tranches", 0, "nominal_usd"),
    ("meta", "giving_tranches", 0, "cpi"), ("allocation_concentration",),
    ("realization_factor", "mode"), ("conversions", "vqaly_usd", "low"),
    ("conversions", "qaly_per_death_averted", "remaining_life_expectancy", "sd"),
    ("archetypes", "health_coverage", "allocation_share"),
    ("evidence_tiers", "randomized", "mean"),
    ("evidence_tiers", "randomized", "concentration"),
]


def assign(params, path, value):
    node = params
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


@given(st.sampled_from(NUMERIC_PATHS),
       st.sampled_from([float("nan"), float("inf"), -float("inf"), True, False, "NaN", None]))
def test_bad_numbers_are_rejected_at_every_numeric_boundary(path, bad):
    params = copy.deepcopy(PARAMS)
    assign(params, path, bad)
    with pytest.raises(ParamValidationError):
        validate_params(params)


@pytest.mark.parametrize("path", [
    ("meta", "cpi_target"), ("meta", "giving_tranches", 0, "nominal_usd"),
    ("meta", "giving_tranches", 0, "cpi"), ("allocation_concentration",),
    ("archetypes", "health_coverage", "allocation_share"),
    ("evidence_tiers", "randomized", "concentration"),
])
@pytest.mark.parametrize("bad", [0, -1])
def test_positive_numbers_cannot_be_nonpositive(path, bad):
    params = copy.deepcopy(PARAMS)
    assign(params, path, bad)
    with pytest.raises(ParamValidationError, match="positive"):
        validate_params(params)


@pytest.mark.parametrize("bad", [True, False, 2026.5, "2026"])
def test_base_year_is_an_integer_not_a_coercible_scalar(bad):
    params = copy.deepcopy(PARAMS)
    params["meta"]["base_year"] = bad
    with pytest.raises(ParamValidationError, match="integer year"):
        validate_params(params)


@pytest.mark.parametrize("spec", [
    {"dist": "unknown"}, {"dist": []}, {"dist": "fixed"},
    {"dist": "uniform", "low": 2, "high": 1},
    {"dist": "loguniform", "low": 0, "high": 1},
    {"dist": "lognormal_ci", "low": 1, "high": 1},
    {"dist": "triangular", "low": 0, "mode": 2, "high": 1},
    {"dist": "normal", "mean": 1, "sd": -1},
    {"dist": "normal", "mean": 1, "sd": 1, "min": 2, "max": 1},
    {"dist": "beta", "mean": 0, "concentration": 1},
    {"dist": "beta", "mean": 0.5, "concentration": 0},
])
def test_distribution_shape_is_validated_before_sampling(spec):
    params = copy.deepcopy(PARAMS)
    params["realization_factor"] = {**spec, "unit": "multiplier"}
    with pytest.raises(ParamValidationError):
        validate_params(params)


@pytest.mark.parametrize("spec", [
    {"dist": "fixed", "value": 1},
    {"dist": "uniform", "low": 0.5, "high": 1.5},
    {"dist": "loguniform", "low": 0.5, "high": 1.5},
    {"dist": "triangular", "low": 0.5, "mode": 1, "high": 1.5},
    {"dist": "normal", "mean": 1, "sd": 0.1, "min": 0.1},
    {"dist": "beta", "mean": 0.5, "concentration": 2},
    {"dist": "lognormal_ci", "low": 0.5, "high": 1.5},
])
def test_all_supported_distribution_forms_remain_valid(spec):
    params = copy.deepcopy(PARAMS)
    params["realization_factor"] = {**spec, "unit": "multiplier"}
    assert validate_params(params) is params
    assert np.isfinite(run(params, n=16).total_qalys).all()


@pytest.mark.parametrize("bad_label", ["", "  ", None, 1])
def test_archetype_labels_are_nonempty_strings(bad_label):
    params = copy.deepcopy(PARAMS)
    params["archetypes"]["health_coverage"]["label"] = bad_label
    with pytest.raises(ParamValidationError, match="nonempty label"):
        validate_params(params)


def test_duplicate_labels_cannot_overwrite_reported_components():
    params = copy.deepcopy(PARAMS)
    first, second = list(params["archetypes"])[:2]
    params["archetypes"][second]["label"] = params["archetypes"][first]["label"]
    with pytest.raises(ParamValidationError, match="duplicate archetype label"):
        validate_params(params)


@settings(max_examples=20, deadline=None)
@given(st.lists(st.text(alphabet="abcdef0123456789", min_size=1, max_size=12),
                min_size=14, max_size=14, unique=True), st.integers(0, 1000))
def test_unique_labels_preserve_component_additivity(labels, seed):
    params = copy.deepcopy(PARAMS)
    for archetype, label in zip(params["archetypes"].values(), labels, strict=True):
        archetype["label"] = label
    validate_params(params)
    result = run(params, n=32, seed=seed)
    assert len(result.per_archetype) == len(labels)
    np.testing.assert_allclose(sum(result.per_archetype.values()), result.total_qalys, rtol=1e-12)

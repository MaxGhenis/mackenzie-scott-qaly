"""Schema validation for parameters.yaml: typed units and dollar vintages.

Motivated by the two real bugs this model shipped with, both metadata errors
that lived in prose instead of structure:

  * the global-health frontier was a per-DALY figure labeled per-QALY, and
  * the Medicaid cost-per-life was quoted in 2007 dollars and used as current.

Every sampled parameter therefore declares a ``unit``, and every
dollar-denominated parameter additionally declares ``dollars_base_year``,
which must equal ``meta.base_year``. Pasting a figure in its publication-year
dollars (e.g. ``dollars_base_year: 2007``) is an error until the author
inflates it and documents the conversion in ``source`` — the bug class
becomes impossible to commit, not merely catchable in review.

``load_params`` calls :func:`validate_params` on every load, so the CLI, the
params exporter, and the test suite all refuse a malformed file.

Giving is recorded as nominal tranches (``meta.giving_tranches``) that the
loader inflates to base-year dollars, so the model's dollars and its
cost-per-QALY inputs share one price level; ``meta.total_giving_usd`` is
DERIVED by the loader, never stored. ``allocation_share`` floats are validated
separately (tests assert they sum to 1).
"""
from __future__ import annotations

from math import isfinite

ALLOWED_UNITS = {
    "usd_per_qaly",
    "usd_per_life",
    "usd_per_life_year",
    "years",
    "utility_weight",
    "fraction",
    "multiplier",
}
DOLLAR_UNITS = {"usd_per_qaly", "usd_per_life", "usd_per_life_year"}

# Expected unit for each sampled spec, by location. Archetype expectations are
# keyed by the archetype's `method`, so adding an archetype needs no edit here.
CONVERSION_UNITS = {
    "vqaly_usd": "usd_per_qaly",
    "frontier_cost_per_qaly_usd": "usd_per_qaly",
}
QALY_PER_DEATH_UNITS = {
    "remaining_life_expectancy": "years",
    "utility_weight": "utility_weight",
}
FRONTIER_CHILD_UNITS = {
    "remaining_life_years": "years",
    "utility_weight": "utility_weight",
}
VQALY_ADULT_UNITS = FRONTIER_CHILD_UNITS
METHOD_UNITS = {
    "cost_per_qaly": {"cost_per_qaly_usd": "usd_per_qaly"},
    "cost_per_life": {"cost_per_life_usd": "usd_per_life"},
    # $/life-year figures are divided by the utility-weight draw in the model
    # to become $/QALY — the life-year -> QALY conversion is explicit, never
    # a silent relabeling.
    "cost_per_life_year": {"cost_per_life_year_usd": "usd_per_life_year"},
}


class ParamValidationError(ValueError):
    """A parameter violates its numerical, unit, vintage or identity schema."""


def _number(value, path: str, *, positive: bool = False) -> float:
    try:
        valid = isinstance(value, int | float) and not isinstance(value, bool) and isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ParamValidationError(f"{path}: required finite number, not a boolean")
    if positive and value <= 0:
        raise ParamValidationError(f"{path}: must be positive")
    return float(value)


def _finite_tree(value, path: str = "parameters") -> None:
    """Reject non-finite numbers even in extra numeric export metadata."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        _number(value, path)
    elif isinstance(value, dict):
        for key, child in value.items():
            _finite_tree(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _finite_tree(child, f"{path}[{i}]")


def _check_distribution(spec: dict, path: str) -> None:
    fields = {
        "fixed": ("value",), "uniform": ("low", "high"),
        "loguniform": ("low", "high"), "triangular": ("low", "mode", "high"),
        "normal": ("mean", "sd"), "beta": ("mean", "concentration"),
        "lognormal_ci": ("low", "high"),
    }
    kind = spec.get("dist")
    if not isinstance(kind, str) or kind not in fields:
        raise ParamValidationError(f"{path}: unknown distribution {kind!r}")
    numbers = {key: _number(spec.get(key), f"{path}.{key}") for key in fields[kind]}
    if kind in {"uniform", "loguniform", "lognormal_ci", "triangular"}:
        lo, hi = numbers["low"], numbers["high"]
        if hi < lo or (kind in {"triangular", "lognormal_ci"} and hi == lo):
            raise ParamValidationError(f"{path}: distribution bounds must be ordered")
        if kind in {"loguniform", "lognormal_ci"} and lo <= 0:
            raise ParamValidationError(f"{path}: logarithmic bounds must be positive")
        if kind == "triangular" and not lo <= numbers["mode"] <= hi:
            raise ParamValidationError(f"{path}: triangular mode must be within bounds")
    elif kind == "normal":
        if numbers["sd"] < 0:
            raise ParamValidationError(f"{path}.sd: must be nonnegative")
        for key in ("min", "max"):
            if key in spec:
                _number(spec[key], f"{path}.{key}")
        if "min" in spec and "max" in spec and spec["min"] > spec["max"]:
            raise ParamValidationError(f"{path}: normal clipping bounds must be ordered")
    elif kind == "beta":
        if not 0 < numbers["mean"] < 1 or numbers["concentration"] <= 0:
            raise ParamValidationError(
                f"{path}: beta needs 0 < mean < 1 and positive concentration"
            )


def _check_spec(spec, path: str, expected_unit: str, base_year: int) -> None:
    if not isinstance(spec, dict):
        raise ParamValidationError(
            f"{path}: expected a distribution spec dict, got {type(spec).__name__}"
        )
    unit = spec.get("unit")
    if unit is None:
        raise ParamValidationError(f"{path}: missing required `unit` (expected {expected_unit!r})")
    if unit not in ALLOWED_UNITS:
        raise ParamValidationError(
            f"{path}: unknown unit {unit!r}; allowed: {sorted(ALLOWED_UNITS)}"
        )
    if unit != expected_unit:
        raise ParamValidationError(
            f"{path}: unit is {unit!r} but this slot is denominated in {expected_unit!r}. "
            "Convert the figure (and document the conversion in `source`) rather than "
            "relabeling the slot."
        )
    if unit in DOLLAR_UNITS:
        year = spec.get("dollars_base_year")
        if year is None:
            raise ParamValidationError(
                f"{path}: dollar-denominated specs must declare `dollars_base_year`."
            )
        if year != base_year:
            raise ParamValidationError(
                f"{path}: dollars_base_year is {year} but meta.base_year is {base_year}. "
                f"Inflate the figure to {base_year} dollars (e.g. CPI-U), document the "
                f"conversion in `source`, and set dollars_base_year: {base_year}."
            )
        if not isinstance(year, int) or isinstance(year, bool):
            raise ParamValidationError(f"{path}.dollars_base_year: must be an integer year")
    _check_distribution(spec, path)


def _check_tranches(meta: dict) -> None:
    """Giving is recorded as nominal tranches inflated to base-year dollars by
    the loader. Each tranche needs a year, a positive nominal amount, the CPI-U
    annual average for that year, and a source."""
    tranches = meta.get("giving_tranches")
    if not isinstance(tranches, list) or not tranches:
        raise ParamValidationError(
            "meta.giving_tranches: required non-empty list of "
            "{year, nominal_usd, cpi, source} tranches"
        )
    _number(meta.get("cpi_target"), "meta.cpi_target", positive=True)
    for i, t in enumerate(tranches):
        path = f"meta.giving_tranches[{i}]"
        if not isinstance(t, dict):
            raise ParamValidationError(f"{path}: expected a dict")
        year = t.get("year")
        if (
            not isinstance(year, int) or isinstance(year, bool)
            or not 2019 <= year <= meta["base_year"]
        ):
            raise ParamValidationError(f"{path}: year must be an int in [2019, base_year]")
        _number(t.get("nominal_usd"), f"{path}.nominal_usd", positive=True)
        _number(t.get("cpi"), f"{path}.cpi", positive=True)
        if not t.get("source"):
            raise ParamValidationError(f"{path}: missing source")


def validate_params(params: dict) -> dict:
    """Validate numerical inputs and metadata; return params unchanged if valid."""
    _finite_tree(params)
    meta = params["meta"]
    base_year = meta.get("base_year")
    if (
        not isinstance(base_year, int) or isinstance(base_year, bool)
        or not 2019 <= base_year <= 9999
    ):
        raise ParamValidationError("meta.base_year: expected an integer year in [2019, 9999]")
    _number(meta.get("discount_rate"), "meta.discount_rate")
    _number(meta.get("cost_per_qaly_floor_usd", 5000),
            "meta.cost_per_qaly_floor_usd", positive=True)
    for key in ("total_giving_usd", "total_giving_nominal_usd"):
        if key in meta:
            _number(meta[key], f"meta.{key}", positive=True)
    _number(params.get("allocation_concentration", 50), "allocation_concentration", positive=True)
    _check_tranches(params["meta"])

    conv = params["conversions"]
    for key, expected in CONVERSION_UNITS.items():
        _check_spec(conv[key], f"conversions.{key}", expected, base_year)
    qd = conv["qaly_per_death_averted"]
    for key, expected in QALY_PER_DEATH_UNITS.items():
        _check_spec(qd[key], f"conversions.qaly_per_death_averted.{key}", expected, base_year)
    fc = conv["frontier_child"]
    for key, expected in FRONTIER_CHILD_UNITS.items():
        _check_spec(fc[key], f"conversions.frontier_child.{key}", expected, base_year)
    va = conv["vqaly_adult"]
    for key, expected in VQALY_ADULT_UNITS.items():
        _check_spec(va[key], f"conversions.vqaly_adult.{key}", expected, base_year)
    # These reference conversions are fixed scalars in model.run, not sampled.
    for group, specs in (("frontier_child", fc), ("vqaly_adult", va)):
        for key, spec in specs.items():
            if key not in FRONTIER_CHILD_UNITS:
                continue
            if spec["dist"] != "fixed":
                raise ParamValidationError(f"conversions.{group}.{key}: reference must be fixed")
            _number(spec["value"], f"conversions.{group}.{key}.value", positive=True)

    _check_spec(params["realization_factor"], "realization_factor", "multiplier", base_year)

    tiers = params.get("evidence_tiers", {})
    for name, tier in tiers.items():
        mean = _number(tier.get("mean"), f"evidence_tiers.{name}.mean")
        _number(tier.get("concentration"), f"evidence_tiers.{name}.concentration", positive=True)
        if not 0 < mean < 1:
            raise ParamValidationError(f"evidence_tiers.{name}.mean: must be in (0, 1)")

    archetypes = params["archetypes"]
    if not isinstance(archetypes, dict) or not archetypes:
        raise ParamValidationError("archetypes: required nonempty mapping")
    labels = set()
    shares = []
    for name, arche in archetypes.items():
        label = arche.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ParamValidationError(f"archetypes.{name}.label: required nonempty label")
        if label in labels:
            raise ParamValidationError(
                f"archetypes.{name}.label: duplicate archetype label {label!r}"
            )
        labels.add(label)
        shares.append(_number(arche.get("allocation_share"),
                              f"archetypes.{name}.allocation_share", positive=True))
        tier_name = arche.get("causal_credibility")
        if tier_name and tier_name not in tiers:
            raise ParamValidationError(f"archetypes.{name}: unknown evidence tier {tier_name!r}")
        method = arche.get("method", "cost_per_qaly")
        expected_fields = METHOD_UNITS.get(method)
        if expected_fields is None:
            raise ParamValidationError(f"archetypes.{name}: unknown method {method!r}")
        for field, expected in expected_fields.items():
            if field not in arche:
                raise ParamValidationError(
                    f"archetypes.{name}: method {method!r} requires `{field}`"
                )
            _check_spec(arche[field], f"archetypes.{name}.{field}", expected, base_year)

    _number(sum(shares), "archetypes.allocation_share total", positive=True)

    return params

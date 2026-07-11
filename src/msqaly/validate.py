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
    """A parameter spec is missing or mismatching unit/vintage metadata."""


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
    cpi_target = meta.get("cpi_target")
    if not isinstance(cpi_target, int | float) or cpi_target <= 0:
        raise ParamValidationError("meta.cpi_target: required positive CPI-U index value")
    for i, t in enumerate(tranches):
        path = f"meta.giving_tranches[{i}]"
        if not isinstance(t, dict):
            raise ParamValidationError(f"{path}: expected a dict")
        year = t.get("year")
        if not isinstance(year, int) or not 2019 <= year <= int(meta["base_year"]):
            raise ParamValidationError(f"{path}: year must be an int in [2019, base_year]")
        if not isinstance(t.get("nominal_usd"), int | float) or t["nominal_usd"] <= 0:
            raise ParamValidationError(f"{path}: nominal_usd must be positive")
        if not isinstance(t.get("cpi"), int | float) or t["cpi"] <= 0:
            raise ParamValidationError(f"{path}: cpi must be a positive CPI-U index value")
        if not t.get("source"):
            raise ParamValidationError(f"{path}: missing source")


def validate_params(params: dict) -> dict:
    """Validate units and dollar vintages; return params unchanged if valid."""
    base_year = int(params["meta"]["base_year"])
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

    _check_spec(params["realization_factor"], "realization_factor", "multiplier", base_year)

    for name, arche in params["archetypes"].items():
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

    return params

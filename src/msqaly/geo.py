"""Aggregate disclosed dollars by reported service geography.

Descriptive data for the site's geography chart — NOT a model input. The
model prices geography only through the ``global_health`` routing in
:mod:`msqaly.allocation`; this module just tabulates where the disclosed
dollars go, with each organization's dollars split equally across its
listed service locations (the same equal-location weighting
``nonus_fraction`` uses).

Run ``python -m msqaly.geo`` to (re)write ``web/geo.json``.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .allocation import load_inputs

# ISO-3166 alpha-2 codes appearing in the Yield locations field, rolled into
# the database's own region vocabulary. US territories with their own codes
# (as, gu) are grouped with East Asia & Pacific geographically; they are a
# rounding error (<0.5% of non-US dollars) either way.
_CODE_REGION = {
    "ke": "sub-_saharan_africa", "za": "sub-_saharan_africa",
    "sn": "sub-_saharan_africa", "ng": "sub-_saharan_africa",
    "sl": "sub-_saharan_africa", "tz": "sub-_saharan_africa",
    "ug": "sub-_saharan_africa", "gh": "sub-_saharan_africa",
    "rw": "sub-_saharan_africa", "et": "sub-_saharan_africa",
    "cd": "sub-_saharan_africa", "ml": "sub-_saharan_africa",
    "mw": "sub-_saharan_africa", "zm": "sub-_saharan_africa",
    "lr": "sub-_saharan_africa",
    "in": "south_asia", "bd": "south_asia", "pk": "south_asia",
    "np": "south_asia", "lk": "south_asia",
    "br": "latin_america&_caribbean", "mx": "latin_america&_caribbean",
    "co": "latin_america&_caribbean", "gt": "latin_america&_caribbean",
    "ht": "latin_america&_caribbean", "pe": "latin_america&_caribbean",
    "ec": "latin_america&_caribbean", "bs": "latin_america&_caribbean",
    "jm": "latin_america&_caribbean", "do": "latin_america&_caribbean",
    "hn": "latin_america&_caribbean", "ni": "latin_america&_caribbean",
    "cn": "east_asia&_pacific", "kr": "east_asia&_pacific",
    "jp": "east_asia&_pacific", "ph": "east_asia&_pacific",
    "id": "east_asia&_pacific", "vn": "east_asia&_pacific",
    "kh": "east_asia&_pacific", "mh": "east_asia&_pacific",
    "fm": "east_asia&_pacific", "pw": "east_asia&_pacific",
    "as": "east_asia&_pacific", "gu": "east_asia&_pacific",
    "au": "east_asia&_pacific", "nz": "east_asia&_pacific",
    "gb": "europe&_central_asia", "ie": "europe&_central_asia",
    "gr": "europe&_central_asia", "fr": "europe&_central_asia",
    "de": "europe&_central_asia", "ua": "europe&_central_asia",
    "tr": "europe&_central_asia",
    "eg": "middle_east&_north_africa", "jo": "middle_east&_north_africa",
    "lb": "middle_east&_north_africa", "il": "middle_east&_north_africa",
    "ye": "middle_east&_north_africa", "iq": "middle_east&_north_africa",
    "ca": "canada",
}

_LABELS = {
    "global": "Global (multi-region)",
    "sub-_saharan_africa": "Sub-Saharan Africa",
    "south_asia": "South Asia",
    "latin_america&_caribbean": "Latin America & Caribbean",
    "east_asia&_pacific": "East Asia & Pacific",
    "europe&_central_asia": "Europe & Central Asia",
    "middle_east&_north_africa": "Middle East & North Africa",
    "canada": "Canada",
    "other": "Other / unmapped",
}


def _is_us(loc: str) -> bool:
    # Mirrors allocation.nonus_fraction's US test.
    return loc.startswith("us") or loc == "north_america"


def aggregate(orgs: list) -> dict:
    """Return {us_usd, nonus_usd, regions: [{key, label, usd}]} over
    disclosed dollars, equal-split across each org's listed locations."""
    us = 0.0
    regions: Counter[str] = Counter()
    for o in orgs:
        usd = sum(g.get("amount") or 0 for g in o.get("gifts", []))
        locs = o.get("locations") or []
        if not usd or not locs:
            continue
        per = usd / len(locs)
        for loc in locs:
            if _is_us(loc):
                us += per
            else:
                key = loc if loc in _LABELS else _CODE_REGION.get(loc, "other")
                regions[key] += per
    entries = [
        {"key": k, "label": _LABELS[k], "usd": round(v)}
        for k, v in regions.most_common()
    ]
    return {
        "source": "data/yieldgiving/organisations.json (snapshot 2026-07-11)",
        "method": (
            "Disclosed gift dollars split equally across each organization's "
            "reported service locations; ISO country codes rolled into the "
            "database's region vocabulary. Descriptive data, not a model "
            "output."
        ),
        "us_usd": round(us),
        "nonus_usd": round(sum(regions.values())),
        "regions": entries,
    }


def main() -> None:
    orgs, _, _ = load_inputs()
    out = aggregate(orgs)
    path = Path(__file__).resolve().parents[2] / "web" / "geo.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {path}: US ${out['us_usd']/1e9:.2f}B, "
          f"non-US ${out['nonus_usd']/1e9:.2f}B, "
          f"{len(out['regions'])} regions")


if __name__ == "__main__":
    main()

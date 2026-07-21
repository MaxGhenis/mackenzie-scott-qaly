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

# Audit region keys (geo_audit.jsonl) -> bucket keys.
_AUDIT_REGION = {
    "sub_saharan_africa": "sub-_saharan_africa",
    "south_asia": "south_asia",
    "east_asia_pacific": "east_asia&_pacific",
    "latin_america_caribbean": "latin_america&_caribbean",
    "middle_east_north_africa": "middle_east&_north_africa",
    "europe_central_asia": "europe&_central_asia",
    "north_america_us": "us_national",
    "global_unattributable": "global",
}


def load_geo_audit(data_dir=None) -> dict[str, dict[str, float]]:
    """org name -> audited region shares for 'global'-listed orgs (terra
    sweep of the top 50 by dollars; each row cites its source_url)."""
    from .allocation import DATA_DIR

    d = Path(data_dir) if data_dir else DATA_DIR
    path = d / "geo_audit" / "geo_audit.jsonl"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        shares = {k: float(v) for k, v in (row.get("region_shares") or {}).items() if float(v) > 0}
        total = sum(shares.values())
        if total > 0:
            out[row["name"]] = {k: v / total for k, v in shares.items()}
    return out

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

_US_BUCKETS = (
    ("us_west", "US — West"),
    ("us_south", "US — South"),
    ("us_midwest", "US — Midwest"),
    ("us_northeast", "US — Northeast"),
)

# Buckets that name a reporting granularity rather than a place.
_UNSPECIFIED = {"global", "us_national", "north_america_unspec", "other"}

_LABELS = {
    "global": "Global (multi-region)",
    "us_national": "US — national / unspecified",
    "north_america_unspec": "North America (unspecified)",
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


def _bucket(loc: str) -> str:
    """Full-ledger bucket for one location slug (US and non-US alike)."""
    if loc == "us":
        return "us_national"
    if loc == "north_america":
        return "north_america_unspec"
    for prefix, _ in _US_BUCKETS:
        if loc.startswith(prefix):
            return prefix
    if loc in _LABELS:
        return loc
    return _CODE_REGION.get(loc, "other")


def aggregate_full(
    orgs: list, org_usd: list[float], audit: dict | None = None
) -> dict:
    """Bucket ALL ledger dollars (disclosed + imputed, index-aligned
    ``org_usd`` from ``derive_shares``) by service geography. When an org's
    'global' listing has audited region shares, that slice is redistributed
    accordingly (unattributable shares stay in the Global bucket)."""
    audit = audit or {}
    buckets: Counter[str] = Counter()
    labels = dict(_LABELS)
    labels.update({k: v for k, v in _US_BUCKETS})
    n_audited = 0
    for org, usd in zip(orgs, org_usd, strict=True):
        locs = org.get("locations") or []
        if not usd:
            continue
        if not locs:
            buckets["us_national"] += usd  # no locations reported
            continue
        per = usd / len(locs)
        shares = audit.get(org["name"])
        for loc in locs:
            if loc == "global" and shares:
                n_audited += 1
                for rk, sh in shares.items():
                    buckets[_AUDIT_REGION[rk]] += per * sh
            else:
                buckets[_bucket(loc)] += per
    entries = [
        {
            "key": k,
            "label": labels[k],
            "usd": round(v),
            "unspecified": k in _UNSPECIFIED,
        }
        for k, v in buckets.most_common()
    ]
    return {
        "method": (
            "All ledger dollars (disclosed + imputed) split equally across "
            "each organization's reported service locations. 'Global' slices "
            "of the top-50 audited organizations are redistributed per their "
            "own published geographies (geo_audit.jsonl); unattributable "
            "shares stay Global. Muted buckets name a reporting granularity, "
            "not a place."
        ),
        "n_audited_orgs": n_audited,
        "total_usd": round(sum(buckets.values())),
        "regions": entries,
    }


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
    from .allocation import derive_shares

    orgs, _, _ = load_inputs()
    _, stats = derive_shares()
    out = {
        "disclosed_nonus": aggregate(orgs),
        "full_ledger": aggregate_full(orgs, stats["org_usd"], load_geo_audit()),
    }
    path = Path(__file__).resolve().parents[2] / "web" / "geo.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    fl = out["full_ledger"]
    print(f"wrote {path}: full ledger ${fl['total_usd']/1e9:.2f}B "
          f"in {len(fl['regions'])} buckets")


if __name__ == "__main__":
    main()

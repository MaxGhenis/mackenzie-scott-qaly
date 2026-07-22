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


def _org_region_dists(org, audit_shares):
    """(us_dist, abroad_dist, all_dist): region-bucket dollar distributions
    for one org's US-side, abroad-side, and overall geography."""
    locs = org.get("locations") or []
    if audit_shares:
        us = {"us_national": 1.0}
        abroad = {}
        for rk, sh in audit_shares.items():
            if rk == "north_america_us":
                continue
            abroad[_AUDIT_REGION[rk]] = abroad.get(_AUDIT_REGION[rk], 0.0) + sh
        tot = sum(abroad.values())
        abroad = {k: v / tot for k, v in abroad.items()} if tot else {"global": 1.0}
        us_w = audit_shares.get("north_america_us", 0.0)
        alls = {k: v * (1 - us_w) for k, v in abroad.items()}
        if us_w:
            alls["us_national"] = alls.get("us_national", 0.0) + us_w
        return us, abroad, alls
    if not locs:
        d = {"us_national": 1.0}
        return d, {"global": 1.0}, d
    us_locs = [l for l in locs if _is_us(l)]
    ab_locs = [l for l in locs if not _is_us(l)]
    def dist(ls):
        out: dict[str, float] = {}
        for l in ls:
            b = _bucket(l)
            out[b] = out.get(b, 0.0) + 1.0 / len(ls)
        return out
    us = dist(us_locs) if us_locs else {"us_national": 1.0}
    abroad = dist(ab_locs) if ab_locs else {"global": 1.0}
    return us, abroad, dist(locs)


def archetype_region_matrix(data_dir=None) -> dict:
    """Per-archetype regional dollar shares, mirroring the allocation
    pipeline's crediting rules exactly (substantive areas, PASSTHROUGH,
    SPLIT_HEALTH halves, audited geo routing). Within each archetype the
    model prices all regions identically, so these shares also decompose
    the archetype's QALYs — by construction, not as an empirical claim."""
    from .allocation import (GEO_SPLIT_TARGETS, GLOBAL_HEALTH, PASSTHROUGH,
                             SPLIT_HEALTH, SPLIT_HEALTH_TARGETS,
                             derive_shares, load_geo_overlay, nonus_fraction)

    orgs, leaves, mapping = load_inputs(data_dir)
    overlay = load_geo_overlay(data_dir)
    audit = load_geo_audit(data_dir)
    # geo_audit region shares are keyed by audit vocabulary; keep raw rows too
    import json as _json
    from .allocation import DATA_DIR
    d = Path(data_dir) if data_dir else DATA_DIR
    raw_audit = {}
    for line in (d / "geo_audit" / "geo_audit.jsonl").read_text().splitlines():
        row = _json.loads(line)
        raw_audit[row["name"]] = row.get("region_shares") or {}
    _, stats = derive_shares(data_dir)
    org_usd = stats["org_usd"]

    matrix: dict[str, Counter] = {}

    def add(target: str, dist: dict[str, float], amount: float) -> None:
        if amount <= 0:
            return
        m = matrix.setdefault(target, Counter())
        for region, w in dist.items():
            m[region] += amount * w

    for org, usd in zip(orgs, org_usd, strict=True):
        if not usd:
            continue
        labels = [leaves[c]["label"] for c in org.get("giftAreas") or []]
        subst = [la for la in labels if mapping[la] != PASSTHROUGH] or labels
        if not subst:
            continue
        weight = usd / len(subst)
        geo = overlay.get(org["name"], nonus_fraction(org.get("locations")))
        us_d, ab_d, all_d = _org_region_dists(org, raw_audit.get(org["name"]))
        for la in subst:
            target = mapping[la]
            if target == PASSTHROUGH:
                continue
            local = weight
            if target in GEO_SPLIT_TARGETS and geo > 0:
                add(GLOBAL_HEALTH, ab_d, weight * geo)
                local = weight * (1 - geo)
            if target == SPLIT_HEALTH:
                for half in SPLIT_HEALTH_TARGETS:
                    add(half, us_d if target in GEO_SPLIT_TARGETS else all_d, local / 2)
            elif target in GEO_SPLIT_TARGETS:
                add(target, us_d, local)
            else:
                add(target, all_d, local)

    labels = dict(_LABELS)
    labels.update({k: v for k, v in _US_BUCKETS})
    out_regions = sorted({r for m in matrix.values() for r in m})
    return {
        "note": (
            "Within each archetype the model prices all delivery locations "
            "identically (the health->global_health routing is the only "
            "geographic pricing), so these dollar shares decompose the "
            "archetype's QALYs by construction."
        ),
        "regions": [
            {"key": k, "label": labels[k], "unspecified": k in _UNSPECIFIED}
            for k in out_regions
        ],
        "matrix": {
            t: {k: round(v / sum(m.values()), 6) for k, v in m.items()}
            for t, m in matrix.items()
        },
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
        "archetype_region_matrix": archetype_region_matrix(),
    }
    path = Path(__file__).resolve().parents[2] / "web" / "geo.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    fl = out["full_ledger"]
    print(f"wrote {path}: full ledger ${fl['total_usd']/1e9:.2f}B "
          f"in {len(fl['regions'])} buckets")


if __name__ == "__main__":
    main()

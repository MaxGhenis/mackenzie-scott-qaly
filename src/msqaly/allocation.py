"""Derive the dollar-allocation centers from Yield Giving's gift database.

Scott's Yield Giving site publishes a gift-level database
(https://yieldgiving.com/gifts, snapshot in ``data/yieldgiving/``): every
organization with its org-reported focus areas, and a dollar amount for about
two-thirds of the disclosed dollars (``amount: 0`` marks undisclosed gifts).
This module turns that into the model's 14 ``allocation_share`` centers.

Disclosed gifts: each gift's dollars are split equally across its
organization's listed focus areas (tags are org-level, not per-gift); vehicle
tags (``PASSTHROUGH``: funds, regrantors) are dropped when the organization
lists substantive areas; generic health-delivery areas (``SPLIT_HEALTH``)
split 50/50 between ``health_coverage`` and ``health_chc``.

Undisclosed gifts are imputed rather than ignored. Scott's essays give each
year's *total* (``meta.giving_tranches`` in parameters.yaml), so the
undisclosed residual per year window is a known dollar amount; it is
distributed across that window's undisclosed gifts in proportion to each
recipient's **pre-gift IRS 990 total revenue** raised to an elasticity
calibrated on the disclosed pairs (log-log OLS of gift size on revenue).
Pre-gift means the latest ``tax_prd_yr`` strictly before the gift year — a
Scott gift inflates receipt-year revenue, so same-year revenue would be
endogenous. Recipients without a usable matched pre-gift history get the
window's median weight. Years 2019-2021 form one window because the
database attributes more disclosed 2021 dollars than the 2021 announcement
total — year attribution is noisy at the boundary.

Everything is deterministic from committed files
(``data/yieldgiving/{organisations.json, area_map.json,
leaf_to_archetype.yaml, propublica_revenue.jsonl}`` and
``data/parameters.yaml``); ``tests/test_allocation.py`` asserts that
``parameters.yaml`` carries exactly the derived shares.
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from pathlib import Path
from statistics import median

import yaml

from msqaly.recipients import (
    RecipientIndex,
    RecipientKey,
    recipient_key,
    validate_ein,
    validate_match_record,
    validate_revenue_history,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "yieldgiving"
PARAMS_PATH = ROOT / "data" / "parameters.yaml"
PASSTHROUGH = "PASSTHROUGH"
SPLIT_HEALTH = "SPLIT_HEALTH"
SPLIT_HEALTH_TARGETS = ("health_coverage", "health_chc")
# Health-relevant targets whose dollars split by delivery geography: the
# non-US-location share of each org routes to `global_health` (LMIC anchors)
# instead of the US-anchored archetype. A bed-net gift priced at Medicaid
# rates is off by orders of magnitude — the flaw a LinkedIn reader caught.
GEO_SPLIT_TARGETS = {SPLIT_HEALTH, "health_mental", "econ_food", "econ_cash"}
GLOBAL_HEALTH = "global_health"


def nonus_fraction(locations: list | None) -> float:
    """Share of an org's reported service locations outside the US."""
    if not locations:
        return 0.0
    nonus = [
        loc for loc in locations
        if not loc.startswith("us") and loc != "north_america"
    ]
    return len(nonus) / len(locations)
# 2019-2021 pooled: the DB attributes more disclosed 2021 dollars than the
# 2021 announcement total, so the year boundary inside the pool is unreliable.
WINDOWS = ((2019, 2021), (2022, 2022), (2023, 2023), (2024, 2024), (2025, 2025))


def load_inputs(data_dir: str | Path | None = None) -> tuple[list, dict, dict]:
    """Return (organisations, leaf code -> {label, group}, label -> archetype)."""
    d = Path(data_dir) if data_dir else DATA_DIR
    orgs = json.loads((d / "organisations.json").read_text())
    leaves = json.loads((d / "area_map.json").read_text())["leaves"]
    mapping = yaml.safe_load((d / "leaf_to_archetype.yaml").read_text())
    return orgs, leaves, mapping


def load_matches(data_dir: str | Path | None = None) -> dict[RecipientKey, dict]:
    """Effective matches indexed by recipient name and website.

    Legacy rows without links are accepted only for unique recipient names.
    Each raw and overlay layer must contain at most one row per identity.
    """
    d = Path(data_dir) if data_dir else DATA_DIR
    index = RecipientIndex(json.loads((d / "organisations.json").read_text()))

    def read_rows(path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    raw = index.records(read_rows(d / "propublica_revenue.jsonl"), label="raw match")
    out = dict(raw)
    for key, rec in out.items():
        validate_match_record(rec, f"raw match {key!r}")
    if out.keys() != index.by_key.keys():
        raise ValueError("raw matches must cover every recipient; finish the resumable fetch first")
    audit = d / "match_audit.jsonl"
    if audit.exists():
        for key, rec in index.records(read_rows(audit), label="audit overlay").items():
            if key not in out:
                raise ValueError(f"audit recipient missing from raw matches: {key!r}")
            # The overlay owns the effective filer snapshot. Even when its EIN
            # equals the raw candidate's, the filing retrieval may be different.
            active = {"name": key[0], "link": index.by_key[key].get("link"), **rec}
            if rec["action"] == "drop":
                out[key] = {
                    **active, "ein": None, "revenue_by_year": {},
                    "source_url": None, "legal_name": None, "retrieved_at": None,
                }
            elif rec["action"] == "replace":
                validate_ein(rec.get("ein"), f"replacement {key!r}")
                validate_revenue_history(rec.get("revenue_by_year"), f"replacement {key!r}")
                out[key] = {
                    "source_url": None, "legal_name": None, "retrieved_at": None,
                    **active,
                }
            else:
                raise ValueError(f"unknown audit action for {key!r}: {rec['action']!r}")
    for key, rec in out.items():
        rec["raw_candidate"] = {
            field: raw[key].get(field)
            for field in ("ein", "match", "score", "source_url", "retrieved_at")
        }
    return out


def load_revenue(data_dir: str | Path | None = None) -> dict[RecipientKey, dict[int, float]]:
    """Recipient identity -> {990 tax year -> total revenue} after audit overlay."""
    return {
        key: validate_revenue_history(rec["revenue_by_year"], f"match {key!r}")
        for key, rec in load_matches(data_dir).items()
        if rec.get("ein")
    }


def pre_gift_revenue_year(rev_by_year: dict[int, float] | None, gift_year: int) -> int | None:
    """Tax year selected for the latest available strictly pre-gift revenue."""
    if not rev_by_year:
        return None
    years = [y for y in rev_by_year if y < gift_year]
    return max(years) if years else None


def pre_gift_revenue(rev_by_year: dict[int, float] | None, gift_year: int) -> float | None:
    """Latest 990 revenue strictly before the gift year (avoids the gift
    itself inflating receipt-year revenue)."""
    year = pre_gift_revenue_year(rev_by_year, gift_year)
    return rev_by_year[year] if year is not None else None


def impute_window(
    revenues: list[float | None], beta: float, residual: float
) -> tuple[list[float], list[float], int]:
    """Assign a window's residual using revenue weights and the median fallback.

    Return assigned dollars, effective weights, and the fallback gift count.
    Allocation and diagnostics share this calculation so their ledgers agree.
    """
    if not revenues:
        return [], [], 0
    weights = [r**beta if r else None for r in revenues]
    known = [w for w in weights if w is not None]
    fallback = median(known) if known else 1.0
    n_fallback = sum(1 for w in weights if w is None)
    weights = [w if w is not None else fallback for w in weights]
    total_w = sum(weights)
    return [residual * w / total_w for w in weights], weights, n_fallback


def year_window(year: int) -> tuple[int, int]:
    for lo, hi in WINDOWS:
        if lo <= year <= hi:
            return (lo, hi)
    raise ValueError(f"gift year {year} outside known windows")


def calibrate_elasticity(orgs: list, revenue: dict) -> tuple[float, float, int]:
    """OLS of log10(gift amount) on log10(pre-gift revenue) over disclosed
    pairs. Returns (elasticity beta, R^2, n)."""
    # The exported fit must reproduce even at decimal rounding boundaries.
    # Compute the same simple regression in fixed-precision decimal arithmetic,
    # independent of the host libm, BLAS and caller's decimal context.
    pairs = []
    with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
        for org in orgs:
            history = revenue.get(recipient_key(org))
            for gift in org.get("gifts") or []:
                amount = gift.get("amount") or 0
                if amount <= 0:
                    continue
                prior = pre_gift_revenue(history, int(gift["year"]))
                if prior:
                    pairs.append((Decimal(str(prior)).log10(), Decimal(str(amount)).log10()))

        if len(pairs) < 2:
            raise ValueError("calibration requires at least two gift–revenue pairs")
        pairs.sort()
        n = len(pairs)
        mean_x = sum(x for x, _ in pairs) / n
        mean_y = sum(y for _, y in pairs) / n
        xx = sum((x - mean_x) ** 2 for x, _ in pairs)
        yy = sum((y - mean_y) ** 2 for _, y in pairs)
        if not xx or not yy:
            raise ValueError("calibration requires variation in both revenue and gift size")
        xy = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
        return float(xy / xx), float(xy**2 / (xx * yy)), n


def load_geo_overlay(data_dir: str | Path | None = None) -> dict[str, float]:
    """Audited non-US fractions for 'global'-listed orgs (geo_audit.jsonl):
    org name -> (1 - audited US share). Produced by the terra research sweep;
    each row carries source_url + confidence. Opt-in via derive_shares."""
    d = Path(data_dir) if data_dir else DATA_DIR
    path = d / "geo_audit" / "geo_audit.jsonl"
    out: dict[str, float] = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        out[row["name"]] = max(0.0, min(1.0, 1.0 - float(row["us_share"])))
    return out


def derive_shares(
    data_dir: str | Path | None = None,
    params_path: str | Path | None = None,
    impute: bool = True,
    geo_overlay: bool = True,
) -> tuple[dict[str, float], dict]:
    """Compute archetype -> share (3-decimal, sums to exactly 1.0) and stats.

    ``geo_overlay=True`` (default since v1.1) applies the cross-checked
    audit of 'global'-listed organizations' non-US fractions; pass False
    to reproduce the v1.0 (July 13) allocation."""
    orgs, leaves, mapping = load_inputs(data_dir)
    overlay = load_geo_overlay(data_dir) if geo_overlay else {}

    unmapped = sorted({leaf["label"] for leaf in leaves.values()} - set(mapping))
    if unmapped:
        raise ValueError(f"focus areas missing from leaf_to_archetype.yaml: {unmapped}")

    def substantive_areas(org: dict) -> list[str]:
        labels = [leaves[code]["label"] for code in org.get("giftAreas") or []]
        return [la for la in labels if mapping[la] != PASSTHROUGH] or labels

    def credit(usd: dict, org: dict, amount: float) -> None:
        areas = substantive_areas(org)
        weight = amount / len(areas)
        geo = overlay.get(org["name"], nonus_fraction(org.get("locations")))
        for label in areas:
            target = mapping[label]
            if target == PASSTHROUGH:
                continue  # vehicle-only org: spread via normalization
            local = weight
            if target in GEO_SPLIT_TARGETS and geo > 0:
                usd[GLOBAL_HEALTH] += weight * geo
                local = weight * (1 - geo)
            if target == SPLIT_HEALTH:
                for half in SPLIT_HEALTH_TARGETS:
                    usd[half] += local / 2
            else:
                usd[target] += local

    usd: dict[str, float] = defaultdict(float)
    disclosed_usd = 0.0
    n_gifts = n_disclosed = 0
    disclosed_by_window: dict[tuple, float] = defaultdict(float)
    org_usd = [0.0] * len(orgs)  # dollars credited per org (index-aligned)
    undisclosed: list[tuple[int, dict, int]] = []  # (org index, org, gift year)
    for i, org in enumerate(orgs):
        for gift in org.get("gifts") or []:
            n_gifts += 1
            year = int(gift["year"])
            amount = gift.get("amount") or 0
            if amount > 0:
                n_disclosed += 1
                disclosed_usd += amount
                disclosed_by_window[year_window(year)] += amount
                org_usd[i] += amount
                credit(usd, org, amount)
            else:
                undisclosed.append((i, org, year))

    stats: dict = {
        "n_orgs": len(orgs),
        "n_gifts": n_gifts,
        "n_disclosed": n_disclosed,
        "disclosed_usd": disclosed_usd,
    }

    if impute:
        revenue = load_revenue(data_dir)
        beta, r2, n_cal = calibrate_elasticity(orgs, revenue)
        params = yaml.safe_load(Path(params_path or PARAMS_PATH).read_text())
        window_total: dict[tuple, float] = defaultdict(float)
        for tranche in params["meta"]["giving_tranches"]:
            window_total[year_window(int(tranche["year"]))] += float(tranche["nominal_usd"])

        by_window: dict[tuple, list] = defaultdict(list)
        n_fallback = 0
        for i, org, year in undisclosed:
            r = pre_gift_revenue(revenue.get(recipient_key(org)), year)
            by_window[year_window(year)].append((i, org, r))
        imputed_usd = 0.0
        imputed_by_window = {}
        for window, rows in by_window.items():
            residual = max(window_total[window] - disclosed_by_window[window], 0.0)
            amounts, _, window_fallback = impute_window([r for _, _, r in rows], beta, residual)
            n_fallback += window_fallback
            imputed_by_window[f"{window[0]}-{window[1]}"] = residual
            for (i, org, _), amount in zip(rows, amounts, strict=True):
                imputed_usd += amount
                org_usd[i] += amount
                credit(usd, org, amount)
        stats.update(
            elasticity=beta,
            elasticity_r2=r2,
            n_calibration=n_cal,
            n_undisclosed=len(undisclosed),
            n_revenue_fallback=n_fallback,
            imputed_usd=imputed_usd,
            imputed_by_window=imputed_by_window,
        )

    total = sum(usd.values())
    raw = {k: v / total for k, v in usd.items()}

    # Largest-remainder rounding to 3 decimals -> sums to exactly 1.000.
    floors = {k: int(v * 1000) for k, v in raw.items()}
    remainder = 1000 - sum(floors.values())
    order = sorted(raw, key=lambda k: raw[k] * 1000 - floors[k], reverse=True)
    for k in order[:remainder]:
        floors[k] += 1
    shares = {k: floors[k] / 1000 for k in sorted(floors, key=floors.get, reverse=True)}
    stats["raw_shares"] = raw
    stats["org_usd"] = org_usd
    return shares, stats


def main() -> None:
    base, _ = derive_shares(impute=False)
    shares, stats = derive_shares()
    print(
        f"{stats['n_orgs']} orgs, {stats['n_disclosed']}/{stats['n_gifts']} gifts "
        f"disclosed (${stats['disclosed_usd'] / 1e9:.2f}B) + "
        f"${stats['imputed_usd'] / 1e9:.2f}B imputed over {stats['n_undisclosed']} gifts"
    )
    print(
        f"gift~revenue elasticity {stats['elasticity']:.3f} "
        f"(R^2 {stats['elasticity_r2']:.2f}, n={stats['n_calibration']}); "
        f"{stats['n_revenue_fallback']} gifts on median-weight fallback"
    )
    print(f"{'archetype':30s} {'imputed':>8s} {'disclosed-only':>15s}")
    for key, share in shares.items():
        print(f"  {key:30s} {share:8.3f} {base.get(key, 0):15.3f}")
    print(f"  {'sum':30s} {sum(shares.values()):8.3f} {sum(base.values()):15.3f}")


if __name__ == "__main__":
    main()

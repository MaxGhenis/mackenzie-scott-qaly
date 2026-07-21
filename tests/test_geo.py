"""Geo aggregation: conservation, US test parity, and export sync."""

import json
from pathlib import Path

from msqaly.allocation import load_inputs, nonus_fraction
from msqaly.geo import aggregate

ROOT = Path(__file__).resolve().parents[1]


def test_dollars_are_conserved_and_match_nonus_fraction():
    orgs, _, _ = load_inputs()
    out = aggregate(orgs)
    total = out["us_usd"] + out["nonus_usd"]
    # Same weighting as nonus_fraction: sum of usd * nonus share.
    expect_nonus = sum(
        sum(g.get("amount") or 0 for g in o.get("gifts", []))
        * nonus_fraction(o.get("locations"))
        for o in orgs
        if o.get("locations")
    )
    disclosed_with_locs = sum(
        sum(g.get("amount") or 0 for g in o.get("gifts", []))
        for o in orgs
        if o.get("locations")
    )
    assert abs(total - disclosed_with_locs) < 1000
    assert abs(out["nonus_usd"] - expect_nonus) < 1000
    assert abs(sum(r["usd"] for r in out["regions"]) - out["nonus_usd"]) < 1000


def test_unmapped_tail_is_small():
    orgs, _, _ = load_inputs()
    out = aggregate(orgs)
    other = next((r["usd"] for r in out["regions"] if r["key"] == "other"), 0)
    assert other < 0.02 * out["nonus_usd"], "grow _CODE_REGION instead"


def test_export_in_sync():
    orgs, _, _ = load_inputs()
    disk = json.loads((ROOT / "web" / "geo.json").read_text())
    assert disk == aggregate(orgs)

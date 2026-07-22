"""Geo aggregation: conservation, US test parity, and export sync."""

import json
from pathlib import Path

from msqaly.allocation import load_inputs, nonus_fraction
from msqaly.geo import aggregate, aggregate_full, load_geo_audit

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


def test_full_ledger_conserves_all_dollars():
    from msqaly.allocation import derive_shares

    orgs, _, _ = load_inputs()
    _, stats = derive_shares()
    out = aggregate_full(orgs, stats["org_usd"], load_geo_audit())
    assert abs(out["total_usd"] - sum(stats["org_usd"])) < 1000
    assert abs(sum(r["usd"] for r in out["regions"]) - out["total_usd"]) < 1000
    # Every bucket is labeled and flagged
    assert all("label" in r and "unspecified" in r for r in out["regions"])


def test_export_in_sync():
    from msqaly.allocation import derive_shares

    orgs, _, _ = load_inputs()
    _, stats = derive_shares()
    disk = json.loads((ROOT / "web" / "geo.json").read_text())
    assert disk == {
        "disclosed_nonus": aggregate(orgs),
        "full_ledger": aggregate_full(orgs, stats["org_usd"], load_geo_audit()),
    }


def test_geo_overlay_loads_and_shares_still_sum():
    from msqaly.allocation import derive_shares, load_geo_overlay

    overlay = load_geo_overlay()
    assert len(overlay) == 50
    assert all(0.0 <= v <= 1.0 for v in overlay.values())
    shares, _ = derive_shares(geo_overlay=True)
    assert abs(sum(shares.values()) - 1.0) < 1e-9


def test_version_exports_in_sync():
    from msqaly.exportversions import build, build_v10

    for name, builder in (("allocation_v11.json", build),
                          ("allocation_v10.json", build_v10)):
        disk = json.loads((ROOT / "web" / name).read_text())
        assert disk == builder()
        assert abs(sum(disk["allocation_share"].values()) - 1.0) < 1e-9

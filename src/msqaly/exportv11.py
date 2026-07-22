"""Export the v1.1 (geo-audited) allocation vector for the site's
version toggle.

v1.0 = parameters.yaml allocation_share values (published July 13 model,
tag v2026.07.20). v1.1 applies the cross-checked geography audit
(``derive_shares(geo_overlay=True)``): the 50 largest 'global'-listed
organizations get their audited non-US fractions instead of the blanket
geo=1. Same 3-decimal largest-remainder rounding as the base pipeline.

Run ``python -m msqaly.exportv11`` to (re)write ``web/allocation_v11.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .allocation import derive_shares


def build() -> dict:
    shares, stats = derive_shares(geo_overlay=True)
    return {
        "version": "v1.1",
        "label": "v1.1 — geo-audited allocation (July 22, 2026)",
        "description": (
            "Allocation centers recomputed with audited non-US fractions "
            "for the 50 largest 'global'-listed organizations (87% of that "
            "bucket's dollars), verified by two independent model reviews "
            "with per-organization sources in "
            "data/yieldgiving/geo_audit/geo_audit.jsonl."
        ),
        "allocation_share": shares,
        "abroad_share_raw": round(stats["raw_shares"]["global_health"], 6),
    }


def main() -> None:
    out = build()
    path = Path(__file__).resolve().parents[2] / "web" / "allocation_v11.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {path}: global_health {out['allocation_share']['global_health']}")


if __name__ == "__main__":
    main()

"""Export current allocations and preserve the published historical vectors.

The v1.0 and v1.1 snapshots predate the Form 990 identity corrections. They
must not change when revenue inputs change. v1.2 derives from current data.
"""

from __future__ import annotations

import json
from pathlib import Path

from .allocation import derive_shares

HISTORY = Path(__file__).resolve().parents[2] / "data" / "yieldgiving" / "allocation_history"


def build_v10() -> dict:
    """Return the immutable July 13 allocation, copied before 990 corrections."""
    return json.loads((HISTORY / "v10.json").read_text())


def build_v11() -> dict:
    """Return the immutable July 22 allocation, copied before 990 corrections."""
    return json.loads((HISTORY / "v11.json").read_text())


def build() -> dict:
    shares, stats = derive_shares(geo_overlay=True)
    return {
        "version": "v1.2",
        "label": "v1.2 — corrected Form 990 matches (November 16, 2026)",
        "description": (
            "Allocation centers use source-linked Form 990 identity corrections, "
            "distinct keys for recipients with the same name, and the existing "
            "geography audit. See data/yieldgiving/match_audit.jsonl."
        ),
        "allocation_share": shares,
        "abroad_share_raw": round(stats["raw_shares"]["global_health"], 6),
        "calibration": {
            # NumPy/BLAS implementations differ at machine precision. Keep
            # exported metadata stable without rounding the fitted model input.
            "elasticity": round(stats["elasticity"], 12),
            "r_squared": round(stats["elasticity_r2"], 12),
            "n_pairs": stats["n_calibration"],
            "n_revenue_fallback": stats["n_revenue_fallback"],
            "n_undisclosed": stats["n_undisclosed"],
        },
    }


def main() -> None:
    web = Path(__file__).resolve().parents[2] / "web"
    for name, out in (("allocation_v10.json", build_v10()),
                      ("allocation_v11.json", build_v11()),
                      ("allocation_v12.json", build())):
        (web / name).write_text(json.dumps(out, indent=1) + "\n")
        print(f"wrote {name}: global_health {out['allocation_share']['global_health']}")


if __name__ == "__main__":
    main()

"""Derive the dollar-allocation centers from Yield Giving's gift database.

Scott's Yield Giving site publishes a gift-level database
(https://yieldgiving.com/gifts, snapshot in ``data/yieldgiving/``): every
organization with its org-reported focus areas, and a dollar amount for about
two-thirds of the disclosed dollars (``amount: 0`` marks undisclosed gifts).
This module turns that into the model's 13 ``allocation_share`` centers:

1. each disclosed gift's dollars are split equally across its organization's
   listed focus areas (tags are org-level, not per-gift);
2. vehicle tags (``PASSTHROUGH``: funds, regrantors) are dropped when the
   organization lists substantive areas — orgs tagged only as vehicles end up
   spread proportionally via the final normalization;
3. generic health-delivery areas (``SPLIT_HEALTH``) split 50/50 between
   ``health_coverage`` and ``health_chc``, the model's two US health-access
   archetypes;
4. archetype sums are normalized and rounded to 3 decimals by largest
   remainder, so the printed shares sum to exactly 1.0.

``tests/test_allocation.py`` asserts that ``data/parameters.yaml`` carries
exactly these shares, so the YAML cannot silently drift from the data.
Undisclosed gifts (one-third of dollars) are assumed to allocate like
disclosed ones; the Dirichlet concentration in ``parameters.yaml`` stays
author-elicited partly for that reason.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "yieldgiving"
PASSTHROUGH = "PASSTHROUGH"
SPLIT_HEALTH = "SPLIT_HEALTH"
SPLIT_HEALTH_TARGETS = ("health_coverage", "health_chc")


def load_inputs(data_dir: str | Path | None = None) -> tuple[list, dict, dict]:
    """Return (organisations, leaf code -> {label, group}, label -> archetype)."""
    d = Path(data_dir) if data_dir else DATA_DIR
    orgs = json.loads((d / "organisations.json").read_text())
    leaves = json.loads((d / "area_map.json").read_text())["leaves"]
    mapping = yaml.safe_load((d / "leaf_to_archetype.yaml").read_text())
    return orgs, leaves, mapping


def derive_shares(data_dir: str | Path | None = None) -> tuple[dict[str, float], dict]:
    """Compute archetype -> share (3-decimal, sums to exactly 1.0) and stats."""
    orgs, leaves, mapping = load_inputs(data_dir)

    unmapped = sorted(
        {leaf["label"] for leaf in leaves.values()} - set(mapping)
    )
    if unmapped:
        raise ValueError(f"focus areas missing from leaf_to_archetype.yaml: {unmapped}")

    usd = defaultdict(float)
    disclosed_usd = 0.0
    n_gifts = n_disclosed = 0
    for org in orgs:
        labels = [leaves[code]["label"] for code in org.get("giftAreas") or []]
        substantive = [la for la in labels if mapping[la] != PASSTHROUGH] or labels
        for gift in org.get("gifts") or []:
            n_gifts += 1
            amount = gift.get("amount") or 0
            if amount <= 0:
                continue
            n_disclosed += 1
            disclosed_usd += amount
            weight = amount / len(substantive)
            for label in substantive:
                target = mapping[label]
                if target == PASSTHROUGH:
                    continue  # vehicle-only org: spread via normalization
                if target == SPLIT_HEALTH:
                    for half in SPLIT_HEALTH_TARGETS:
                        usd[half] += weight / 2
                else:
                    usd[target] += weight

    total = sum(usd.values())
    raw = {k: v / total for k, v in usd.items()}

    # Largest-remainder rounding to 3 decimals -> sums to exactly 1.000.
    floors = {k: int(v * 1000) for k, v in raw.items()}
    remainder = 1000 - sum(floors.values())
    order = sorted(raw, key=lambda k: raw[k] * 1000 - floors[k], reverse=True)
    for k in order[:remainder]:
        floors[k] += 1
    shares = {k: floors[k] / 1000 for k in sorted(floors, key=floors.get, reverse=True)}

    stats = {
        "n_orgs": len(orgs),
        "n_gifts": n_gifts,
        "n_disclosed": n_disclosed,
        "disclosed_usd": disclosed_usd,
        "raw_shares": raw,
    }
    return shares, stats


def main() -> None:
    shares, stats = derive_shares()
    print(
        f"{stats['n_orgs']} orgs, {stats['n_disclosed']}/{stats['n_gifts']} gifts "
        f"disclosed, ${stats['disclosed_usd'] / 1e9:.2f}B allocated"
    )
    for key, share in shares.items():
        print(f"  {key:30s} {share:.3f}")
    print(f"  {'sum':30s} {sum(shares.values()):.3f}")


if __name__ == "__main__":
    main()

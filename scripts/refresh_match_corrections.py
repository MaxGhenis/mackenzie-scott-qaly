"""Refresh source-linked Form 990 match corrections without rerunning name matching.

By default, fetch and preview the corrected histories without changing files.
Use ``--write`` to replace those histories only after every request succeeds.
Recipient identity citations, original EINs and other audit metadata are retained.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

DATA = Path(__file__).resolve().parents[1] / "data" / "yieldgiving" / "match_audit.jsonl"
API = "https://projects.propublica.org/nonprofits/api/v2/organizations"
MAX_TAX_YEAR = 2024


def extract_revenue(detail: dict, expected_ein: int, max_tax_year: int) -> dict[str, int]:
    """Validate filer identity and extract positive revenue through the audit cutoff."""
    actual_ein = (detail.get("organization") or {}).get("ein")
    if actual_ein != expected_ein:
        raise ValueError(f"expected EIN {expected_ein}, received {actual_ein}")
    if max_tax_year > MAX_TAX_YEAR:
        raise ValueError(f"tax-year cutoff must be at most {MAX_TAX_YEAR}")
    revenue: dict[str, int] = {}
    for filing in detail.get("filings_with_data") or []:
        year, value = filing.get("tax_prd_yr"), filing.get("totrevenue")
        if year and year <= max_tax_year and value and value > 0:
            # Match the historical fetch's duplicate/amended-row convention.
            revenue[str(year)] = max(value, revenue.get(str(year), 0))
    if not revenue:
        raise ValueError(f"no positive revenue history through {max_tax_year} for {expected_ein}")
    return dict(sorted(revenue.items(), reverse=True))


def refresh(rows: list[dict]) -> list[dict]:
    """Return refreshed rows; any failed request aborts before the caller writes."""
    refreshed = []
    for row in rows:
        updated = dict(row)
        if (
            row.get("action") == "replace"
            and row.get("identity_source_url")
            and row.get("source_url")
            and "old_ein" in row
        ):
            ein = row["ein"]
            expected_url = f"{API}/{ein}.json"
            if row["source_url"] != expected_url:
                raise ValueError(f"unexpected revenue source for {row['name']}")
            request = Request(expected_url, headers={"User-Agent": "mackenzie-scott-qaly audit"})
            with urlopen(request, timeout=30) as response:
                detail = json.load(response)
            cutoff = row.get("revenue_tax_year_max", MAX_TAX_YEAR)
            updated["revenue_by_year"] = extract_revenue(detail, ein, cutoff)
            updated["legal_name"] = detail["organization"]["name"]
            updated["retrieved_at"] = datetime.now(UTC).isoformat()
            time.sleep(0.3)
        refreshed.append(updated)
    return refreshed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write only after all fetches succeed")
    args = parser.parse_args()
    original = DATA.read_text()
    rows = [json.loads(line) for line in original.splitlines() if line.strip()]
    updated = refresh(rows)
    changes = [
        {
            "name": after["name"],
            "link": after.get("link"),
            "ein": after.get("ein"),
            "revenue_changed": before.get("revenue_by_year") != after.get("revenue_by_year"),
        }
        for before, after in zip(rows, updated, strict=True)
        if before != after
    ]
    if args.write:
        if DATA.read_text() != original:
            raise RuntimeError("audit file changed during refresh; refusing to overwrite it")
        temporary = DATA.with_suffix(".jsonl.tmp")
        temporary.write_text("".join(json.dumps(row) + "\n" for row in updated))
        temporary.replace(DATA)
    print(json.dumps({"written": args.write, "refreshed": changes}, indent=2))


if __name__ == "__main__":
    main()

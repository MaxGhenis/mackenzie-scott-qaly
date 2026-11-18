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
from stat import S_IMODE
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen

from fetch_propublica import output_lock

from msqaly.recipients import (
    CORRECTION_MAX_TAX_YEAR,
    extract_filing_revenue,
    validate_ein,
    validate_match_record,
    validate_tax_year,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "yieldgiving" / "match_audit.jsonl"
API = "https://projects.propublica.org/nonprofits/api/v2/organizations"


def extract_revenue(
    detail: dict, expected_ein: int, max_tax_year: int, *, allow_empty: bool = False
) -> dict[str, int | float]:
    """Validate filer identity and extract positive revenue through the audit cutoff."""
    cutoff = validate_tax_year(max_tax_year, "tax-year cutoff")
    if cutoff > CORRECTION_MAX_TAX_YEAR:
        raise ValueError(f"tax-year cutoff must be at most {CORRECTION_MAX_TAX_YEAR}")
    revenue = extract_filing_revenue(detail, expected_ein, max_tax_year=cutoff)
    if not revenue and not allow_empty:
        raise ValueError(f"no positive revenue history through {cutoff} for {expected_ein}")
    return dict(sorted(revenue.items(), key=lambda entry: int(entry[0]), reverse=True))


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
            label = f"correction for {row['name']!r}"
            validate_match_record(row, label)
            validate_ein(row["old_ein"], f"{label} previous EIN", allow_none=True)
            ein = validate_ein(row.get("ein"), f"{label} EIN")
            expected_url = f"{API}/{ein}.json"
            if row["source_url"] != expected_url:
                raise ValueError(f"unexpected revenue source for {row['name']}")
            request = Request(expected_url, headers={"User-Agent": "mackenzie-scott-qaly audit"})
            with urlopen(request, timeout=30) as response:
                detail = json.load(response)
            cutoff = row.get("revenue_tax_year_max", CORRECTION_MAX_TAX_YEAR)
            updated["revenue_by_year"] = extract_revenue(
                detail, ein, cutoff, allow_empty=not row["revenue_by_year"]
            )
            legal_name = detail["organization"].get("name")
            if not isinstance(legal_name, str) or not legal_name.strip():
                raise ValueError(f"organization endpoint lacks a legal name for EIN {ein}")
            updated["legal_name"] = legal_name
            updated["retrieved_at"] = datetime.now(UTC).isoformat()
            time.sleep(0.3)
        refreshed.append(updated)
    return refreshed


def write_overlay(path: Path, original: bytes, rows: list[dict]) -> None:
    """Replace the overlay only after serializing and checking for intervening edits."""
    payload = "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows)
    temporary = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        with output_lock(path):
            if path.read_bytes() != original:
                raise RuntimeError("audit file changed during refresh; refusing to overwrite it")
            temporary.chmod(S_IMODE(path.stat().st_mode))
            temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write only after all fetches succeed")
    args = parser.parse_args()
    original = DATA.read_bytes()
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
        write_overlay(DATA, original, updated)
    print(json.dumps({"written": args.write, "refreshed": changes}, indent=2))


if __name__ == "__main__":
    main()

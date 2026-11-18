"""Resolve recipient identity without conflating organizations that share a name."""

from __future__ import annotations

from collections import defaultdict
from math import isfinite
from urllib.parse import urlsplit

RecipientKey = tuple[str, str]
CORRECTION_MAX_TAX_YEAR = 2024


def validate_ein(value, path: str = "EIN", *, allow_none: bool = False) -> int | None:
    """EINs are positive integers with at most nine digits, never booleans."""
    if value is None and allow_none:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value < 10**9:
        raise ValueError(f"{path}: expected a positive EIN with at most nine digits")
    return value


def validate_tax_year(value, path: str = "tax year") -> int:
    """Return a positive calendar year without silently rounding a fraction."""
    if isinstance(value, str) and value.isascii() and value.isdigit():
        number = int(value)
        if str(number) != value:
            raise ValueError(f"{path}: noncanonical tax year {value!r}")
    elif isinstance(value, int) and not isinstance(value, bool):
        number = value
    else:
        raise ValueError(f"{path}: expected a positive integer tax year")
    if not 0 < number <= 9999:
        raise ValueError(f"{path}: expected a positive calendar year")
    return number


def finite_revenue(value, path: str) -> int | float:
    """Validate an API revenue number before selecting positive histories."""
    try:
        valid = isinstance(value, int | float) and not isinstance(value, bool) and isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{path}: revenue must be a finite number, not a boolean")
    return value


def validate_revenue_history(history, path: str) -> dict[int, float]:
    """Validate stored positive-revenue histories and normalize calendar-year keys."""
    if not isinstance(history, dict):
        raise ValueError(f"{path}: expected a revenue-by-year object")
    result = {}
    for year, value in history.items():
        canonical_year = validate_tax_year(year, f"{path}.{year}")
        if canonical_year in result:
            raise ValueError(f"{path}: duplicate normalized tax year {canonical_year}")
        number = finite_revenue(value, f"{path}.{year}")
        if number <= 0:
            raise ValueError(f"{path}.{year}: stored revenue must be positive")
        result[canonical_year] = float(number)
    return result


def validate_match_record(record: dict, path: str) -> None:
    """The raw-fetch schema also applies to effective replacement records."""
    ein = validate_ein(record.get("ein"), path, allow_none=True)
    history = validate_revenue_history(record.get("revenue_by_year"), path)
    if ein is None and history:
        raise ValueError(f"{path}: unmatched recipient must have empty revenue")
    if record.get("score") is not None:
        score = finite_revenue(record["score"], f"{path}.score")
        if not 0 <= score <= 1:
            raise ValueError(f"{path}.score: similarity must be in [0, 1]")


def extract_filing_revenue(
    detail: dict, expected_ein: int, *, max_tax_year: int | None = None
) -> dict[str, int | float]:
    """Read positive annual revenues from the requested filer's API response."""
    validate_ein(expected_ein, "requested EIN")
    if max_tax_year is not None:
        max_tax_year = validate_tax_year(max_tax_year, "tax-year cutoff")
    if not isinstance(detail, dict) or not isinstance(detail.get("organization"), dict):
        raise ValueError(f"organization endpoint lacks a profile for EIN {expected_ein}")
    actual_ein = validate_ein(detail["organization"].get("ein"), "API organization EIN")
    if actual_ein != expected_ein:
        raise ValueError(f"expected EIN {expected_ein}, received {actual_ein}")
    filings = detail.get("filings_with_data")
    if not isinstance(filings, list):
        raise ValueError(f"organization endpoint lacks filing history for EIN {expected_ein}")
    revenue: dict[str, int | float] = {}
    for filing in filings:
        if not isinstance(filing, dict):
            raise ValueError(f"expected filing object for EIN {expected_ein}")
        year, value = filing.get("tax_prd_yr"), filing.get("totrevenue")
        if year is not None:
            year = validate_tax_year(year, "API filing tax year")
        if value is not None:
            value = finite_revenue(value, "API filing revenue")
        if year is None or value is None or value <= 0:
            continue
        if max_tax_year is None or year <= max_tax_year:
            # Multiple filings for one year use the largest positive total revenue.
            revenue[str(year)] = max(value, revenue.get(str(year), 0))
    return revenue


def recipient_key(recipient: dict) -> RecipientKey:
    """Stable (public name, website) identity from the verbatim gift snapshot.

    Scheme, a leading www., and a final slash do not distinguish websites.
    Paths and queries remain significant. A snapshot recipient without a
    website keeps an empty website component; the index still rejects collisions.
    """
    name, link = recipient.get("name"), recipient.get("link")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("recipient needs a nonempty name")
    if link in (None, ""):
        return name.strip(), ""
    if not isinstance(link, str):
        raise ValueError(f"recipient {name!r} needs a string link")
    if not link.strip():
        return name.strip(), ""
    url = urlsplit(link.strip() if "://" in link else "https://" + link.strip())
    host = url.netloc.lower().removeprefix("www.")
    if not host:
        raise ValueError(f"invalid recipient link: {link!r}")
    website = host + url.path.rstrip("/")
    if url.query:
        website += "?" + url.query
    return name.strip(), website


class RecipientIndex:
    """Resolve legacy unique-name rows and require a website for namesakes."""

    def __init__(self, organizations: list[dict]):
        self.by_key: dict[RecipientKey, dict] = {}
        self.by_name: dict[str, list[RecipientKey]] = defaultdict(list)
        for org in organizations:
            key = recipient_key(org)
            if key in self.by_key:
                raise ValueError(f"duplicate recipient identity: {key!r}")
            self.by_key[key] = org
            self.by_name[key[0]].append(key)

    def resolve(self, record: dict) -> RecipientKey:
        """Reject unknown, ambiguous, or mismatched identities."""
        if "link" in record:
            key = recipient_key(record)
            if key not in self.by_key:
                raise ValueError(f"unknown recipient identity: {key!r}")
            return key
        name = record.get("name")
        candidates = self.by_name.get(name, [])
        if not candidates:
            raise ValueError(f"unknown recipient name: {name!r}")
        if len(candidates) != 1:
            raise ValueError(f"ambiguous recipient name {name!r}; include link")
        return candidates[0]

    def records(self, rows: list[dict], *, label: str) -> dict[RecipientKey, dict]:
        """Index one layer of records; duplicate identities are always errors."""
        result = {}
        for row in rows:
            key = self.resolve(row)
            if key in result:
                raise ValueError(f"duplicate {label} recipient identity: {key!r}")
            result[key] = row
        return result

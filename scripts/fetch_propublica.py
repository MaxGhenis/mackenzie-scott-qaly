"""Fetch IRS 990 total-revenue histories for every Yield Giving recipient.

For each organization in data/yieldgiving/organisations.json, query
ProPublica's Nonprofit Explorer API (https://projects.propublica.org/nonprofits/api/):
match the name to an EIN via the search endpoint, then pull every filing's
``tax_prd_yr`` and ``totrevenue``. Results are appended to
data/yieldgiving/propublica_revenue.jsonl (one JSON object per org) so the
run is resumable; rerunning skips orgs already fetched.

Matching: names are normalized (lowercase, "&"->"and", punctuation stripped,
leading "the" dropped) and scored with difflib against the top search hits; a
match needs a ratio >= 0.87 (a second attempt strips parentheticals). Orgs
that don't clear the bar are recorded with ein=null and their best candidate
kept for audit. An unmatched name does not establish absence of a US filing.

Usage: uv run python scripts/fetch_propublica.py
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from msqaly.recipients import RecipientIndex, recipient_key

DATA = Path(__file__).resolve().parents[1] / "data" / "yieldgiving"
OUT = DATA / "propublica_revenue.jsonl"
API = "https://projects.propublica.org/nonprofits/api/v2"
HEADERS = {
    "User-Agent": "mackenzie-scott-qaly research (github.com/MaxGhenis/mackenzie-scott-qaly)"
}
THRESHOLD = 0.87


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    return s


def get(url: str) -> dict:
    """Fetch JSON or fail; transport errors must never become cached nonmatches."""
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=30) as r:
                result = json.loads(r.read())
            if not isinstance(result, dict):
                raise ValueError(f"expected a JSON object from {url}")
            return result
        except HTTPError as exc:
            # Stop promptly on rate limiting/auth/not-found; retry only server failures.
            if exc.code < 500 or attempt == 3:
                raise
        except (URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 3:
                raise
        if attempt < 3:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}")  # unreachable; keeps the return contract explicit


def fetch_revenue(ein: int) -> dict[str, float]:
    """Retrieve one identified filer's positive annual revenue history."""
    detail = get(f"{API}/organizations/{ein}.json")
    if int(detail.get("organization", {}).get("ein", 0)) != ein:
        raise ValueError(f"organization endpoint did not identify requested EIN {ein}")
    if not isinstance(detail.get("filings_with_data"), list):
        raise ValueError(f"organization endpoint lacks filing history for EIN {ein}")
    revenue = {}
    for filing in detail["filings_with_data"]:
        year, rev = filing.get("tax_prd_yr"), filing.get("totrevenue")
        if year and rev and rev > 0:
            revenue[str(year)] = max(rev, revenue.get(str(year), 0))
    return revenue


def best_match(name: str) -> tuple[int | None, str | None, float]:
    target = norm(name)
    queries = [name]
    stripped = re.sub(r"\([^)]*\)", "", name).split(",")[0].strip()
    if stripped and stripped != name:
        queries.append(stripped)
    best: tuple[int | None, str | None, float] = (None, None, 0.0)
    for q in queries:
        data = get(f"{API}/search.json?q={quote(q)}")
        if not isinstance(data.get("organizations"), list):
            raise ValueError(f"search endpoint lacks organization results for {q!r}")
        for org in data["organizations"][:10]:
            score = SequenceMatcher(None, target, norm(org["name"])).ratio()
            if score > best[2]:
                best = (org["ein"], org["name"], score)
        if best[2] >= THRESHOLD:
            break
    return best


def main() -> None:
    orgs = json.loads((DATA / "organisations.json").read_text())
    index = RecipientIndex(orgs)
    done = {}
    if OUT.exists():
        rows = [json.loads(line) for line in OUT.read_text().splitlines() if line.strip()]
        done = index.records(rows, label="cached raw match")
    todo = [o for o in orgs if recipient_key(o) not in done]
    print(f"{len(orgs)} orgs, {len(done)} cached, {len(todo)} to fetch", flush=True)
    lock = threading.Lock()
    count = [0]

    def fetch_one(org):
        ein, matched, score = best_match(org["name"])
        rec = {
            "name": org["name"], "link": org["link"], "ein": None, "match": matched,
            "score": round(score, 3), "revenue_by_year": {},
            "retrieved_at": datetime.now(UTC).isoformat(),
            "match_status": "below_threshold" if matched else "no_candidate",
        }
        if ein is not None and score >= THRESHOLD:
            rec["ein"] = ein
            rec["revenue_by_year"] = fetch_revenue(ein)
            rec["source_url"] = f"{API}/organizations/{ein}.json"
            rec["match_status"] = "name_candidate"  # an audit still needs to verify identity
        with lock:
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            count[0] += 1
            if count[0] % 100 == 0:
                print(f"  {count[0]}/{len(todo)}", flush=True)

    with OUT.open("a") as fh, ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch_one, todo))
    print("done", flush=True)


if __name__ == "__main__":
    main()

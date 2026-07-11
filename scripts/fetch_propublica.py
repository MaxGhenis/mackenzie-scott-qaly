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
kept for audit — typically non-US recipients with no 990 at all.

Usage: uv run python scripts/fetch_propublica.py
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

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


def get(url: str) -> dict | None:
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=30) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None


def best_match(name: str) -> tuple[int | None, str | None, float]:
    target = norm(name)
    queries = [name]
    stripped = re.sub(r"\([^)]*\)", "", name).split(",")[0].strip()
    if stripped and stripped != name:
        queries.append(stripped)
    best: tuple[int | None, str | None, float] = (None, None, 0.0)
    for q in queries:
        data = get(f"{API}/search.json?q={quote(q)}")
        for org in (data or {}).get("organizations", [])[:10]:
            score = SequenceMatcher(None, target, norm(org["name"])).ratio()
            if score > best[2]:
                best = (org["ein"], org["name"], score)
        if best[2] >= THRESHOLD:
            break
    return best


def main() -> None:
    orgs = json.loads((DATA / "organisations.json").read_text())
    done = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            done.add(json.loads(line)["name"])
    todo = [o for o in orgs if o["name"] not in done]
    print(f"{len(orgs)} orgs, {len(done)} cached, {len(todo)} to fetch", flush=True)
    lock = threading.Lock()
    count = [0]

    def fetch_one(org):
        ein, matched, score = best_match(org["name"])
        rec = {"name": org["name"], "ein": None, "match": matched,
               "score": round(score, 3), "revenue_by_year": {}}
        if ein is not None and score >= THRESHOLD:
            rec["ein"] = ein
            detail = get(f"{API}/organizations/{ein}.json")
            for f in (detail or {}).get("filings_with_data", []):
                year, rev = f.get("tax_prd_yr"), f.get("totrevenue")
                if year and rev and rev > 0:
                    # Keep the largest filing per year (amended/duplicate rows).
                    rec["revenue_by_year"][str(year)] = max(
                        rev, rec["revenue_by_year"].get(str(year), 0)
                    )
        with lock:
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            count[0] += 1
            if count[0] % 100 == 0:
                print(f"  {count[0]}/{len(todo)}", flush=True)

    with OUT.open("a") as fh, ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(fetch_one, todo))
    print("done", flush=True)


if __name__ == "__main__":
    main()

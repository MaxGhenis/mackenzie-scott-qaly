"""Build and apply an LLM audit of the fuzzy name->EIN matches.

The ProPublica fetch (scripts/fetch_propublica.py) matches Yield Giving
recipient names to IRS 990 filers with difflib similarity. That is good
enough for exact-ish names but can mis-fire on generic names and misses
organizations whose legal name differs from their public one. This script:

``build <workdir>``
    Selects the audit-worthy strata --
    (A) accepted matches with similarity below 0.95,
    (B) rejected orgs whose best candidate scored at least 0.70,
    (C) matched orgs carrying undisclosed gifts whose pre-gift revenue is in
        the top 40 (they will carry the largest imputed dollars, so even
        high-similarity matches deserve a look) --
    and writes them as batches of 30 (``batch_NN/items.json`` +
    ``batch_NN/prompt.txt``) for an agentic model (gpt-5.6-terra via the
    Codex CLI) to verify against the live ProPublica API.

``apply <workdir>``
    Collects every ``batch_NN/verdicts.jsonl``, fetches corrected EINs'
    filings, and writes ``data/yieldgiving/match_audit.jsonl`` — the audit
    overlay that ``msqaly.allocation.load_revenue`` applies on top of the raw
    fetch (verdict WRONG/NO_990 on a matched org -> drop; FOUND -> replace
    with the corrected organization's revenue history).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_propublica import API, get  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "yieldgiving"
BATCH_SIZE = 30

PROMPT = """\
You are auditing name->EIN matches between MacKenzie Scott gift recipients
(Yield Giving) and IRS 990 filers (ProPublica Nonprofit Explorer).

Read items.json in this directory: an array of objects
{{name, mission, locations, gift_years, current: {{ein, match, score}}}}.
`current.ein` null means no match was accepted; `current.match` is the best
rejected candidate.

For EACH item, decide whether `current` identifies the same real-world
organization. Verify against the live API:
  curl -s "https://projects.propublica.org/nonprofits/api/v2/search.json?q=NAME"
  curl -s "https://projects.propublica.org/nonprofits/api/v2/organizations/EIN.json"
Compare legal vs public names (DBA forms, 'the', punctuation), the filer's
city/state against the item's locations, and mission coherence. Try name
variants when the obvious query fails.

Verdict per item:
  CORRECT - current EIN is the same organization; keep it.
  WRONG   - current EIN is a different organization and you found no right one.
  NO_990  - the recipient almost certainly files no US 990 (non-US entity,
            government body, or fiscally sponsored project).
  FOUND   - you identified the right EIN (use this both for unmatched items
            and for wrong matches you could correct); set "ein" to it.

Append one JSON object per line to verdicts.jsonl in this directory:
  {{"name": "<exact input name>", "verdict": "CORRECT|WRONG|NO_990|FOUND",
    "ein": <int or null>, "note": "<= 15 words"}}
Every input item must appear exactly once. Do not modify any other file.
"""


def build(workdir: Path) -> None:
    orgs = {o["name"]: o for o in json.loads((DATA / "organisations.json").read_text())}
    recs = [json.loads(x) for x in (DATA / "propublica_revenue.jsonl").read_text().splitlines()]

    def undisclosed_years(name: str) -> list[int]:
        return [
            int(g["year"])
            for g in orgs[name].get("gifts") or []
            if not (g.get("amount") or 0)
        ]

    borderline = [r for r in recs if r["ein"] and r["score"] < 0.95]
    rejected = [r for r in recs if not r["ein"] and r["score"] >= 0.70]
    # High-stakes: matched orgs with undisclosed gifts, largest pre-gift revenue.
    stakes_pool = [
        r
        for r in recs
        if r["ein"] and r["score"] < 0.98 and undisclosed_years(r["name"])
    ]
    stakes_pool.sort(
        key=lambda r: -max([float(v) for v in r["revenue_by_year"].values()] or [0])
    )
    chosen: dict[str, dict] = {}
    for r in borderline + rejected + stakes_pool[:40]:
        chosen.setdefault(r["name"], r)

    items = []
    for name, rec in sorted(chosen.items()):
        org = orgs[name]
        items.append(
            {
                "name": name,
                "mission": (org.get("mission") or "")[:300],
                "locations": org.get("locations") or [],
                "gift_years": sorted({int(g["year"]) for g in org.get("gifts") or []}),
                "current": {"ein": rec["ein"], "match": rec["match"], "score": rec["score"]},
            }
        )
    workdir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(items), BATCH_SIZE):
        b = workdir / f"batch_{i // BATCH_SIZE:02d}"
        b.mkdir(exist_ok=True)
        (b / "items.json").write_text(json.dumps(items[i : i + BATCH_SIZE], indent=1))
        (b / "prompt.txt").write_text(PROMPT)
    print(
        f"{len(items)} items ({len(borderline)} borderline, {len(rejected)} rejected, "
        f"{len(stakes_pool[:40])} high-stakes) in "
        f"{(len(items) + BATCH_SIZE - 1) // BATCH_SIZE} batches under {workdir}"
    )


def apply(workdir: Path) -> None:
    recs = {
        json.loads(x)["name"]: json.loads(x)
        for x in (DATA / "propublica_revenue.jsonl").read_text().splitlines()
    }
    verdicts: dict[str, dict] = {}
    for vf in sorted(workdir.glob("batch_*/verdicts.jsonl")):
        for line in vf.read_text().splitlines():
            if not line.strip():
                continue
            v = json.loads(line)
            verdicts[v["name"]] = v
    out = []
    counts = {"CORRECT": 0, "WRONG": 0, "NO_990": 0, "FOUND": 0}
    for name, v in sorted(verdicts.items()):
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
        had_match = bool(recs.get(name, {}).get("ein"))
        if v["verdict"] in ("WRONG", "NO_990") and had_match:
            out.append({"name": name, "action": "drop", "note": v.get("note", "")})
        elif v["verdict"] == "FOUND" and v.get("ein"):
            if recs.get(name, {}).get("ein") == v["ein"]:
                continue  # audit agreed with the fetch after all
            detail = get(f"{API}/organizations/{v['ein']}.json")
            revenue = {}
            for f in (detail or {}).get("filings_with_data", []):
                year, rev = f.get("tax_prd_yr"), f.get("totrevenue")
                if year and rev and rev > 0:
                    revenue[str(year)] = max(rev, revenue.get(str(year), 0))
            out.append(
                {
                    "name": name,
                    "action": "replace",
                    "ein": v["ein"],
                    "revenue_by_year": revenue,
                    "note": v.get("note", ""),
                }
            )
    path = DATA / "match_audit.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in out))
    print(f"verdicts {counts} -> {len(out)} overlay records in {path}")


if __name__ == "__main__":
    cmd, wd = sys.argv[1], Path(sys.argv[2])
    build(wd) if cmd == "build" else apply(wd)

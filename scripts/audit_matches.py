"""Build/apply an identity audit of all Yield Giving -> EIN candidates.

``build <workdir>`` includes every recipient, including exact-name candidates.
``apply <workdir>`` validates complete batches, retains all reviewer evidence in
``match_verdicts.jsonl`` and updates the effective ``match_audit.jsonl`` overlay.
HTTP failures abort before either output is replaced; they never mean no filer.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from msqaly.allocation import load_matches
from msqaly.recipients import RecipientIndex, RecipientKey

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_propublica import fetch_revenue  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "yieldgiving"
BATCH_SIZE = 30
VERDICTS = {"CORRECT", "WRONG", "NO_990", "FOUND"}

PROMPT = """\
Audit every input recipient -> EIN identity against primary evidence.
Read items.json. BOTH name and link identify a recipient; namesakes are
separate recipients. current.ein null means no accepted candidate.

Use the recipient's own website, official tax documents or government records
to bind its identity to an EIN. Compare city/state, mission, legal name and
history. Exact names and search rank do not prove identity. Distinguish related
foundations/subsidiaries and fiscal sponsors from an operating entity; do not
use an entire sponsor's revenue as project size. A failed request is not
no-filing evidence; report it and stop rather than inventing a verdict.

Append one JSON object per input to verdicts.jsonl, retaining exact name/link:
{"name": "...", "link": "...", "verdict": "CORRECT|WRONG|NO_990|FOUND",
 "ein": 123456789, "note": "reason", "source_url": "primary evidence URL",
 "confidence": "high|medium|low"}
CORRECT: existing EIN identifies intended recipient and revenue scope.
WRONG: existing candidate is wrong; no replacement established.
NO_990: primary evidence establishes no suitable independent US filer.
FOUND: correct EIN established, including corrections of wrong candidates.
Use null EIN for WRONG/NO_990. Every item must appear exactly once.
Do not edit items.json or any other file.
"""


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build(workdir: Path) -> None:
    orgs = json.loads((DATA / "organisations.json").read_text())
    index = RecipientIndex(orgs)
    matches = load_matches(DATA)
    items = []
    for key, org in sorted(index.by_key.items()):
        rec = matches.get(key, {})
        items.append({
            "name": org["name"], "link": org.get("link", ""), "mission": org.get("mission"),
            "locations": org.get("locations") or [],
            "gift_years": sorted({int(g["year"]) for g in org.get("gifts") or []}),
            "current": {"ein": rec.get("ein"), "match": rec.get("match"),
                        "score": rec.get("score")},
        })
    # Reusing old batches can silently mix two audit populations.
    if list(workdir.glob("batch_*")):
        raise ValueError(f"audit workdir already contains batches: {workdir}")
    workdir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(items), BATCH_SIZE):
        batch = workdir / f"batch_{i // BATCH_SIZE:02d}"
        batch.mkdir()
        (batch / "items.json").write_text(json.dumps(items[i:i + BATCH_SIZE], indent=1))
        (batch / "prompt.txt").write_text(PROMPT)
    print(f"{len(items)} recipients (all similarity scores) under {workdir}")


def collect_verdicts(workdir: Path, index: RecipientIndex) -> dict[RecipientKey, dict]:
    """Reject missing, duplicate and out-of-population verdicts."""
    expected, verdicts = {}, {}
    batches = sorted(workdir.glob("batch_*"))
    if not batches:
        raise ValueError(f"no audit batches in {workdir}")
    for batch in batches:
        items = json.loads((batch / "items.json").read_text())
        batch_items = index.records(items, label="batch input")
        overlap = expected.keys() & batch_items.keys()
        if overlap:
            raise ValueError(f"duplicate audit input identities: {overlap!r}")
        expected.update(batch_items)
        batch_verdicts = index.records(read_rows(batch / "verdicts.jsonl"), label="verdict")
        if batch_verdicts.keys() != batch_items.keys():
            raise ValueError(f"verdicts must exactly cover inputs in {batch}")
        for key, verdict in batch_verdicts.items():
            if verdict.get("verdict") not in VERDICTS:
                raise ValueError(f"unknown verdict for {key!r}: {verdict.get('verdict')!r}")
            source = verdict.get("source_url")
            url = urlsplit(source) if isinstance(source, str) else None
            if url is None or url.scheme not in {"https", "http"} or not url.netloc:
                raise ValueError(f"audit verdict needs a primary source URL for {key!r}")
            if verdict.get("confidence") not in {"high", "medium", "low"}:
                raise ValueError(f"audit verdict needs confidence for {key!r}")
            if "current" not in batch_items[key]:
                raise ValueError(f"audit input lacks its candidate snapshot: {key!r}")
            verdicts[key] = {
                **verdict, "link": index.by_key[key].get("link", ""),
                "audited_ein": batch_items[key]["current"].get("ein"),
            }
    if expected.keys() != index.by_key.keys():
        raise ValueError("audit inputs must cover every recipient; rebuild missing batches")
    return verdicts


def apply(workdir: Path) -> None:
    # Fetches may take minutes. Do not overwrite edits made while they run.
    batches = sorted(workdir.glob("batch_*"))
    input_paths = [
        DATA / "organisations.json", DATA / "propublica_revenue.jsonl",
        DATA / "match_audit.jsonl", DATA / "match_verdicts.jsonl",
        *(batch / name for batch in batches for name in ("items.json", "verdicts.jsonl")),
    ]

    def contents(path: Path) -> bytes | None:
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    original = {path: contents(path) for path in input_paths}
    index = RecipientIndex(json.loads((DATA / "organisations.json").read_text()))
    effective = load_matches(DATA)
    verdicts = collect_verdicts(workdir, index)
    overlay_path = DATA / "match_audit.jsonl"
    overlay = (
        index.records(read_rows(overlay_path), label="audit overlay")
        if overlay_path.exists() else {}
    )
    for key, verdict in sorted(verdicts.items()):
        current = effective.get(key, {})
        if verdict["audited_ein"] != current.get("ein"):
            raise ValueError(f"candidate changed since audit build for {key!r}; rebuild audit")
        action = verdict["verdict"]
        identity = {"name": key[0], "link": index.by_key[key].get("link", "")}
        if action == "CORRECT":
            if not current.get("ein"):
                raise ValueError(f"cannot confirm an unmatched recipient: {key!r}")
            if verdict.get("ein") not in (None, current["ein"]):
                raise ValueError(f"CORRECT changes EIN for {key!r}; use FOUND")
            if key in overlay:
                overlay[key] = {**overlay[key], **identity, "audit_verdict": verdict}
        elif action in ("WRONG", "NO_990"):
            if verdict.get("ein") is not None:
                raise ValueError(f"{action} cannot provide a replacement EIN: {key!r}")
            overlay[key] = {
                **identity, "action": "drop", "note": verdict.get("note", ""),
                "audit_verdict": verdict,
            }
        elif action == "FOUND":
            ein = verdict.get("ein")
            if not isinstance(ein, int) or isinstance(ein, bool) or not 0 < ein < 10**9:
                raise ValueError(f"FOUND needs a valid EIN for {key!r}")
            # Fetch first: failures leave both output files untouched.
            revenue = fetch_revenue(ein)
            overlay[key] = {
                **identity, "action": "replace", "ein": ein, "revenue_by_year": revenue,
                "note": verdict.get("note", ""), "audit_verdict": verdict,
            }

    def write_rows(path: Path, rows: list[dict]) -> None:
        pending = path.with_suffix(path.suffix + ".tmp")
        pending.write_text("".join(json.dumps(row) + "\n" for row in rows))
        pending.replace(path)

    if sorted(workdir.glob("batch_*")) != batches or any(
        contents(path) != before for path, before in original.items()
    ):
        raise ValueError(
            "audit inputs changed during apply; refusing to overwrite concurrent edits"
        )
    write_rows(DATA / "match_verdicts.jsonl", [verdicts[k] for k in sorted(verdicts)])
    write_rows(overlay_path, [overlay[k] for k in sorted(overlay)])
    print(f"verdicts {dict(Counter(v['verdict'] for v in verdicts.values()))}; "
          f"{len(overlay)} overlay records")


if __name__ == "__main__":
    command, directory = sys.argv[1], Path(sys.argv[2])
    if command not in {"build", "apply"}:
        raise SystemExit("usage: audit_matches.py build|apply <workdir>")
    build(directory) if command == "build" else apply(directory)

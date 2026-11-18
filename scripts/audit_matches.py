"""Build/apply an identity audit of all Yield Giving -> EIN candidates.

``build <workdir>`` includes every recipient, including exact-name candidates.
``apply <workdir>`` validates complete batches, retains all reviewer evidence in
``match_verdicts.jsonl`` and updates the effective ``match_audit.jsonl`` overlay.
Superseded verdicts and overlays remain in their respective histories.
HTTP failures abort before either output is replaced; they never mean no filer.
Both payloads are staged before publishing. If the second rename fails, rerun
the same audit to finish publication without adding duplicate verdicts.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from stat import S_IMODE
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from msqaly.allocation import load_matches
from msqaly.recipients import (
    CORRECTION_MAX_TAX_YEAR,
    RecipientIndex,
    RecipientKey,
    extract_filing_revenue,
    validate_ein,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_propublica import API, get, output_lock  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "yieldgiving"
BATCH_SIZE = 30
VERDICTS = {"CORRECT", "WRONG", "NO_990", "FOUND"}

PROMPT = """\
Audit every input recipient -> EIN identity against primary evidence.
Read items.json. BOTH name and link identify a recipient; namesakes are
separate recipients. current.ein null means no accepted candidate.
raw_candidate retains the original search match and similarity; it may have
been superseded. current.match/score are null after an EIN correction.
current.legal_name and source_url describe the effective filer when available.

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
FOUND: a different correct EIN established. Use CORRECT for the current EIN.
For FOUND, add classification "related_entity_scope" if changing to a distinct
related entity for an explicitly documented revenue scope. Use "wrong_entity"
if the prior EIN was demonstrably a different, unrelated organization.
Use null EIN for WRONG/NO_990. Every item must appear exactly once.
Do not edit items.json or any other file.
"""


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def retain_previous(record: dict, previous: dict | None, field: str) -> dict:
    """Attach a flat history so evidence remains tied to its original snapshot."""
    if previous is None:
        return record
    snapshot = {key: value for key, value in previous.items() if key != field}
    current = {key: value for key, value in record.items() if key != field}
    if current == snapshot:
        return previous
    return {**current, field: [*previous.get(field, []), snapshot]}


def matches_applied_verdict(verdict: dict, current: dict) -> bool:
    """Recognize exact replays after an audit changed the effective EIN."""
    if current.get("audit_verdict") != verdict:
        return False
    if verdict["verdict"] == "FOUND":
        return (
            current.get("action") == "replace" and current.get("ein") == verdict.get("ein")
            and verdict["audited_ein"] == current.get("old_ein")
            and verdict["audited_ein"] != current.get("ein")
        )
    if verdict["verdict"] in {"WRONG", "NO_990"}:
        return (
            current.get("action") == "drop" and current.get("ein") is None
            and verdict["audited_ein"] == current.get("old_ein")
        )
    return False


def publish_outputs(outputs: list[tuple[Path, bytes]]) -> None:
    """Stage every output before replacing either. Each rename is atomic by itself."""
    with ExitStack() as cleanup:
        staged = []
        for path, payload in outputs:
            with NamedTemporaryFile(
                "wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                pending = Path(stream.name)
                cleanup.callback(pending.unlink, missing_ok=True)
                stream.write(payload)
            if path.exists():
                pending.chmod(S_IMODE(path.stat().st_mode))
            staged.append((pending, path))
        for pending, path in staged:
            pending.replace(path)


def build(workdir: Path) -> None:
    orgs = json.loads((DATA / "organisations.json").read_text())
    index = RecipientIndex(orgs)
    matches = load_matches(DATA)
    items = []
    for key, org in sorted(index.by_key.items()):
        rec = matches.get(key, {})
        candidate = rec.get("raw_candidate", {})
        unchanged = rec.get("action") != "drop" and rec.get("ein") == candidate.get("ein")
        items.append({
            "name": org["name"], "link": org.get("link", ""), "mission": org.get("mission"),
            "locations": org.get("locations") or [],
            "gift_years": sorted({int(g["year"]) for g in org.get("gifts") or []}),
            "current": {
                "ein": rec.get("ein"), "legal_name": rec.get("legal_name"),
                "match": candidate.get("match") if unchanged else None,
                "score": candidate.get("score") if unchanged else None,
                "source_url": rec.get("source_url"),
            },
            "raw_candidate": candidate,
        })
    # Reusing old batches can silently mix two audit populations.
    if list(workdir.glob("batch_*")):
        raise ValueError(f"audit workdir already contains batches: {workdir}")
    workdir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(items), BATCH_SIZE):
        batch = workdir / f"batch_{i // BATCH_SIZE:02d}"
        batch.mkdir()
        (batch / "items.json").write_text(
            json.dumps(items[i:i + BATCH_SIZE], indent=1, allow_nan=False)
        )
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
                **{k: v for k, v in verdict.items() if k != "previous_verdicts"},
                "link": index.by_key[key].get("link", ""),
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
    ledger_path = DATA / "match_verdicts.jsonl"
    overlay = (
        index.records(read_rows(overlay_path), label="audit overlay")
        if overlay_path.exists() else {}
    )
    previous_verdicts = (
        index.records(read_rows(ledger_path), label="previous audit verdict")
        if ledger_path.exists() else {}
    )
    for key, verdict in sorted(verdicts.items()):
        current = effective.get(key, {})
        current_ein = current.get("ein")
        if matches_applied_verdict(verdict, current):
            continue
        if verdict["audited_ein"] != current_ein:
            raise ValueError(f"candidate changed since audit build for {key!r}; rebuild audit")
        action = verdict["verdict"]
        identity = {"name": key[0], "link": index.by_key[key].get("link", "")}
        previous = overlay.get(key)
        if action == "CORRECT":
            if not current_ein:
                raise ValueError(f"cannot confirm an unmatched recipient: {key!r}")
            ein = validate_ein(verdict.get("ein"), f"CORRECT for {key!r}", allow_none=True)
            if ein not in (None, current_ein):
                raise ValueError(f"CORRECT changes EIN for {key!r}; use FOUND")
            if previous is not None:
                overlay[key] = retain_previous(
                    {**previous, **identity, "audit_verdict": verdict}, previous, "previous_audits"
                )
        elif action in ("WRONG", "NO_990"):
            if verdict.get("ein") is not None:
                raise ValueError(f"{action} cannot provide a replacement EIN: {key!r}")
            row = {
                **identity, "action": "drop", "note": verdict.get("note", ""),
                "old_ein": current_ein, "audit_verdict": verdict,
                "identity_source_url": verdict["source_url"],
                "confidence": verdict["confidence"],
                "classification": "wrong_entity_drop" if action == "WRONG" else "no_990",
            }
            overlay[key] = retain_previous(row, previous, "previous_audits")
        elif action == "FOUND":
            ein = validate_ein(verdict.get("ein"), f"FOUND for {key!r}")
            if ein == current_ein:
                raise ValueError(f"FOUND repeats the current EIN for {key!r}; use CORRECT")
            classification = verdict.get("classification")
            if classification is None:
                classification = "changed_ein" if current_ein is not None else "recovered_ein"
            elif classification not in ("wrong_entity", "related_entity_scope"):
                raise ValueError(f"unknown FOUND classification for {key!r}: {classification!r}")
            # Fetch first: failures leave both output files untouched.
            source_url = f"{API}/organizations/{ein}.json"
            detail = get(source_url)
            revenue = extract_filing_revenue(detail, ein, max_tax_year=CORRECTION_MAX_TAX_YEAR)
            legal_name = detail["organization"].get("name")
            if not isinstance(legal_name, str) or not legal_name.strip():
                raise ValueError(f"API response needs a filer name for EIN {ein}")
            row = {
                **identity, "action": "replace", "ein": ein, "revenue_by_year": revenue,
                "note": verdict.get("note", ""), "audit_verdict": verdict,
                "source_url": source_url,
                "identity_source_url": verdict["source_url"],
                "confidence": verdict["confidence"],
                "old_ein": current_ein, "classification": classification,
                "legal_name": legal_name, "retrieved_at": datetime.now(UTC).isoformat(),
                "revenue_tax_year_max": CORRECTION_MAX_TAX_YEAR,
            }
            overlay[key] = retain_previous(row, previous, "previous_audits")

    def serialize(rows: list[dict]) -> bytes:
        return "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows).encode("utf-8")

    # Validate both payloads before publishing either, including extra metadata.
    ledger_text = serialize([
        retain_previous(verdicts[k], previous_verdicts.get(k), "previous_verdicts")
        for k in sorted(verdicts)
    ])
    overlay_text = serialize([overlay[k] for k in sorted(overlay)])

    with output_lock(overlay_path):
        if sorted(workdir.glob("batch_*")) != batches or any(
            contents(path) != before for path, before in original.items()
        ):
            raise ValueError(
                "audit inputs changed during apply; refusing to overwrite concurrent edits"
            )
        publish_outputs([
            (path, payload)
            for path, payload in ((ledger_path, ledger_text), (overlay_path, overlay_text))
            if payload != original[path]
        ])
    print(f"verdicts {dict(Counter(v['verdict'] for v in verdicts.values()))}; "
          f"{len(overlay)} overlay records")


if __name__ == "__main__":
    command, directory = sys.argv[1], Path(sys.argv[2])
    if command not in {"build", "apply"}:
        raise SystemExit("usage: audit_matches.py build|apply <workdir>")
    build(directory) if command == "build" else apply(directory)

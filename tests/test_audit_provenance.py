"""Keep each effective filer and its supporting evidence in the same snapshot."""

import importlib.util
import io
import json
from pathlib import Path

import pytest

from msqaly.allocation import load_matches, load_revenue
from msqaly.diagnostics import _audit_evidence
from msqaly.recipients import CORRECTION_MAX_TAX_YEAR, RecipientIndex, recipient_key

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_EIN = 363728910
CORRECTED_EIN = 133255679
NEXT_EIN = 123456789
RAW_RETRIEVED_AT = "2026-07-01T01:02:03+00:00"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_jsonl(path, row):
    path.write_text(json.dumps(row) + "\n")


@pytest.fixture
def strive_audit(tmp_path, monkeypatch):
    data = ROOT / "data" / "yieldgiving"
    org = next(
        org for org in json.loads((data / "organisations.json").read_text())
        if org["name"] == "STRIVE"
    )

    def strive_record(name):
        return next(
            row for line in (data / name).read_text().splitlines()
            if (row := json.loads(line))["name"] == "STRIVE"
        )

    original = {
        **strive_record("propublica_revenue.jsonl"),
        "retrieved_at": RAW_RETRIEVED_AT,
        "source_url": "https://example.org/raw-api",
        "legal_name": "Original namesake",
        "identity_source_url": "https://example.org/raw-identity",
        "classification": "raw_candidate",
    }
    correction = strive_record("match_audit.jsonl")
    (tmp_path / "organisations.json").write_text(json.dumps([org]))
    write_jsonl(tmp_path / "propublica_revenue.jsonl", original)
    write_jsonl(tmp_path / "match_audit.jsonl", correction)
    audit = load_script("audit_matches")
    monkeypatch.setattr(audit, "DATA", tmp_path)
    return audit, org, original, correction


def prepare(audit, org, batch, verdict, ein, **fields):
    run = audit.DATA / batch
    audit.build(run)
    write_jsonl(run / "batch_00" / "verdicts.jsonl", {
        "name": org["name"], "link": org["link"], "verdict": verdict, "ein": ein,
        "source_url": f"https://example.org/{batch}", "confidence": "high",
        "note": f"Fixture evidence for {verdict}", **fields,
    })
    return run


def filer(ein, revenue, legal_name="Successor Filer"):
    return {
        "organization": {"ein": ein, "name": legal_name},
        "filings_with_data": [
            {"tax_prd_yr": 2023, "totrevenue": revenue},
            {"tax_prd_yr": 2025, "totrevenue": 5 * revenue},
        ],
    }


def test_found_cannot_erase_strive_provenance_by_repeating_current_ein(strive_audit, monkeypatch):
    audit, org, _, correction = strive_audit
    run = prepare(audit, org, "repeat-found", "FOUND", CORRECTED_EIN)

    def fail_if_fetched(_):
        pytest.fail("same-EIN FOUND must fail before fetching another history")

    monkeypatch.setattr(audit, "get", fail_if_fetched)
    before = (audit.DATA / "match_audit.jsonl").read_bytes()
    with pytest.raises(ValueError, match="FOUND repeats the current EIN.*use CORRECT"):
        audit.apply(run)
    assert (audit.DATA / "match_audit.jsonl").read_bytes() == before
    assert not (audit.DATA / "match_verdicts.jsonl").exists()
    current = load_matches(audit.DATA)[recipient_key(org)]
    assert current["old_ein"] == ORIGINAL_EIN
    assert current["legal_name"] == correction["legal_name"]
    assert current["retrieved_at"] == correction["retrieved_at"]


def test_later_verdicts_keep_filer_snapshots_and_prior_evidence_separate(strive_audit, monkeypatch):
    audit, org, original, correction = strive_audit
    key = recipient_key(org)
    overlay = audit.DATA / "match_audit.jsonl"
    ledger = audit.DATA / "match_verdicts.jsonl"

    first = prepare(audit, org, "confirmation", "CORRECT", None)
    audit.apply(first)
    confirmed = json.loads(overlay.read_text())
    assert all(confirmed[k] == v for k, v in correction.items())
    assert confirmed["audit_verdict"]["audited_ein"] == CORRECTED_EIN
    assert confirmed["previous_audits"] == [correction]

    monkeypatch.setattr(audit, "get", lambda _: filer(NEXT_EIN, 200))
    second = prepare(audit, org, "new-ein", "FOUND", NEXT_EIN)
    audit.apply(second)
    replaced = json.loads(overlay.read_text())
    assert replaced["old_ein"] == CORRECTED_EIN
    assert replaced["classification"] == "changed_ein"
    assert replaced["identity_source_url"] == "https://example.org/new-ein"
    assert replaced["source_url"] == f"{audit.API}/organizations/{NEXT_EIN}.json"
    assert replaced["legal_name"] == "Successor Filer"
    assert replaced["retrieved_at"] not in (RAW_RETRIEVED_AT, correction["retrieved_at"])
    assert replaced["revenue_tax_year_max"] == CORRECTION_MAX_TAX_YEAR
    assert replaced["revenue_by_year"] == {"2023": 200}
    assert replaced["previous_audits"][0] == correction
    assert replaced["previous_audits"][1]["audit_verdict"]["verdict"] == "CORRECT"
    assert load_matches(audit.DATA)[key]["raw_candidate"]["ein"] == ORIGINAL_EIN
    assert load_revenue(audit.DATA)[key] == {2023: 200.0}
    assert json.loads(ledger.read_text())["previous_verdicts"][0]["verdict"] == "CORRECT"

    third = prepare(audit, org, "withdraw", "WRONG", None)
    audit.apply(third)
    dropped = load_matches(audit.DATA)[key]
    for field in ("ein", "legal_name", "source_url", "retrieved_at"):
        assert dropped[field] is None
    assert dropped["revenue_by_year"] == {}
    assert dropped["identity_source_url"] == "https://example.org/withdraw"
    assert dropped["old_ein"] == NEXT_EIN
    assert dropped["raw_candidate"]["retrieved_at"] == original["retrieved_at"]
    assert dropped["previous_audits"][2]["revenue_by_year"] == {"2023": 200}
    assert key not in load_revenue(audit.DATA)
    stale = correction["identity_source_url"]
    effective_drop = {k: v for k, v in dropped.items() if k != "audit_verdict"}
    evidence = _audit_evidence(RecipientIndex([org]), key, original, effective_drop, {
        "name": org["name"], "link": org["link"], "verdict": "WRONG", "ein": None,
        "audited_ein": CORRECTED_EIN, "source_url": stale, "confidence": "high",
    })
    assert evidence["source_url"] == dropped["identity_source_url"]

    fourth = prepare(audit, org, "recover", "FOUND", CORRECTED_EIN)
    monkeypatch.setattr(audit, "get", lambda _: filer(CORRECTED_EIN, 300, "Recovered Filer"))
    audit.apply(fourth)
    recovered = load_matches(audit.DATA)[key]
    assert recovered["ein"] == CORRECTED_EIN
    assert recovered["old_ein"] is None
    assert recovered["classification"] == "recovered_ein"
    assert recovered["identity_source_url"] == "https://example.org/recover"
    assert recovered["revenue_by_year"] == {"2023": 300}
    assert recovered["previous_audits"][3]["action"] == "drop"
    assert [v["verdict"] for v in json.loads(ledger.read_text())["previous_verdicts"]] == [
        "CORRECT", "FOUND", "WRONG",
    ]


@pytest.mark.parametrize("action,ein", [("drop", None), ("replace", ORIGINAL_EIN),
                                        ("replace", NEXT_EIN)])
def test_sparse_overlay_never_borrows_raw_filer_metadata(strive_audit, action, ein):
    audit, org, original, _ = strive_audit
    sparse = {"name": org["name"], "action": action}
    if action == "replace":
        sparse.update(ein=ein, revenue_by_year={"2023": 100})
    write_jsonl(audit.DATA / "match_audit.jsonl", sparse)
    current = load_matches(audit.DATA)[recipient_key(org)]
    assert current["ein"] == ein
    for field in (
        "source_url", "legal_name", "retrieved_at", "identity_source_url", "classification",
    ):
        assert current.get(field) is None
    assert current["raw_candidate"]["source_url"] == original["source_url"]
    assert current["raw_candidate"]["retrieved_at"] == RAW_RETRIEVED_AT


def test_found_remains_refreshable_with_current_and_archived_evidence(strive_audit, monkeypatch):
    audit, org, _, correction = strive_audit
    run = prepare(audit, org, "replace", "FOUND", NEXT_EIN)
    monkeypatch.setattr(audit, "get", lambda _: filer(NEXT_EIN, 200))
    audit.apply(run)
    row = json.loads((audit.DATA / "match_audit.jsonl").read_text())
    refresh = load_script("refresh_match_corrections")
    monkeypatch.setattr(refresh.time, "sleep", lambda _: None)

    def retrieve(request, **_):
        assert request.full_url == row["source_url"]
        return io.BytesIO(json.dumps(filer(NEXT_EIN, 400)).encode())

    monkeypatch.setattr(refresh, "urlopen", retrieve)
    refreshed, = refresh.refresh([row])
    assert refreshed["revenue_by_year"] == {"2023": 400}
    assert refreshed["previous_audits"] == [correction]
    for field in ("old_ein", "classification", "identity_source_url", "audit_verdict"):
        assert refreshed[field] == row[field]


@pytest.mark.parametrize("action", ["CORRECT", "WRONG", "NO_990", "FOUND"])
def test_identical_audit_replay_preserves_output_bytes(strive_audit, monkeypatch, action):
    audit, org, _, _ = strive_audit
    ein = NEXT_EIN if action == "FOUND" else None
    run = prepare(audit, org, "replay", action, ein)
    monkeypatch.setattr(audit, "get", lambda _: filer(NEXT_EIN, 200))
    audit.apply(run)
    paths = [audit.DATA / name for name in ("match_verdicts.jsonl", "match_audit.jsonl")]
    before = [path.read_bytes() for path in paths]

    def fail_if_fetched(_):
        pytest.fail("already applied FOUND should not fetch another history")

    monkeypatch.setattr(audit, "get", fail_if_fetched)
    audit.apply(run)
    assert [path.read_bytes() for path in paths] == before


def test_dated_confirmation_remains_new_evidence(strive_audit):
    audit, org, _, _ = strive_audit
    source = "https://example.org/confirmation"
    first = prepare(audit, org, "first", "CORRECT", None, source_url=source,
                    evidence_date="2026-11-17")
    second = prepare(audit, org, "second", "CORRECT", None, source_url=source,
                     evidence_date="2026-11-18")
    audit.apply(first)
    audit.apply(second)
    ledger = json.loads((audit.DATA / "match_verdicts.jsonl").read_text())
    assert ledger["evidence_date"] == "2026-11-18"
    assert ledger["previous_verdicts"][0]["evidence_date"] == "2026-11-17"


def test_second_staging_failure_leaves_neither_output_changed(strive_audit, monkeypatch):
    audit, org, _, _ = strive_audit
    run = prepare(audit, org, "stage-failure", "CORRECT", None)
    overlay = audit.DATA / "match_audit.jsonl"
    before = overlay.read_bytes()
    temp_factory = audit.NamedTemporaryFile

    def fail_second_output(*args, **kwargs):
        if kwargs["prefix"].startswith(".match_audit.jsonl."):
            raise OSError("second output cannot be staged")
        return temp_factory(*args, **kwargs)

    monkeypatch.setattr(audit, "NamedTemporaryFile", fail_second_output)
    with pytest.raises(OSError, match="second output cannot be staged"):
        audit.apply(run)
    assert overlay.read_bytes() == before
    assert not (audit.DATA / "match_verdicts.jsonl").exists()
    assert not list(audit.DATA.glob(".*.tmp"))


def test_retry_after_second_rename_failure_keeps_ledger_history_once(strive_audit, monkeypatch):
    audit, org, _, correction = strive_audit
    first = prepare(audit, org, "confirmation-before-failure", "CORRECT", None)
    audit.apply(first)
    run = prepare(audit, org, "rename-failure", "FOUND", NEXT_EIN)
    monkeypatch.setattr(audit, "get", lambda _: filer(NEXT_EIN, 200))
    ledger = audit.DATA / "match_verdicts.jsonl"
    overlay = audit.DATA / "match_audit.jsonl"
    before = overlay.read_bytes()
    replace = Path.replace

    def fail_overlay(path, target):
        if target == overlay:
            raise OSError("second rename failed")
        return replace(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", fail_overlay)
        with pytest.raises(OSError, match="second rename failed"):
            audit.apply(run)
    assert overlay.read_bytes() == before
    assert not list(audit.DATA.glob(".*.tmp"))
    partial_ledger = ledger.read_bytes()
    assert [v["verdict"] for v in json.loads(partial_ledger)["previous_verdicts"]] == ["CORRECT"]
    audit.apply(run)
    assert ledger.read_bytes() == partial_ledger
    current = load_matches(audit.DATA)[recipient_key(org)]
    assert current["ein"] == NEXT_EIN
    assert current["previous_audits"][0] == correction
    assert len(current["previous_audits"]) == 2
    assert not list(audit.DATA.glob(".*.tmp"))

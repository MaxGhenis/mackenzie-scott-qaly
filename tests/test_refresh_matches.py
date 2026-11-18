"""Refresh failures must preserve the committed match histories and identity evidence."""

import copy
import importlib.util
import io
import json
import sys
from pathlib import Path
from stat import S_IMODE
from urllib.error import HTTPError

import pytest


@pytest.fixture
def refresher(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts" / "refresh_match_corrections.py"
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location("refresh_match_corrections", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    return module


@pytest.fixture
def correction(refresher):
    return {
        "name": "Example recipient",
        "link": "example.org/",
        "action": "replace",
        "ein": 111111111,
        "old_ein": 222222222,
        "legal_name": "Example Recipient Inc",
        "revenue_by_year": {"2022": 100},
        "source_url": f"{refresher.API}/111111111.json",
        "identity_source_url": "https://example.org/financials/",
        "retrieved_at": "2026-11-16",
        "audited_at": "2026-11-16",
        "revenue_tax_year_max": 2024,
        "confidence": "high",
        "classification": "wrong_entity",
        "note": "Official recipient source identifies the corrected EIN.",
    }


def detail(ein=111111111, filings=None):
    return {
        "organization": {"ein": ein, "name": "Example Recipient Incorporated"},
        "filings_with_data": filings
        if filings is not None
        else [{"tax_prd_yr": 2023, "totrevenue": 200}],
    }


def write_fixture(path, rows):
    original = "".join(json.dumps(row) + "\n" for row in rows).encode()
    path.write_bytes(original)
    return original


@pytest.mark.parametrize(
    ("response", "expected_ein", "cutoff", "error"),
    [
        (detail(ein=333333333), 111111111, 2024, "expected EIN"),
        (detail(ein=True), 1, 2024, "positive EIN"),
        (detail(ein=1), True, 2024, "positive EIN"),
        (detail(), 111111111, False, "tax-year cutoff"),
        (detail(), 111111111, 2023.5, "tax-year cutoff"),
        (detail(filings=[]), 111111111, 2024, "no positive revenue history"),
        (detail(filings={}), 111111111, 2024, "lacks filing history"),
        (detail(filings=[None]), 111111111, 2024, "expected filing object"),
        (
            detail(filings=[{"tax_prd_yr": 2025, "totrevenue": 200}]),
            111111111,
            2024,
            "no positive revenue history",
        ),
        (detail(), 111111111, 2025, "tax-year cutoff"),
    ],
)
def test_invalid_response_cannot_replace_history(refresher, response, expected_ein, cutoff, error):
    with pytest.raises(ValueError, match=error):
        refresher.extract_revenue(response, expected_ein, cutoff)


@pytest.mark.parametrize(
    ("year", "value", "error"),
    [
        (2024.5, 12, "API filing tax year"),
        ("02024", 12, "noncanonical tax year"),
        (True, 12, "API filing tax year"),
        (2024, True, "finite number"),
        (2024, "12", "finite number"),
        (2024, float("inf"), "finite number"),
        (2025, float("nan"), "finite number"),
    ],
)
def test_malformed_filing_cannot_be_silently_dropped(refresher, year, value, error):
    response = detail(
        filings=[
            {"tax_prd_yr": 2023, "totrevenue": 200},
            {"tax_prd_yr": year, "totrevenue": value},
        ]
    )
    with pytest.raises(ValueError, match=error):
        refresher.extract_revenue(response, 111111111, 2024)


def test_extraction_preserves_duplicate_filing_convention_and_tax_year_cutoff(refresher):
    response = detail(
        filings=[
            {"tax_prd_yr": 2023, "totrevenue": 200},
            {"tax_prd_yr": 2023, "totrevenue": 150},
            {"tax_prd_yr": 2024, "totrevenue": 300},
            {"tax_prd_yr": 2025, "totrevenue": 999},
            {"tax_prd_yr": 2022, "totrevenue": 0},
            {"tax_prd_yr": 2021, "totrevenue": -20},
            {"tax_prd_yr": 2020, "totrevenue": None},
            {"tax_prd_yr": None, "totrevenue": 120},
        ]
    )
    assert refresher.extract_revenue(response, 111111111, 2024) == {
        "2024": 300,
        "2023": 200,
    }


def test_later_fetch_failure_leaves_original_file_bytes_intact(
    refresher, correction, monkeypatch, tmp_path
):
    rows = [copy.deepcopy(correction) for _ in range(3)]
    for i, row in enumerate(rows):
        row.update(name=f"Recipient {i}", ein=111111111 + i)
        row["source_url"] = f"{refresher.API}/{row['ein']}.json"
    path = tmp_path / "match_audit.jsonl"
    original = write_fixture(path, rows)
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 2:
            raise HTTPError(request.full_url, 429, "Too Many Requests", {}, None)
        return io.StringIO(json.dumps(detail()))

    monkeypatch.setattr(refresher, "DATA", path)
    monkeypatch.setattr(refresher, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["refresh_match_corrections.py", "--write"])
    with pytest.raises(HTTPError):
        refresher.main()
    assert path.read_bytes() == original
    assert calls == [row["source_url"] for row in rows[:2]]
    assert sorted(tmp_path.iterdir()) == [path]


def test_default_preview_never_changes_file(refresher, correction, monkeypatch, tmp_path, capsys):
    path = tmp_path / "match_audit.jsonl"
    original = write_fixture(path, [correction])
    monkeypatch.setattr(refresher, "DATA", path)
    monkeypatch.setattr(
        refresher, "urlopen", lambda request, timeout: io.StringIO(json.dumps(detail()))
    )
    monkeypatch.setattr(sys, "argv", ["refresh_match_corrections.py"])
    refresher.main()
    assert path.read_bytes() == original
    assert sorted(tmp_path.iterdir()) == [path]
    preview = json.loads(capsys.readouterr().out)
    assert preview["written"] is False
    assert preview["refreshed"][0]["revenue_changed"] is True


def test_success_preserves_identity_evidence_and_skips_drop_and_legacy_records(
    refresher, correction, monkeypatch, tmp_path
):
    drop = {
        **correction,
        "name": "Sponsored project",
        "action": "drop",
        "source_url": "https://example.org/project/",
    }
    legacy = {
        "name": "Legacy recovery",
        "action": "replace",
        "ein": 444444444,
        "revenue_by_year": {"2020": 400},
        "note": "Earlier audit retained this history.",
    }
    rows = [correction, drop, legacy]
    before = copy.deepcopy(rows)
    path = tmp_path / "match_audit.jsonl"
    write_fixture(path, rows)
    path.chmod(0o640)
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return io.StringIO(json.dumps(detail()))

    monkeypatch.setattr(refresher, "DATA", path)
    monkeypatch.setattr(refresher, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["refresh_match_corrections.py", "--write"])
    refresher.main()
    after = [json.loads(line) for line in path.read_text().splitlines()]
    assert S_IMODE(path.stat().st_mode) == 0o640
    assert calls == [correction["source_url"]]
    assert after[1:] == before[1:]
    refreshed = after[0]
    assert refreshed["revenue_by_year"] == {"2023": 200}
    assert refreshed["legal_name"] == "Example Recipient Incorporated"
    assert refreshed["retrieved_at"] != correction["retrieved_at"]
    for field in correction.keys() - {"revenue_by_year", "legal_name", "retrieved_at"}:
        assert refreshed[field] == correction[field]
    assert rows == before


def test_refresh_can_preserve_empty_history_but_cannot_erase_revenue(
    refresher, correction, monkeypatch
):
    monkeypatch.setattr(
        refresher, "urlopen", lambda request, timeout: io.StringIO(json.dumps(detail(filings=[])))
    )
    with pytest.raises(ValueError, match="no positive revenue history"):
        refresher.refresh([correction])
    unknown_history = {**correction, "old_ein": None, "revenue_by_year": {}}
    assert refresher.refresh([unknown_history])[0]["revenue_by_year"] == {}


def test_intervening_edit_survives_refresh(refresher, correction, monkeypatch, tmp_path):
    path = tmp_path / "match_audit.jsonl"
    write_fixture(path, [correction])
    concurrent = {**correction, "note": "A second writer supplied fresher evidence."}

    def fake_urlopen(request, timeout):
        with refresher.output_lock(path):
            write_fixture(path, [concurrent])
        return io.StringIO(json.dumps(detail()))

    monkeypatch.setattr(refresher, "DATA", path)
    monkeypatch.setattr(refresher, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["refresh_match_corrections.py", "--write"])
    with pytest.raises(RuntimeError, match="audit file changed during refresh"):
        refresher.main()
    assert json.loads(path.read_bytes()) == concurrent
    assert not list(tmp_path.glob("*.tmp"))


def test_refresh_write_lock_excludes_another_overlay_writer(refresher, correction, tmp_path):
    path = tmp_path / "match_audit.jsonl"
    original = write_fixture(path, [correction])
    with refresher.output_lock(path), pytest.raises(RuntimeError, match="another writer owns"):
        refresher.write_overlay(path, original, [{**correction, "revenue_by_year": {}}])
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_replace_cleans_unique_temp_file(refresher, correction, monkeypatch, tmp_path):
    path = tmp_path / "match_audit.jsonl"
    original = write_fixture(path, [correction])
    staged = []

    def fail_replace(self, target):
        assert self.is_file() and self.parent == target.parent
        staged.append(self)
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    for _ in range(2):
        with pytest.raises(OSError, match="simulated replace failure"):
            refresher.write_overlay(path, original, [correction])
        assert path.read_bytes() == original
    assert len(set(staged)) == 2
    assert all(not temporary.exists() for temporary in staged)


def test_strict_json_rejects_nonfinite_audit_metadata(refresher, correction, tmp_path):
    path = tmp_path / "match_audit.jsonl"
    original = write_fixture(path, [correction])
    with pytest.raises(ValueError, match="Out of range float"):
        refresher.write_overlay(path, original, [{**correction, "score": float("inf")}])
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))

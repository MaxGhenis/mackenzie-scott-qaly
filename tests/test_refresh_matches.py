"""Refresh failures must preserve the committed match histories and identity evidence."""

import copy
import importlib.util
import io
import json
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest


@pytest.fixture
def refresher(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts" / "refresh_match_corrections.py"
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
        (detail(filings=[]), 111111111, 2024, "no positive revenue history"),
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


def test_extraction_preserves_duplicate_filing_convention_and_tax_year_cutoff(refresher):
    response = detail(
        filings=[
            {"tax_prd_yr": 2023, "totrevenue": 200},
            {"tax_prd_yr": 2023, "totrevenue": 150},
            {"tax_prd_yr": 2024, "totrevenue": 300},
            {"tax_prd_yr": 2025, "totrevenue": 999},
            {"tax_prd_yr": 2022, "totrevenue": 0},
            {"tax_prd_yr": 2021, "totrevenue": -20},
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
    assert not path.with_suffix(".jsonl.tmp").exists()


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
    assert not path.with_suffix(".jsonl.tmp").exists()
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
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return io.StringIO(json.dumps(detail()))

    monkeypatch.setattr(refresher, "DATA", path)
    monkeypatch.setattr(refresher, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["refresh_match_corrections.py", "--write"])
    refresher.main()
    after = [json.loads(line) for line in path.read_text().splitlines()]
    assert calls == [correction["source_url"]]
    assert after[1:] == before[1:]
    refreshed = after[0]
    assert refreshed["revenue_by_year"] == {"2023": 200}
    assert refreshed["legal_name"] == "Example Recipient Incorporated"
    assert refreshed["retrieved_at"] != correction["retrieved_at"]
    for field in correction.keys() - {"revenue_by_year", "legal_name", "retrieved_at"}:
        assert refreshed[field] == correction[field]
    assert rows == before

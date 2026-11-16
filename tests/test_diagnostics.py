"""Diagnostics must conserve allocation dollars and distinguish observations from imputations."""

import copy
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from msqaly import diagnostics
from msqaly.allocation import derive_shares, impute_window


@pytest.fixture(scope="module")
def exported():
    return diagnostics.build()


@given(
    st.lists(st.one_of(st.none(), st.floats(min_value=1, max_value=1e9)), min_size=1, max_size=20),
    st.floats(min_value=0.1, max_value=1.2),
    st.floats(min_value=0, max_value=1e10),
    st.floats(min_value=0.1, max_value=10),
)
def test_imputation_conserves_residual_and_ignores_common_revenue_scale(
    revenues, beta, residual, scale
):
    amounts, weights, n_fallback = impute_window(revenues, beta, residual)
    scaled, _, _ = impute_window(
        [value * scale if value is not None else None for value in revenues], beta, residual
    )
    assert sum(amounts) == pytest.approx(residual, rel=1e-12, abs=1e-5)
    assert all(amount >= 0 for amount in amounts)
    assert all(weight > 0 for weight in weights)
    assert n_fallback == sum(value is None for value in revenues)
    assert scaled == pytest.approx(amounts, rel=1e-12, abs=1e-5)
    reversed_amounts, _, _ = impute_window(list(reversed(revenues)), beta, residual)
    assert list(reversed(reversed_amounts)) == pytest.approx(amounts, rel=1e-12, abs=1e-5)


def test_imputation_median_fallback_keeps_its_existing_meaning():
    amounts, weights, count = impute_window([100, 400, None], 0.5, 90)
    assert weights == [10, 20, 15]
    assert amounts == [20, 40, 30]
    assert count == 1
    assert impute_window([], 0.5, 0) == ([], [], 0)


def test_gift_ledger_reconciles_each_recipient_to_allocation(exported):
    _, ledger = exported
    _, allocation = derive_shares()
    totals = defaultdict(float)
    identities = set()
    for row in ledger:
        identity = row["name"], row["recipient_website_key"], row["gift_index"]
        assert identity not in identities
        identities.add(identity)
        totals[row["org_index"]] += row["assigned_amount_nominal_usd"]
        if row["selected_revenue_tax_year"] is not None:
            assert row["selected_revenue_tax_year"] < row["gift_year"]
            assert row["filing_lag_years"] > 0
    assert len(ledger) == allocation["n_gifts"]
    for org_index, expected in enumerate(allocation["org_usd"]):
        assert totals[org_index] == pytest.approx(expected, abs=0.001)


def test_disclosed_and_model_imputed_amounts_cannot_be_confused(exported):
    _, ledger = exported
    for row in ledger:
        if row["amount_status"] == "disclosed":
            assert row["disclosed_amount_nominal_usd"] > 0
            assert row["imputed_amount_nominal_usd"] == 0
            assert row["assigned_amount_nominal_usd"] == row["disclosed_amount_nominal_usd"]
            assert row["revenue_weight_method"] == "not_imputed"
            assert row["fallback_reason"] is None
        else:
            assert row["amount_status"] == "model_imputed"
            assert row["disclosed_amount_nominal_usd"] is None
            assert row["assigned_amount_nominal_usd"] == row["imputed_amount_nominal_usd"]
            assert (row["revenue_weight_method"] == "window_median_fallback") == bool(
                row["fallback_reason"]
            )


def test_summary_flows_and_window_dollars_reconcile(exported):
    summary, ledger = exported
    gifts, dollars = summary["gifts"], summary["nominal_usd"]
    assert gifts["disclosed"] + gifts["undisclosed"] == gifts["total"]
    assert sum(gifts["disclosed_revenue_availability"].values()) == gifts["disclosed"]
    assert sum(gifts["undisclosed_revenue_availability"].values()) == gifts["undisclosed"]
    assert (
        gifts["fallback"] + gifts["undisclosed_revenue_availability"]["usable"]
        == gifts["undisclosed"]
    )
    assert dollars["disclosed"] + dollars["imputed"] == pytest.approx(dollars["assigned_total"])
    assert dollars["fallback_imputed"] <= dollars["imputed"]
    assert gifts["calibration_pairs"] == summary["calibration"]["n_pairs"]
    for window, account in summary["windows"].items():
        rows = [row for row in ledger if row["imputation_window"] == window]
        imputed = sum(row["imputed_amount_nominal_usd"] for row in rows)
        assert imputed == pytest.approx(account["residual_nominal_usd"], abs=0.001)
        assert account["assigned_imputed_nominal_usd"] == pytest.approx(imputed, abs=0.001)


def test_corrected_identity_never_relabels_the_raw_candidate(exported):
    summary, ledger = exported
    strive = next(row for row in ledger if row["name"] == "STRIVE")
    assert strive["raw_accepted_ein"] == 363728910
    assert strive["raw_candidate_name"] == "Strive"
    assert strive["effective_ein"] == 133255679
    assert strive["effective_legal_name"] == "Strive International Inc"
    assert strive["verification_standing"] == "source_linked_correction"
    assert strive["identity_evidence_url"] == "https://strive.org/financials"
    mercy = next(row for row in ledger if row["name"] == "Mercy Housing")
    assert mercy["match_classification"] == "related_entity_scope"
    assert "historical Scott gift payee unverified" in mercy["audit_note"]
    cls = [row for row in ledger if row["name"] == "Community Legal Services"]
    assert {row["effective_ein"] for row in cls} == {860166615, 591156260}
    assert summary["recipients"]["verification_standing"]["source_linked_drop"] >= 1
    assert summary["recipients"]["verification_standing"]["legacy_overlay_without_source_url"] > 0


def test_cli_default_prints_without_writing(exported, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(diagnostics, "ROOT", tmp_path)
    monkeypatch.setattr(diagnostics, "build", lambda: exported)
    monkeypatch.setattr(sys, "argv", ["msqaly.diagnostics"])
    diagnostics.main()
    assert json.loads(capsys.readouterr().out) == json.loads(
        json.dumps(diagnostics.prepare_exports(*exported)[0])
    )
    assert list(tmp_path.iterdir()) == []


def test_explicit_export_csv_round_trip_preserves_amount_standing(
    exported, monkeypatch, tmp_path, capsys
):
    (tmp_path / "web").mkdir()
    (tmp_path / "results").mkdir()
    monkeypatch.setattr(diagnostics, "ROOT", tmp_path)
    monkeypatch.setattr(diagnostics, "build", lambda: exported)
    monkeypatch.setattr(sys, "argv", ["msqaly.diagnostics", "--write"])
    diagnostics.main()
    summary = json.loads((tmp_path / "web" / "matching_diagnostics.json").read_text())
    assert summary == json.loads(json.dumps(diagnostics.prepare_exports(*exported)[0]))
    with (tmp_path / "results" / "gift_ledger.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == summary["gifts"]["total"]
    for row, original in zip(rows, exported[1], strict=True):
        assert row["amount_status"] == original["amount_status"]
        difference = abs(
            Decimal(row["assigned_amount_nominal_usd"])
            - Decimal(str(original["assigned_amount_nominal_usd"]))
        )
        assert difference < Decimal("0.01")
        if row["amount_status"] == "disclosed":
            assert Decimal(row["disclosed_amount_nominal_usd"]) == Decimal(
                str(original["disclosed_amount_nominal_usd"])
            )
        assert bool(row["disclosed_amount_nominal_usd"]) == (row["amount_status"] == "disclosed")
    for window, account in summary["windows"].items():
        exported_dollars = sum(
            (
                Decimal(row["imputed_amount_nominal_usd"])
                for row in rows
                if row["imputation_window"] == window
            ),
            Decimal(0),
        )
        assert exported_dollars == Decimal(str(account["residual_nominal_usd"]))
    capsys.readouterr()


def test_canonical_summary_ignores_machine_precision_noise(exported):
    summary, ledger = exported
    altered = copy.deepcopy(summary)
    altered["calibration"]["r_squared"] += 2e-16
    for field in ("imputed", "assigned_total", "fallback_imputed"):
        altered["nominal_usd"][field] += 1e-5
    for account in altered["windows"].values():
        account["assigned_imputed_nominal_usd"] += 1e-5
        account["fallback_imputed_nominal_usd"] += 1e-5
    expected, _ = diagnostics.prepare_exports(summary, ledger)
    actual, _ = diagnostics.prepare_exports(altered, ledger)
    assert json.dumps(actual, allow_nan=False) == json.dumps(expected, allow_nan=False)
    assert summary != altered
    assert expected["export_precision"]["imputation_weight_significant_digits"] == 12
    assert Decimal(str(expected["nominal_usd"]["imputed"])) == sum(
        (Decimal(str(window["residual_nominal_usd"])) for window in expected["windows"].values()),
        Decimal(0),
    )


def test_csv_generation_failure_preserves_both_existing_exports(exported, monkeypatch, tmp_path):
    web, results = tmp_path / "web", tmp_path / "results"
    web.mkdir()
    results.mkdir()
    summary_path, ledger_path = web / "matching_diagnostics.json", results / "gift_ledger.csv"
    summary_path.write_bytes(b"previous summary\n")
    ledger_path.write_bytes(b"previous ledger\n")
    monkeypatch.setattr(diagnostics, "ROOT", tmp_path)
    monkeypatch.setattr(diagnostics, "build", lambda: exported)
    monkeypatch.setattr(sys, "argv", ["msqaly.diagnostics", "--write"])

    def fail_writer(self, rows):
        raise OSError("simulated CSV failure")

    monkeypatch.setattr(diagnostics.csv.DictWriter, "writerows", fail_writer)
    with pytest.raises(OSError, match="simulated CSV failure"):
        diagnostics.main()
    assert summary_path.read_bytes() == b"previous summary\n"
    assert ledger_path.read_bytes() == b"previous ledger\n"
    assert list(web.iterdir()) == [summary_path]
    assert list(results.iterdir()) == [ledger_path]


def test_nonfinite_summary_never_publishes_invalid_json(exported, tmp_path):
    (tmp_path / "web").mkdir()
    (tmp_path / "results").mkdir()
    summary, rows = diagnostics.prepare_exports(*exported)
    summary["calibration"]["r_squared"] = float("nan")
    with pytest.raises(ValueError):
        diagnostics.write_exports(summary, rows, tmp_path)
    assert list((tmp_path / "web").iterdir()) == []
    assert list((tmp_path / "results").iterdir()) == []


def test_csv_currency_and_weights_ignore_small_float_noise(exported):
    summary, ledger = exported
    altered = copy.deepcopy(ledger)
    for row in altered:
        if row["amount_status"] == "model_imputed":
            row["imputed_amount_nominal_usd"] *= 1 + 1e-15
            row["assigned_amount_nominal_usd"] *= 1 + 1e-15
            row["imputation_weight"] *= 1 + 1e-15
    expected_summary, expected_rows = diagnostics.prepare_exports(summary, ledger)
    actual_summary, actual_rows = diagnostics.prepare_exports(summary, altered)
    assert actual_summary == expected_summary
    assert actual_rows == expected_rows


def test_cent_remainder_ties_use_recipient_identity_not_input_order(exported):
    summary = copy.deepcopy(exported[0])
    source = next(row for row in exported[1] if row["amount_status"] == "model_imputed")
    rows = []
    for name in ("Z recipient", "A recipient"):
        row = {**source, "name": name, "imputation_window": "2025-2025"}
        row.update(imputed_amount_nominal_usd=1.005, assigned_amount_nominal_usd=1.005)
        rows.append(row)
    summary["windows"] = {
        "2025-2025": {
            "undisclosed_gifts": 2,
            "fallback_gifts": 2,
            "residual_nominal_usd": 2.01,
            "assigned_imputed_nominal_usd": 2.01,
            "fallback_imputed_nominal_usd": 2.01,
        }
    }
    _, first = diagnostics.prepare_exports(summary, rows)
    _, reversed_rows = diagnostics.prepare_exports(summary, list(reversed(rows)))
    amounts = {row["name"]: row["imputed_amount_nominal_usd"] for row in first}
    assert amounts == {"A recipient": "1.01", "Z recipient": "1.00"}
    assert amounts == {row["name"]: row["imputed_amount_nominal_usd"] for row in reversed_rows}


@pytest.fixture
def audit_data(tmp_path):
    """Keep synthetic audit evidence isolated from the public committed snapshots."""
    import shutil

    directory = tmp_path / "yieldgiving"
    shutil.copytree(diagnostics.DATA_DIR, directory)
    return directory


def automatic_recipient(directory):
    from msqaly.allocation import load_matches
    from msqaly.recipients import RecipientIndex

    orgs = json.loads((directory / "organisations.json").read_text())
    index = RecipientIndex(orgs)
    key, record = next(
        (key, record)
        for key, record in load_matches(directory).items()
        if record.get("ein") and not record.get("action")
    )
    return index.by_key[key], record


@pytest.mark.parametrize("explicit_ein", [True, False])
def test_full_verdict_ledger_confirms_raw_match_without_overlay(audit_data, explicit_ein):
    org, record = automatic_recipient(audit_data)
    verdict = {
        "name": org["name"],
        "link": org.get("link"),
        "verdict": "CORRECT",
        "ein": record["ein"] if explicit_ein else None,
        "audited_ein": record["ein"],
        "source_url": "https://fixture.example/recipient-ein",
        "confidence": "high",
        "note": "Fixture primary evidence confirms the current EIN.",
    }
    (audit_data / "match_verdicts.jsonl").write_text(json.dumps(verdict) + "\n")
    summary, ledger = diagnostics.build(data_dir=audit_data)
    row = next(row for row in ledger if row["name"] == org["name"])
    assert row["raw_accepted_ein"] == row["effective_ein"] == record["ein"]
    assert row["verification_standing"] == "source_linked_confirmation"
    assert row["identity_evidence_url"] == verdict["source_url"]
    assert row["audit_confidence"] == verdict["confidence"]
    assert row["audit_note"] == verdict["note"]
    assert summary["recipients"]["verification_standing"]["source_linked_confirmation"] == 1


def test_nested_found_verdict_exposes_current_replacement_evidence(audit_data):
    from msqaly.recipients import RecipientIndex

    index = RecipientIndex(json.loads((audit_data / "organisations.json").read_text()))
    path = audit_data / "match_audit.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    replacement = next(
        row for row in rows if row["action"] == "replace" and not row.get("identity_source_url")
    )
    org = index.by_key[index.resolve(replacement)]
    verdict = {
        "name": org["name"],
        "link": org.get("link"),
        "verdict": "FOUND",
        "ein": replacement["ein"],
        "audited_ein": None,
        "source_url": "https://fixture.example/new-replacement",
        "confidence": "medium",
        "note": "Fixture identifies the replacement filer.",
    }
    replacement["audit_verdict"] = verdict
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    _, ledger = diagnostics.build(data_dir=audit_data)
    row = next(row for row in ledger if row["name"] == org["name"])
    assert row["verification_standing"] == "source_linked_correction"
    assert row["identity_evidence_url"] == verdict["source_url"]
    assert row["audit_confidence"] == verdict["confidence"]
    assert row["audit_note"] == verdict["note"]


@pytest.mark.parametrize("action", ["CORRECT", "FOUND", "WRONG", "NO_990"])
def test_stale_full_ledger_evidence_cannot_prove_a_current_match(audit_data, action):
    org, record = automatic_recipient(audit_data)
    verdict = {
        "name": org["name"],
        "link": org.get("link"),
        "verdict": action,
        "ein": record["ein"] + 1 if action in {"CORRECT", "FOUND"} else None,
        "audited_ein": record["ein"] + 1,
        "source_url": "https://fixture.example/stale-ein",
        "confidence": "high",
        "note": "Fixture concerns an obsolete identity.",
    }
    (audit_data / "match_verdicts.jsonl").write_text(json.dumps(verdict) + "\n")
    _, ledger = diagnostics.build(data_dir=audit_data)
    row = next(row for row in ledger if row["name"] == org["name"])
    assert row["verification_standing"] == "automatic_name_match_unverified"
    assert row["identity_evidence_url"] is None
    assert row["audit_confidence"] is None


def test_stale_nested_verdict_does_not_replace_valid_current_correction_proof(audit_data):
    path = audit_data / "match_audit.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    replacement = next(row for row in rows if row["name"] == "STRIVE")
    original_source, original_note = replacement["identity_source_url"], replacement["note"]
    replacement["audit_verdict"] = {
        "name": "STRIVE",
        "link": "strive.org/",
        "verdict": "FOUND",
        "ein": 363728910,
        "source_url": "https://fixture.example/obsolete-strive",
        "confidence": "high",
        "note": "Fixture concerns the discarded Chicago filer.",
    }
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    _, ledger = diagnostics.build(data_dir=audit_data)
    row = next(row for row in ledger if row["name"] == "STRIVE")
    assert row["effective_ein"] == 133255679
    assert row["identity_evidence_url"] == original_source
    assert row["audit_note"] == original_note


@pytest.mark.parametrize("action", ["WRONG", "NO_990"])
def test_full_ledger_drop_evidence_applies_only_to_no_effective_ein(audit_data, action):
    orgs = json.loads((audit_data / "organisations.json").read_text())
    org = next(org for org in orgs if org["name"] == "Abriendo Puertas/Opening Doors")
    verdict = {
        "name": org["name"],
        "link": org["link"],
        "verdict": action,
        "ein": None,
        "audited_ein": 61338937,
        "source_url": "https://fixture.example/project-sponsorship",
        "confidence": "high",
        "note": "Fixture project sponsorship confirms the drop.",
    }
    (audit_data / "match_verdicts.jsonl").write_text(json.dumps(verdict) + "\n")
    _, ledger = diagnostics.build(data_dir=audit_data)
    row = next(row for row in ledger if row["name"] == org["name"])
    assert row["effective_ein"] is None
    assert row["verification_standing"] == "source_linked_drop"
    assert row["identity_evidence_url"] == verdict["source_url"]

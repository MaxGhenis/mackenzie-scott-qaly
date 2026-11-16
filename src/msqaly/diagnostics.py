"""Inspect matching coverage and model-imputed gift dollars without changing the fit.

``python -m msqaly.diagnostics`` prints a compact summary. Explicit ``--write``
exports that summary and a gift-level CSV from the committed gift snapshot.
Dollar amounts remain nominal; imputed amounts do not represent disclosed gifts.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import tempfile
from collections import Counter, defaultdict
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from urllib.parse import urlsplit

from .allocation import (
    DATA_DIR,
    ROOT,
    derive_shares,
    impute_window,
    load_inputs,
    load_matches,
    load_revenue,
    pre_gift_revenue_year,
    year_window,
)
from .recipients import RecipientIndex, recipient_key


def _audit_evidence(
    index: RecipientIndex, key: tuple[str, str], raw: dict, effective: dict, verdict: dict | None
) -> dict:
    """Use a verdict's evidence only while it describes the effective identity."""
    for candidate in (effective.get("audit_verdict"), verdict):
        if not isinstance(candidate, dict):
            continue
        try:
            if index.resolve(candidate) != key:
                continue
        except ValueError:
            continue
        source = candidate.get("source_url")
        url = urlsplit(source) if isinstance(source, str) else None
        if (
            url is None
            or url.scheme not in {"http", "https"}
            or not url.netloc
            or candidate.get("confidence") not in {"high", "medium", "low"}
        ):
            continue
        action, target = candidate.get("verdict"), candidate.get("ein")
        if action == "CORRECT" and target is None:
            target = candidate.get("audited_ein")
        if action in {"FOUND", "CORRECT"}:
            if (
                not isinstance(target, int)
                or isinstance(target, bool)
                or target != effective.get("ein")
                or not 0 < target < 10**9
            ):
                continue
            standing = (
                "source_linked_confirmation" if action == "CORRECT" else "source_linked_correction"
            )
        elif action in {"WRONG", "NO_990"} and effective.get("ein") is None:
            if target is not None:
                continue
            standing = "source_linked_drop"
        else:
            continue
        return {
            "standing": standing,
            "source_url": source,
            "confidence": candidate["confidence"],
            "note": candidate.get("note"),
        }
    if effective.get("identity_source_url"):
        standing = (
            "source_linked_drop"
            if effective.get("action") == "drop"
            else "source_linked_correction"
        )
    elif effective.get("action"):
        standing = "legacy_overlay_without_source_url"
    else:
        standing = "automatic_name_match_unverified" if raw.get("ein") else "unmatched"
    return {
        "standing": standing,
        "source_url": effective.get("identity_source_url"),
        "confidence": effective.get("confidence"),
        "note": effective.get("note"),
    }


def build(
    data_dir: str | Path | None = None, params_path: str | Path | None = None
) -> tuple[dict, list]:
    """Return a summary and identity-safe gift ledger using allocation's exact weights."""
    directory = Path(data_dir) if data_dir else DATA_DIR
    orgs, _, _ = load_inputs(directory)
    index = RecipientIndex(orgs)
    raw = index.records(
        [
            json.loads(line)
            for line in (directory / "propublica_revenue.jsonl").read_text().splitlines()
            if line.strip()
        ],
        label="raw match",
    )
    matches, revenue = load_matches(directory), load_revenue(directory)
    verdict_path = directory / "match_verdicts.jsonl"
    verdicts = (
        index.records(
            [json.loads(line) for line in verdict_path.read_text().splitlines() if line.strip()],
            label="audit verdict",
        )
        if verdict_path.exists()
        else {}
    )
    evidence = {
        key: _audit_evidence(index, key, raw[key], effective, verdicts.get(key))
        for key, effective in matches.items()
    }
    _, stats = derive_shares(data_dir=directory, params_path=params_path)
    ledger = []
    by_window = defaultdict(list)
    for org_index, org in enumerate(orgs):
        key = recipient_key(org)
        original, effective = raw[key], matches[key]
        history = revenue.get(key) or {}
        legal_name = effective.get("legal_name")
        if not legal_name and effective.get("ein") == original.get("ein"):
            legal_name = original.get("match") if effective.get("ein") else None
        for gift_index, gift in enumerate(org.get("gifts") or []):
            year = int(gift["year"])
            revenue_year = pre_gift_revenue_year(history, year)
            value = history.get(revenue_year)
            reason = (
                "no_ein"
                if not effective.get("ein")
                else "no_history"
                if not history
                else "no_pre_gift_history"
                if revenue_year is None
                else None
            )
            disclosed = gift.get("amount") or 0
            window = year_window(year)
            window_name = f"{window[0]}-{window[1]}"
            row = {
                "name": org["name"],
                "link": org.get("link"),
                "recipient_website_key": key[1],
                "org_index": org_index,
                "gift_index": gift_index,
                "gift_year": year,
                "imputation_window": window_name,
                "amount_status": "disclosed" if disclosed > 0 else "model_imputed",
                "disclosed_amount_nominal_usd": disclosed if disclosed > 0 else None,
                "imputed_amount_nominal_usd": 0.0,
                "assigned_amount_nominal_usd": float(disclosed),
                "raw_accepted_ein": original.get("ein"),
                "raw_candidate_name": original.get("match"),
                "raw_name_similarity": original.get("score"),
                "effective_ein": effective.get("ein"),
                "effective_legal_name": legal_name,
                "verification_standing": evidence[key]["standing"],
                "match_classification": effective.get("classification"),
                "audit_confidence": evidence[key]["confidence"],
                "audit_note": evidence[key]["note"],
                "identity_evidence_url": evidence[key]["source_url"],
                "revenue_source_url": (
                    effective.get("source_url") if effective.get("ein") else None
                )
                or (
                    f"https://projects.propublica.org/nonprofits/api/v2/organizations/"
                    f"{effective['ein']}.json"
                    if effective.get("ein")
                    else None
                ),
                "revenue_retrieved_at": effective.get("retrieved_at"),
                "selected_revenue_tax_year": revenue_year,
                "pre_gift_revenue_nominal_usd": value,
                "filing_lag_years": year - revenue_year if revenue_year is not None else None,
                "calibration_pair": disclosed > 0 and reason is None,
                "revenue_availability": "usable" if reason is None else reason,
                "fallback_reason": reason if disclosed <= 0 else None,
                "revenue_weight_method": (
                    "not_imputed"
                    if disclosed > 0
                    else "revenue_power"
                    if reason is None
                    else "window_median_fallback"
                ),
                "imputation_weight": None,
            }
            ledger.append(row)
            if disclosed <= 0:
                by_window[window_name].append(row)
    windows = {}
    for window, rows in sorted(by_window.items()):
        residual = stats["imputed_by_window"][window]
        amounts, weights, fallback_count = impute_window(
            [row["pre_gift_revenue_nominal_usd"] for row in rows], stats["elasticity"], residual
        )
        for row, amount, weight in zip(rows, amounts, weights, strict=True):
            row["imputed_amount_nominal_usd"] = amount
            row["assigned_amount_nominal_usd"] = amount
            row["imputation_weight"] = weight
        windows[window] = {
            "undisclosed_gifts": len(rows),
            "fallback_gifts": fallback_count,
            "residual_nominal_usd": residual,
            "assigned_imputed_nominal_usd": sum(amounts),
            "fallback_imputed_nominal_usd": sum(
                row["imputed_amount_nominal_usd"] for row in rows if row["fallback_reason"]
            ),
        }
    assigned_by_org = defaultdict(float)
    for row in ledger:
        assigned_by_org[row["org_index"]] += row["assigned_amount_nominal_usd"]
    if any(
        abs(assigned_by_org[i] - expected) > 0.001 for i, expected in enumerate(stats["org_usd"])
    ):
        raise ValueError("diagnostic gift ledger does not reconcile to allocation")
    disclosed_rows = [row for row in ledger if row["amount_status"] == "disclosed"]
    imputed_rows = [row for row in ledger if row["amount_status"] == "model_imputed"]
    fallback_dollars = sum(
        row["imputed_amount_nominal_usd"] for row in imputed_rows if row["fallback_reason"]
    )
    total_dollars = sum(row["assigned_amount_nominal_usd"] for row in ledger)
    fallback_count = sum(bool(row["fallback_reason"]) for row in imputed_rows)
    summary = {
        "schema_version": 1,
        "units": "nominal USD; dollar vintages follow each gift/revenue tax year",
        "gift_snapshot_date": "2026-07-11",
        "gift_years": [
            min(row["gift_year"] for row in ledger),
            max(row["gift_year"] for row in ledger),
        ],
        "imputed_amount_notice": "Model-imputed amounts do not represent disclosed gift amounts.",
        "recipients": {
            "total": len(orgs),
            "effective_ein": sum(bool(rec.get("ein")) for rec in matches.values()),
            "with_revenue_history": sum(bool(history) for history in revenue.values()),
            "verification_standing": dict(
                sorted(Counter(proof["standing"] for proof in evidence.values()).items())
            ),
        },
        "gifts": {
            "total": len(ledger),
            "disclosed": len(disclosed_rows),
            "undisclosed": len(imputed_rows),
            "calibration_pairs": sum(row["calibration_pair"] for row in ledger),
            "disclosed_revenue_availability": dict(
                sorted(Counter(row["revenue_availability"] for row in disclosed_rows).items())
            ),
            "undisclosed_revenue_availability": dict(
                sorted(Counter(row["revenue_availability"] for row in imputed_rows).items())
            ),
            "fallback": fallback_count,
            "fallback_share_of_undisclosed_gifts": fallback_count / len(imputed_rows)
            if imputed_rows
            else 0.0,
        },
        "nominal_usd": {
            "disclosed": stats["disclosed_usd"],
            "imputed": stats["imputed_usd"],
            "assigned_total": total_dollars,
            "fallback_imputed": fallback_dollars,
            "fallback_share_of_imputed": fallback_dollars / stats["imputed_usd"]
            if stats["imputed_usd"]
            else 0.0,
            "fallback_share_of_total": fallback_dollars / total_dollars if total_dollars else 0.0,
        },
        "calibration": {
            "elasticity": round(stats["elasticity"], 12),
            "r_squared": round(stats["elasticity_r2"], 12),
            "n_pairs": stats["n_calibration"],
        },
        "filing_lag_year_counts": {
            label: dict(
                sorted(
                    Counter(
                        row["filing_lag_years"]
                        for row in rows
                        if row["selected_revenue_tax_year"] is not None
                    ).items()
                )
            )
            for label, rows in (
                ("calibration", [r for r in disclosed_rows if r["calibration_pair"]]),
                ("undisclosed_usable", imputed_rows),
            )
        },
        "windows": windows,
    }
    return summary, ledger


CENT = Decimal("0.01")


def _money(value: float) -> Decimal:
    if not math.isfinite(value):
        raise ValueError("diagnostic dollar amounts must be finite")
    return Decimal(str(value)).quantize(CENT)


def prepare_exports(summary: dict, ledger: list[dict]) -> tuple[dict, list[dict]]:
    """Serialize currency at cents while preserving each window's full residual.

    Largest-remainder cent rounding changes export rows only. The allocation
    pipeline and build() retain their original floating-point amounts.
    """
    canonical = copy.deepcopy(summary)
    rows = [dict(row) for row in ledger]
    by_window = defaultdict(list)
    for index, row in enumerate(rows):
        if any(isinstance(value, float) and not math.isfinite(value) for value in row.values()):
            raise ValueError("diagnostic CSV numbers must be finite")
        if row["imputation_weight"] is not None:
            row["imputation_weight"] = format(row["imputation_weight"], ".12g")
        if row["amount_status"] == "model_imputed":
            by_window[row["imputation_window"]].append(index)
    for window, indices in by_window.items():
        exact_cents = {
            index: Decimal(str(ledger[index]["imputed_amount_nominal_usd"])) * 100
            for index in indices
        }
        cents = {
            index: int(value.to_integral_value(rounding=ROUND_FLOOR))
            for index, value in exact_cents.items()
        }
        target = int(_money(summary["windows"][window]["residual_nominal_usd"]) * 100)
        remaining = target - sum(cents.values())
        if not 0 <= remaining <= len(indices):
            raise ValueError(f"cannot round inconsistent imputation window {window}")
        order = sorted(
            indices,
            key=lambda index: (
                -(exact_cents[index] - cents[index]),
                ledger[index]["name"],
                ledger[index]["recipient_website_key"],
                ledger[index]["gift_year"],
                ledger[index]["gift_index"],
            ),
        )
        for index in order[:remaining]:
            cents[index] += 1
        fallback_cents = 0
        for index in indices:
            amount = format(Decimal(cents[index]) / 100, ".2f")
            rows[index]["imputed_amount_nominal_usd"] = amount
            rows[index]["assigned_amount_nominal_usd"] = amount
            if rows[index]["fallback_reason"]:
                fallback_cents += cents[index]
        account = canonical["windows"][window]
        account["residual_nominal_usd"] = float(Decimal(target) / 100)
        account["assigned_imputed_nominal_usd"] = float(Decimal(target) / 100)
        account["fallback_imputed_nominal_usd"] = float(Decimal(fallback_cents) / 100)
    dollars = canonical["nominal_usd"]
    dollars["disclosed"] = float(_money(dollars["disclosed"]))
    for field, window_field in (
        ("imputed", "residual_nominal_usd"),
        ("fallback_imputed", "fallback_imputed_nominal_usd"),
    ):
        dollars[field] = float(
            sum(
                (_money(account[window_field]) for account in canonical["windows"].values()),
                Decimal(0),
            )
        )
    dollars["assigned_total"] = float(_money(dollars["disclosed"]) + _money(dollars["imputed"]))
    dollars["fallback_share_of_imputed"] = (
        round(dollars["fallback_imputed"] / dollars["imputed"], 12) if dollars["imputed"] else 0.0
    )
    dollars["fallback_share_of_total"] = (
        round(dollars["fallback_imputed"] / dollars["assigned_total"], 12)
        if dollars["assigned_total"]
        else 0.0
    )
    canonical["gifts"]["fallback_share_of_undisclosed_gifts"] = round(
        canonical["gifts"]["fallback_share_of_undisclosed_gifts"], 12
    )
    for field in ("elasticity", "r_squared"):
        canonical["calibration"][field] = round(canonical["calibration"][field], 12)
    canonical["export_precision"] = {
        "nominal_dollars": "cents; disclosed CSV amounts retain original source values",
        "fractions_and_calibration_decimal_places": 12,
        "imputation_weight_significant_digits": 12,
        "imputed_csv_rounding": (
            "Largest-remainder cents within each window; "
            "ties use recipient identity and gift index. "
            "Each exported amount differs by less than one cent from the internal imputation."
        ),
    }
    return canonical, rows


def write_exports(summary: dict, ledger: list[dict], root: Path) -> None:
    """Stage both outputs before replacing either canonical file."""
    serialized = json.dumps(summary, indent=2, allow_nan=False) + "\n"
    summary_path = root / "web" / "matching_diagnostics.json"
    ledger_path = root / "results" / "gift_ledger.csv"
    staged = []
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=summary_path.parent, suffix=".json.tmp", delete=False
        ) as stream:
            temporary_summary = Path(stream.name)
            staged.append(temporary_summary)
            stream.write(serialized)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=ledger_path.parent,
            suffix=".csv.tmp",
            newline="",
            delete=False,
        ) as stream:
            temporary_ledger = Path(stream.name)
            staged.append(temporary_ledger)
            writer = csv.DictWriter(stream, fieldnames=list(ledger[0]))
            writer.writeheader()
            writer.writerows(ledger)
        temporary_summary.replace(summary_path)
        temporary_ledger.replace(ledger_path)
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="export web summary and gift CSV")
    args = parser.parse_args()
    summary, ledger = prepare_exports(*build())
    serialized = json.dumps(summary, indent=2, allow_nan=False)
    if args.write:
        write_exports(summary, ledger, ROOT)
    print(serialized)


if __name__ == "__main__":
    main()

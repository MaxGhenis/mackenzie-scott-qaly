"""Entity identity, overlay isolation, and recoverable fetch/audit failures."""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError

import pytest
from hypothesis import given
from hypothesis import strategies as st

from msqaly.allocation import (
    calibrate_elasticity,
    load_matches,
    load_revenue,
    pre_gift_revenue,
)
from msqaly.recipients import RecipientIndex, recipient_key

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = script("fetch_propublica")
audit = script("audit_matches")


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def dataset(path, orgs, rows, overlay=()):
    (path / "organisations.json").write_text(json.dumps(orgs))
    write_rows(path / "propublica_revenue.jsonl", rows)
    write_rows(path / "match_audit.jsonl", overlay)


def raw(org, ein=123456789, revenue=10):
    return {**org, "ein": ein, "match": org["name"], "score": 1.0,
            "revenue_by_year": {"2020": revenue}}


def test_namesakes_keep_distinct_histories_and_overlay_scope(tmp_path):
    az = {"name": "Community Legal Services", "link": "clsaz.org/"}
    fl = {"name": "Community Legal Services", "link": "www.clsmf.org/"}
    dataset(tmp_path, [az, fl], [raw(az, revenue=10), raw(fl, revenue=100)],
            [{**fl, "action": "replace", "ein": 591156260, "revenue_by_year": {"2020": 200}}])
    revenue = load_revenue(tmp_path)
    assert revenue[recipient_key(az)] == {2020: 10.0}
    assert revenue[recipient_key(fl)] == {2020: 200.0}


def test_legacy_name_only_rows_resolve_only_unique_recipients(tmp_path):
    org = {"name": "Unique", "link": "unique.example"}
    dataset(tmp_path, [org], [raw({"name": "Unique"})],
            [{"name": "Unique", "action": "drop"}])
    assert load_revenue(tmp_path) == {}
    assert load_matches(tmp_path)[recipient_key(org)]["ein"] is None


@pytest.mark.parametrize("layer", ["raw", "overlay"])
def test_ambiguous_name_only_rows_are_rejected(tmp_path, layer):
    orgs = [{"name": "Same", "link": "az.example"},
            {"name": "Same", "link": "fl.example"}]
    rows = [raw(o) for o in orgs]
    overlay = []
    if layer == "raw":
        rows[0].pop("link")
    else:
        overlay = [{"name": "Same", "action": "drop"}]
    dataset(tmp_path, orgs, rows, overlay)
    with pytest.raises(ValueError, match="ambiguous recipient"):
        load_revenue(tmp_path)


@pytest.mark.parametrize("layer", ["raw", "overlay"])
def test_duplicate_identity_rows_are_rejected(tmp_path, layer):
    org = {"name": "One", "link": "one.example"}
    rows, overlay = [raw(org)], []
    if layer == "raw":
        rows.append(raw(org))
    else:
        overlay = [{**org, "action": "drop"}] * 2
    dataset(tmp_path, [org], rows, overlay)
    with pytest.raises(ValueError, match="duplicate"):
        load_revenue(tmp_path)


@pytest.mark.parametrize("bad", [
    {"name": "Unknown", "action": "drop"},
    {"name": "Known", "link": "someone-else.example", "action": "drop"},
])
def test_overlay_cannot_target_an_unknown_recipient(tmp_path, bad):
    org = {"name": "Known", "link": "known.example"}
    dataset(tmp_path, [org], [raw(org)], [bad])
    with pytest.raises(ValueError, match="unknown recipient"):
        load_revenue(tmp_path)


def test_calibration_uses_each_namesakes_own_revenue():
    orgs = [
        {"name": "Same", "link": "a.example", "gifts": [{"year": 2021, "amount": 100}]},
        {"name": "Same", "link": "b.example", "gifts": [{"year": 2021, "amount": 1000}]},
    ]
    revenue = {recipient_key(orgs[0]): {2020: 10}, recipient_key(orgs[1]): {2020: 100}}
    beta, r2, n = calibrate_elasticity(orgs, revenue)
    assert beta == pytest.approx(1)
    assert r2 == pytest.approx(1)
    assert n == 2


@given(st.dictionaries(st.integers(1900, 2099), st.integers(1, 10**10)),
       st.integers(1901, 2099))
def test_pre_gift_revenue_uses_latest_strictly_earlier_year(history, gift_year):
    eligible = [(y, v) for y, v in history.items() if y < gift_year]
    expected = max(eligible)[1] if eligible else None
    assert pre_gift_revenue(history, gift_year) == expected
    future = {**history, gift_year: 10**20, gift_year + 1: 10**21}
    assert pre_gift_revenue(future, gift_year) == expected


@given(st.lists(st.integers(1, 10**8), min_size=1, max_size=8), st.data())
def test_overlay_isolation_and_row_order_invariance(values, data):
    orgs = [{"name": "Shared name", "link": f"recipient-{i}.example"}
            for i in range(len(values))]
    rows = [raw(o, revenue=v) for o, v in zip(orgs, values, strict=True)]
    dropped = data.draw(st.integers(0, len(orgs) - 1))
    permutation = data.draw(st.permutations(rows))
    with TemporaryDirectory() as directory:
        path = Path(directory)
        overlay = [{**orgs[dropped], "action": "drop"}]
        dataset(path, orgs, list(permutation), overlay)
        result = load_revenue(path)
        expected = {recipient_key(o): {2020: float(v)}
                    for i, (o, v) in enumerate(zip(orgs, values, strict=True)) if i != dropped}
        assert result == expected
        dataset(path, list(reversed(orgs)), list(reversed(permutation)), overlay)
        assert load_revenue(path) == expected


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
       st.sampled_from(["", "https://", "http://"]), st.booleans())
def test_website_aliases_and_missing_links_have_stable_keys(name, scheme, www):
    canonical = recipient_key({"name": name, "link": f"{name}.example"})
    link = scheme + ("www." if www else "") + f"{name}.example/"
    assert recipient_key({"name": name, "link": link}) == canonical
    missing = {"name": name, "link": ""}
    assert RecipientIndex([missing]).resolve({"name": name}) == (name, "")
    with pytest.raises(ValueError, match="duplicate recipient"):
        RecipientIndex([missing, missing])


def test_every_snapshot_recipient_has_a_unique_key_including_missing_websites():
    orgs = json.loads((ROOT / "data/yieldgiving/organisations.json").read_text())
    index = RecipientIndex(orgs)
    assert len(index.by_key) == len(orgs) == 2545
    assert sum(not o.get("link") for o in orgs) == 4
    assert len([k for k in index.by_key if k[0] == "Community Legal Services"]) == 2


# These are identity regressions, not precise monetary-outcome snapshots.
# Primary evidence/provenance for each correction is stored in match_audit.jsonl.
@pytest.mark.parametrize("name,link,ein", [
    ("Community Legal Services", "clsaz.org/", 860166615),
    ("Community Legal Services", "www.clsmf.org/", 591156260),
    ("United Way of Southwest Louisiana", "unitedwayswla.org/", 720456901),
    ("Partners In Health", "www.pih.org/", 43567502),
    ("Friends of the Children", "friendsofthechildren.org/", 931300690),
    ("Recovery Café", "recoverycafenetwork.org/", 912158547),
    ("Digital Promise", "digitalpromise.org/", 465460594),
    ("Civic Works", "civicworks.com/story/", 521925614),
    ("The Wildflower Foundation", "wildflowerschools.org/", 812826681),
    ("Community Vision", "communityvisionca.org/", 943032394),
    ("CommunityWorks", "communityworkscarolina.org/", 260421563),
    ("Sunflower Foundation", "www.sunflowerfoundation.org", 481241590),
    ("Room to Grow", "www.roomtogrow.org/", 134012096),
    ("Community Works", "communityworkswest.org/", 205278030),
    ("Chinese Community Center", "ccchouston.org", 760067885),
    ("Voices of Hope", "voicesofhopelex.org/", 810821411),
    ("Shine Together", "shinetogether.org", 450702884),
    ("Journey Home", "journeyhomect.org", 800143570),
    ("Neighbors Together", "www.neighborstogether.org", 112632109),
    ("JustCause", "www.justcauseny.org", 222462905),
    ("Abriendo Puertas/Opening Doors", "ap-od.org/", None),
    ("Junior Achievement of the Michigan Great Lakes", "michigangreatlakes.ja.org/", 381557861),
    ("Mercy Housing", "www.mercyhousing.org/", 470646706),
    ("Invest Detroit", "www.InvestDetroit.com", 271927369),
])
def test_corrected_recipient_eins(name, link, ein):
    key = recipient_key({"name": name, "link": link})
    assert load_matches()[key]["ein"] == ein


def test_http_errors_do_not_become_no_candidate_results(monkeypatch):
    error = HTTPError("https://invalid.example", 429, "rate limited", {}, None)

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(fetch, "urlopen", fail)
    with pytest.raises(HTTPError):
        fetch.best_match("Some recipient")


def test_failed_detail_fetch_leaves_recipient_unfetched(tmp_path, monkeypatch):
    org = {"name": "Recipient", "link": "recipient.example"}
    (tmp_path / "organisations.json").write_text(json.dumps([org]))
    monkeypatch.setattr(fetch, "DATA", tmp_path)
    monkeypatch.setattr(fetch, "OUT", tmp_path / "raw.jsonl")
    monkeypatch.setattr(fetch, "best_match", lambda _: (123456789, "Recipient", 1.0))

    def fail(_):
        raise HTTPError("https://invalid.example", 503, "unavailable", {}, None)

    monkeypatch.setattr(fetch, "fetch_revenue", fail)
    with pytest.raises(HTTPError):
        fetch.main()
    assert fetch.OUT.read_text() == ""


def test_fetch_resume_does_not_skip_a_namesake(tmp_path, monkeypatch):
    orgs = [{"name": "Shared", "link": "a.example"},
            {"name": "Shared", "link": "b.example"}]
    dataset(tmp_path, orgs, [raw(orgs[0])])
    monkeypatch.setattr(fetch, "DATA", tmp_path)
    monkeypatch.setattr(fetch, "OUT", tmp_path / "propublica_revenue.jsonl")
    monkeypatch.setattr(fetch, "best_match", lambda _: (987654321, "Shared", 1.0))
    monkeypatch.setattr(fetch, "fetch_revenue", lambda _: {"2020": 99})
    fetch.main()
    rows = [json.loads(line) for line in fetch.OUT.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[1]["link"] == "b.example"
    assert rows[1]["ein"] == 987654321


def test_full_audit_includes_exact_names_and_preserves_all_verdict_evidence(tmp_path, monkeypatch):
    orgs = [{"name": "Same", "link": "one.example"},
            {"name": "Same", "link": "two.example"}]
    correction = {**orgs[0], "action": "replace", "ein": 987654321,
                  "revenue_by_year": {"2020": 100}, "source_url": "https://one.example/990"}
    dataset(tmp_path, orgs, [raw(o) for o in orgs], [correction])
    monkeypatch.setattr(audit, "DATA", tmp_path)
    workdir = tmp_path / "audit"
    audit.build(workdir)
    batch = workdir / "batch_00"
    inputs = json.loads((batch / "items.json").read_text())
    assert {recipient_key(x) for x in inputs} == {recipient_key(o) for o in orgs}
    verdicts = [
        {**orgs[0], "verdict": "CORRECT", "ein": 987654321,
         "source_url": "https://one.example/official", "confidence": "high"},
        {**orgs[1], "verdict": "NO_990", "ein": None,
         "source_url": "https://two.example/sponsor", "confidence": "high"},
    ]
    write_rows(batch / "verdicts.jsonl", verdicts)
    audit.apply(workdir)
    ledger = [json.loads(s) for s in (tmp_path / "match_verdicts.jsonl").read_text().splitlines()]
    assert len(ledger) == 2
    assert all(v["source_url"] and v["confidence"] == "high" for v in ledger)
    matches = load_matches(tmp_path)
    assert matches[recipient_key(orgs[0])]["ein"] == 987654321
    assert matches[recipient_key(orgs[0])]["source_url"] == correction["source_url"]
    assert matches[recipient_key(orgs[1])]["ein"] is None


def test_missing_duplicate_and_stale_audit_verdicts_fail(tmp_path, monkeypatch):
    org = {"name": "Recipient", "link": "recipient.example"}
    dataset(tmp_path, [org], [raw(org)])
    monkeypatch.setattr(audit, "DATA", tmp_path)
    workdir = tmp_path / "audit"
    audit.build(workdir)
    batch = workdir / "batch_00"
    verdict = {**org, "verdict": "CORRECT", "ein": 123456789,
               "source_url": "https://recipient.example/990", "confidence": "high"}
    write_rows(batch / "verdicts.jsonl", [])
    with pytest.raises(ValueError, match="exactly cover"):
        audit.apply(workdir)
    write_rows(batch / "verdicts.jsonl", [verdict, verdict])
    with pytest.raises(ValueError, match="duplicate"):
        audit.apply(workdir)
    write_rows(batch / "verdicts.jsonl", [verdict])
    write_rows(tmp_path / "propublica_revenue.jsonl", [raw(org, ein=987654321)])
    with pytest.raises(ValueError, match="changed since audit"):
        audit.apply(workdir)


def test_failed_audit_replacement_keeps_previous_overlay(tmp_path, monkeypatch):
    org = {"name": "Recipient", "link": "recipient.example"}
    dataset(tmp_path, [org], [raw(org)])
    monkeypatch.setattr(audit, "DATA", tmp_path)
    workdir = tmp_path / "audit"
    audit.build(workdir)
    write_rows(workdir / "batch_00/verdicts.jsonl", [
        {**org, "verdict": "FOUND", "ein": 987654321,
         "source_url": "https://recipient.example/990", "confidence": "high"},
    ])

    def fail(_):
        raise HTTPError("https://invalid.example", 429, "rate limited", {}, None)

    monkeypatch.setattr(audit, "fetch_revenue", fail)
    previous = (tmp_path / "match_audit.jsonl").read_bytes()
    with pytest.raises(HTTPError):
        audit.apply(workdir)
    assert (tmp_path / "match_audit.jsonl").read_bytes() == previous
    assert not (tmp_path / "match_verdicts.jsonl").exists()


@pytest.mark.parametrize("source,confidence", [(None, "high"), ("not a URL", "high"),
                                              ("https://recipient.example", None)])
def test_audit_requires_source_and_confidence(tmp_path, monkeypatch, source, confidence):
    org = {"name": "Recipient", "link": "recipient.example"}
    dataset(tmp_path, [org], [raw(org)])
    monkeypatch.setattr(audit, "DATA", tmp_path)
    workdir = tmp_path / "audit"
    audit.build(workdir)
    write_rows(workdir / "batch_00/verdicts.jsonl", [
        {**org, "verdict": "CORRECT", "ein": 123456789,
         "source_url": source, "confidence": confidence},
    ])
    with pytest.raises(ValueError, match="source URL|confidence"):
        audit.apply(workdir)
    assert not (tmp_path / "match_verdicts.jsonl").exists()


def test_audit_cannot_silently_omit_a_batch(tmp_path, monkeypatch):
    orgs = [{"name": "One", "link": "one.example"},
            {"name": "Two", "link": "two.example"}]
    dataset(tmp_path, orgs, [raw(o) for o in orgs])
    monkeypatch.setattr(audit, "DATA", tmp_path)
    monkeypatch.setattr(audit, "BATCH_SIZE", 1)
    workdir = tmp_path / "audit"
    audit.build(workdir)
    write_rows(workdir / "batch_00/verdicts.jsonl", [
        {**orgs[0], "verdict": "CORRECT", "ein": 123456789,
         "source_url": "https://one.example/990", "confidence": "high"},
    ])
    (workdir / "batch_01").rename(workdir / "omitted")
    with pytest.raises(ValueError, match="cover every recipient"):
        audit.apply(workdir)


def test_incomplete_fetch_cannot_silently_feed_model_or_audit(tmp_path):
    orgs = [{"name": "One", "link": "one.example"},
            {"name": "Two", "link": "two.example"}]
    dataset(tmp_path, orgs, [raw(orgs[0])])
    with pytest.raises(ValueError, match="raw matches must cover every recipient"):
        load_revenue(tmp_path)


def test_malformed_search_response_is_not_a_cached_nonmatch(monkeypatch):
    monkeypatch.setattr(fetch, "get", lambda _: {"error": "backend unavailable"})
    with pytest.raises(ValueError, match="lacks organization results"):
        fetch.best_match("Recipient")


def test_incomplete_raw_snapshot_creates_no_audit_outputs(tmp_path, monkeypatch):
    orgs = [{"name": "One", "link": "one.example"},
            {"name": "Two", "link": "two.example"}]
    dataset(tmp_path, orgs, [raw(orgs[0])])
    monkeypatch.setattr(audit, "DATA", tmp_path)
    workdir = tmp_path / "audit"
    before = (tmp_path / "match_audit.jsonl").read_bytes()
    for operation in (audit.build, audit.apply):
        with pytest.raises(ValueError, match="raw matches must cover every recipient"):
            operation(workdir)
        assert not workdir.exists()
        assert not (tmp_path / "match_verdicts.jsonl").exists()
        assert (tmp_path / "match_audit.jsonl").read_bytes() == before


@pytest.mark.parametrize("changed", [
    "organisations.json", "propublica_revenue.jsonl", "match_audit.jsonl",
    "match_verdicts.jsonl", "audit/batch_00/items.json", "audit/batch_00/verdicts.jsonl",
])
def test_audit_refuses_to_overwrite_inputs_edited_during_fetch(tmp_path, monkeypatch, changed):
    org = {"name": "Recipient", "link": "recipient.example"}
    dataset(tmp_path, [org], [raw(org)])
    monkeypatch.setattr(audit, "DATA", tmp_path)
    workdir = tmp_path / "audit"
    audit.build(workdir)
    write_rows(workdir / "batch_00/verdicts.jsonl", [
        {**org, "verdict": "FOUND", "ein": 987654321,
         "source_url": "https://recipient.example/990", "confidence": "high"},
    ])
    changed_path = tmp_path / changed
    before_overlay = (tmp_path / "match_audit.jsonl").read_bytes()
    edited = (changed_path.read_bytes() if changed_path.exists() else b"external edit") + b"\n"

    def concurrent_edit(_):
        changed_path.write_bytes(edited)
        return {"2020": 100}

    monkeypatch.setattr(audit, "fetch_revenue", concurrent_edit)
    with pytest.raises(ValueError, match="inputs changed during apply"):
        audit.apply(workdir)
    assert changed_path.read_bytes() == edited
    if changed != "match_audit.jsonl":
        assert (tmp_path / "match_audit.jsonl").read_bytes() == before_overlay
    if changed != "match_verdicts.jsonl":
        assert not (tmp_path / "match_verdicts.jsonl").exists()

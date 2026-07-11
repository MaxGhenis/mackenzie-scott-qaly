# Yield Giving gift database snapshot

Provenance for the files in this directory. They are the **data basis for the
model's dollar-allocation shares** (`allocation_share` in
`data/parameters.yaml`), derived by `src/msqaly/allocation.py` and enforced by
`tests/test_allocation.py`.

## organisations.json

Verbatim snapshot of <https://yieldgiving.com/organisations.json> — the JSON
the [Yield Giving gifts database](https://yieldgiving.com/gifts) loads
client-side — retrieved **2026-07-11**. 2,545 organizations; 2,711 gifts.
Fields per organization: `name`, `link`, `mission`, `giftAreas` (org-reported
focus-area codes), `gifts` (list of `{amount, year}`; `amount: 0` means the
gift's dollar amount is undisclosed), `locations`, `essays`.

Coverage: 2,035 gifts carry disclosed amounts totaling **$17.46B nominal —
about two-thirds of the $26.39B disclosed lifetime total**. Coverage varies by
year (2024: ~74% of that year's dollars; 2021: ~35%). Every disclosed dollar
carries at least one focus-area tag.

## area_map.json

The focus-area taxonomy (10 groups, 53 leaf areas), parsed from the
`data-checkbox-*` attributes of the gifts page's "Focus area" filter UI
(same retrieval date). Maps each numeric `giftAreas` code to its org-facing
label and group.

## propublica_revenue.jsonl

One record per organization: the name→EIN match against ProPublica's
[Nonprofit Explorer API](https://projects.propublica.org/nonprofits/api/)
(difflib similarity ≥ 0.87; fetched by `scripts/fetch_propublica.py`,
2026-07-11) and every filing's total revenue by tax year. 1,462 of 2,545
organizations matched; the rest are mostly non-US recipients with no 990.

## match_audit.jsonl

LLM audit overlay (gpt-5.6-terra via Codex CLI, 2026-07-11) of the fuzzy
matches: 827 audited items (similarity < 0.95, plausible rejects, and the
highest-revenue undisclosed-gift orgs) verified against the live API.
Verdicts: 518 correct, 236 newly-found EINs (legal-name/DBA mismatches), 73
confirmed non-filers, 0 false positives. `msqaly.allocation.load_revenue`
applies these on top of the raw fetch. Built/applied by
`scripts/audit_matches.py`.

## leaf_to_archetype.yaml

The judgment layer: maps each of the 53 Yield Giving leaf areas to one of the
model's 13 intervention archetypes. Every rule is commented inline. To change
the allocation, edit that mapping (or refresh the snapshot), run
`uv run python -m msqaly.allocation`, and copy the printed shares into
`data/parameters.yaml` — the sync test fails until they match.

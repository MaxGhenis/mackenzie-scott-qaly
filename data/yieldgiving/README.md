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

Geography: weighting each organization's disclosed dollars by
`nonus_fraction(locations)` (share of reported service locations outside the
US; a bare `global` counts as fully non-US under this raw rule), **$3.57B of the $17.46B disclosed
— 20.4% — goes to organizations serving outside the US**, led by environment
(~$0.64B), health (~$0.61B), and funding intermediaries (~$0.54B). The model
prices only the health-and-development slice by geography (the
`global_health` routing, ~4.8% of the full ledger under the audited v1.1 allocation); other categories keep
their US-study anchors regardless of delivery location. Applying the audited
us_share overlay (geo_audit/) instead of the raw global-counts-as-abroad rule
gives ~$3.34B / ~19.1% for the same disclosed-dollar calculation.

## area_map.json

The focus-area taxonomy (10 groups, 53 leaf areas), parsed from the
`data-checkbox-*` attributes of the gifts page's "Focus area" filter UI
(same retrieval date). Maps each numeric `giftAreas` code to its org-facing
label and group.

## propublica_revenue.jsonl

The raw fetch records name-to-EIN candidates from ProPublica's
[Nonprofit Explorer API](https://projects.propublica.org/nonprofits/api/) and
positive total revenue by tax year. The July 11, 2026 snapshot accepts
1,462 recipient rows at a difflib similarity threshold of 0.87
([raw records](propublica_revenue.jsonl), [fetch script](../../scripts/fetch_propublica.py)).
Name similarity does not establish identity. Unmatched records can reflect
non-US entities, sponsored projects, or unresolved U.S. legal names.

Two recipients share the name Community Legal Services. The raw rows retain
the original fetch's Arizona EIN, but each now carries its snapshot `link`:
`clsaz.org/` for Arizona and `www.clsmf.org/` for Florida. The overlay supplies
Florida's corrected EIN. Matching uses the recipient's name and link;
[the Yield Giving snapshot](organisations.json) supplies both fields.

## match_audit.jsonl

[The overlay](match_audit.jsonl) currently contains 258 replacements and 13
drops. `msqaly.allocation.load_revenue` applies the overlay before calibration
and imputation ([implementation](../../src/msqaly/allocation.py)).

The July audit retained effectful changes and omitted confirmation-only
verdicts. Those rows cannot establish the original audit's overall error
rate or a count of confirmed non-filers. The November 16, 2026 corrections
replace 23 histories and drop the unrelated Abriendo Puertas match. Each
correction records the recipient link, original EIN, identity evidence,
revenue source, retrieval date, and confidence
([correction records](match_audit.jsonl)).

The corrected histories use ProPublica's `tax_prd_yr` and positive
`totrevenue` values through tax year 2024. For duplicate filings within a
year, the extraction keeps the largest positive total revenue, matching the
[original fetch convention](../../scripts/fetch_propublica.py). The
[refresh script](../../scripts/refresh_match_corrections.py) verifies the
returned EIN and aborts if a request fails or an empty response would erase
existing revenue history. Run the script with either mode below.

```bash
uv run python scripts/refresh_match_corrections.py          # preview
uv run python scripts/refresh_match_corrections.py --write  # update histories
```

These corrections identify organizations for revenue-based size proxies;
they do not identify the legal payee of each Scott gift. Junior Achievement
of the Michigan Great Lakes uses its operating entity, Mercy Housing uses
its parent, and Invest Detroit uses its charitable foundation. Their
records cite the organizations' own financial reports or donation
instructions; the historical gift payees remain unverified
([source-linked records](match_audit.jsonl)).

NACA retains its related foundation's revenue as a school-size proxy;
that choice does not establish that the foundation's revenue measures the
school's full operating size
([school](https://www.nacaschool.org/),
[foundation filer](https://projects.propublica.org/nonprofits/organizations/272193660)).
AP-OD identifies itself as a Tides Center fiscally sponsored project, so the
overlay drops the unrelated Connecticut filer and does not substitute
Tides-wide revenue for project revenue
([AP-OD donation instructions](https://ap-od.org/donate/)).

## Matching and imputation diagnostics

Run `uv run python -m msqaly.diagnostics` to print current sample-flow,
filing-age, and fallback-weight diagnostics. Add `--write` to export the
[compact web summary](../../web/matching_diagnostics.json) and
[gift-level CSV](../../results/gift_ledger.csv). The
[exporter](../../src/msqaly/diagnostics.py) shares the allocation pipeline's
revenue-year selection and window-weight calculation.

The CSV distinguishes disclosed amounts from model-imputed amounts and
reports each gift's effective EIN, selected revenue year, filing lag,
calibration inclusion, and reason for any median-weight fallback. Dollar
amounts remain nominal across the 2019–2025 gift window. An imputed amount
does not disclose the gift's actual size.

Raw candidate names, accepted EINs, and name-similarity scores describe the
original name search. Separate columns identify the effective EIN and legal
name after corrections. Verification-standing fields distinguish source-linked
corrections from legacy audit notes, automatic name matches, and unmatched
recipients; a high similarity score does not establish identity.

Exports round imputed amounts to cents with largest-remainder rounding
within each window, so CSV amounts sum to that window's residual. Each
exported imputation differs from its internal amount by less than one cent;
disclosed amounts retain their source values. Summary fractions and fit
statistics use 12 decimal places, and CSV weights use 12 significant digits.
The exporter stages both files before replacing either output and rejects
non-finite JSON values.

The summary reports fallback shares by gift count and by imputed dollars,
plus residual accounting for each imputation window. The
[diagnostic tests](../../tests/test_diagnostics.py) reconcile gift-level
amounts to allocation totals and check that selected revenue years precede
gift years. They also enforce residual conservation and invariance to a
common scaling of all revenue inputs within a window.

## leaf_to_archetype.yaml

The judgment layer: maps each of the 53 Yield Giving leaf areas to one of the
model's intervention archetypes. Every rule is commented inline. To change
the allocation, edit that mapping (or refresh the snapshot), run
`uv run python -m msqaly.allocation`, and copy the printed shares into
`data/parameters.yaml` — the sync test fails until they match.

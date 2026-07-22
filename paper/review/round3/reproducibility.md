# Reproducibility referee report — round 3

| Round-2 finding | Status | Verification against the fresh revision |
|---:|---|---|
| 3 | **PARTIALLY RESOLVED** | `paper/index.qmd:305` now correctly discloses that the abstract is hand-typed, and the source, HTML source copy, PDF text, and supplied render are synchronized. The broader claim that the *body* interpolates its model-derived numbers is still false: examples of typed model outputs include the 1.3–10% allocation interval (`paper/index.qmd:142`), the pre-audit outputs (`:288`), the historical model medians (`:296-299`), and the 45-fold conclusion figure (`:315`). `README.md:3` and `paper/README.md:3-6` still make the stronger false “every number” claim. Narrow these statements to the current headline outputs, or interpolate/test the remaining values. The deferred render-CI guard remains a reasonable working-paper deferral. |
| 4 | **RESOLVED** | The corrected `uv sync --all-groups --extra dev` recipe works in a fresh clone. It installed the declared environment, and the documented `uv run python -m pytest` invocation completed with **64 passed**. The previously missing-`pytest` failure is fixed. |
| 5 | **PARTIALLY RESOLVED** | `data/yieldgiving/README.md:50-55` now explicitly says that only 248 effectful rows (236 replacements and 12 drops) are committed and that the remaining 579 verdicts are not committed. However, `README.md:88-91` still links the 248-row file directly beside the full 827-item verdict counts without that qualification, so the most visible repository description still implies that the linked file supports all counts. Add the same one-clause qualification there. Deferring publication of the 579 non-effectful verdict records remains reasonable for this working paper. |

## New findings

None. As a regression check, `paper/index.qmd` is byte-identical to `docs/index.qmd`, a fresh `pdftotext docs/index.pdf -` is byte-identical to `paper/review/rendered.txt`, and the full test suite passes in a clean clone.

RECOMMENDATION: Minor revisions

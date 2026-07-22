# Reproducibility referee report — round 2

I checked the revised source, canonical render, generated artifacts, documentation, and tests directly. `paper/index.qmd` is byte-identical to the rendered source copy in `docs/index.qmd`; a fresh `pdftotext docs/index.pdf -` is byte-identical to `paper/review/rendered.txt`; the full test suite passes; and fresh parameter, allocation-version, and geography exports leave their committed artifacts unchanged.

## Resolution of round-1 findings

| Round-1 finding | Status | Note |
|---:|---|---|
| 1 | **RESOLVED** | The revised manuscript source, committed PDF, HTML source copy, and canonical text extraction are synchronized. The requested CI render guard remains absent, but the actual source/render divergence identified in round 1 is gone and the guard is addressed separately in finding 3. |
| 2 | **RESOLVED** | The paper dependencies are declared in the committed lockfile, the custom-kernel installation is documented, and `paper/README.md` states the Quarto and TeX requirements plus exact root-level render commands; installing the kernel recreates the otherwise machine-specific absolute interpreter path. |
| 3 | **PARTIALLY RESOLVED** | The sync claim is correctly narrowed to parameters, allocation shares, and geography exports, and those guards pass. Deferring render CI is defensible for an SSRN working paper, but the replacement claim that all model-derived manuscript numbers are interpolated is false: the abstract alone hand-types 202,000, 94,000–419,000, $150,000, 4.9, 4.8%, 69%, 0.41, ~9,000, ~415,000, and 45× (`paper/index.qmd:18`), with further typed model outputs later. Narrow the claim again or interpolate those values. |
| 4 | **PARTIALLY RESOLVED** | An ordered stranger-facing recipe now exists, but it is not executable as written in a clean checkout: `uv sync --all-groups` installs the paper group but not the `dev` extra, so the documented `uv run python -m pytest` step fails with `No module named pytest`. Use `uv sync --all-groups --extra dev` (or move dev tools into a dependency group), and preferably end the recipe with an explicit clean-tree check. |
| 5 | **PARTIALLY RESOLVED** | The manuscript now accurately says that the 990 audit ships as the applied overlay, and deferring the complete 827-verdict dataset is defensible for a working paper because the computational corrections are committed. The repository documentation is still misleading, however: `README.md:90-91` links the 248-row `match_audit.jsonl` beside counts for all 827 judgments, and `data/yieldgiving/README.md:48-56` describes that file itself as the 827-item audit. State explicitly that only 248 effectful rows are committed and that the other 579 verdict records are unavailable. |

## New findings from the regression pass

None beyond the incomplete resolutions above.

RECOMMENDATION: Minor revisions

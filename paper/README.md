# Working paper

Quarto manuscript. The body interpolates model-derived figures at
render time from the committed artifacts (`results/summary.json`, `web/geo.json`,
`web/matching_diagnostics.json`, the allocation exports, and a live
`derive_shares()` call). The abstract
rounds figures from the same regenerated outputs; check those figures after
changing the model. Historical correction figures retain their published values.

## Render

From the repository root:

```bash
uv sync --all-groups --extra dev
uv run python -m ipykernel install --user --name msqaly-paper
cd paper && QUARTO_PYTHON="$(cd .. && pwd)/.venv/bin/python" quarto render
```

Requires [Quarto](https://quarto.org) ≥ 1.4 (built with 1.9) and, for the PDF,
a TeX distribution with `tgpagella` and `helvet` (`quarto install tinytex`
suffices). Quarto writes the GitHub Pages webview and `index.pdf` to `docs/`.
For the GitHub Pages mirror, rewrite figure URLs from `../results/` to
`results/` in `docs/index.html`: Quarto copies figures into `docs/results/`
but retains source-relative URLs. Quarto PDF renders can link to either
`index-preview.html` or `index.qmd.html` for the source notebook. The
project copies a redirect for the latter into `docs/`.

Regenerating the inputs, in order, when the model changes:

```bash
uv run msqaly --write            # results/
uv run msqaly-export-params      # web/params.json
uv run python -m msqaly.exportversions   # web/allocation_v10.json, _v11.json, _v12.json
uv run python -m msqaly.geo      # web/geo.json
uv run python -m msqaly.diagnostics --write  # web/matching_diagnostics.json + results/gift_ledger.csv
uv run python -m pytest          # sync guards
```

## Sync the website

After regenerating the inputs and rendering the paper, run these commands
from a checkout of the website repository:

```bash
bun scripts/sync-mackenzie-qaly.mjs --source /path/to/mackenzie-scott-qaly
bun scripts/sync-mackenzie-qaly.mjs --source /path/to/mackenzie-scott-qaly --check
```

The full sync copies the model JSON exports, matching diagnostics, gift ledger,
paper fragment, PDF and figures. It also rewrites figure URLs for the website's
paper view. `--check` reports drift without changing files. The canonical
webview occupies the working-paper tab at `/mackenzie-scott-qaly/paper/`.

To sync the paper alone, use `scripts/sync-mackenzie-paper.mjs` with the same
`--source` and `--check` options.

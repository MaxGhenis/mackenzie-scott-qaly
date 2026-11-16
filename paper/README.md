# Working paper

Quarto manuscript. The body interpolates model-derived figures at
render time from the frozen artifacts (`results/summary.json`, `web/geo.json`,
the allocation exports, and a live `derive_shares()` call). The abstract
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
suffices). Output lands in `../docs/` (the GitHub Pages webview + `index.pdf`). Two
post-render steps: rewrite `../results/` to `results/` in `docs/index.html`
(quarto copies the figures into `docs/results/` but keeps the source-relative
src), then run `node scripts/sync-mackenzie-paper.mjs` in the site repo
(~/maxghenis.com) — it extracts the paper body into a fragment the site
renders inside its own page frame at /mackenzie-scott-qaly/paper/, copies
the figure assets, and refreshes the PDF. The canonical webview is a tab
of the interactive page.

Regenerating the inputs, in order, when the model changes:

```bash
uv run msqaly --write            # results/
uv run msqaly-export-params      # web/params.json
uv run python -m msqaly.exportversions   # web/allocation_v10.json, _v11.json, _v12.json
uv run python -m msqaly.geo      # web/geo.json
uv run python -m pytest          # sync guards
```

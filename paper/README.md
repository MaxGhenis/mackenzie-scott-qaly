# Working paper

Quarto manuscript. Every model-derived number in the prose is interpolated at
render time from the frozen artifacts (`results/summary.json`, `web/geo.json`,
the allocation exports, and a live `derive_shares()` call); hand-typed
constants are limited to externally sourced, cited figures.

## Render

From the repository root:

```bash
uv sync --all-groups --extra dev
uv run python -m ipykernel install --user --name msqaly-paper
cd paper && QUARTO_PYTHON="$(cd .. && pwd)/.venv/bin/python" quarto render
```

Requires [Quarto](https://quarto.org) ≥ 1.4 (built with 1.9) and, for the PDF,
a TeX distribution with `tgpagella` and `helvet` (`quarto install tinytex`
suffices). Output lands in `../docs/` (the GitHub Pages webview + `index.pdf`).

Regenerating the inputs, in order, when the model changes:

```bash
uv run msqaly --write            # results/
uv run msqaly-export-params      # web/params.json
uv run python -m msqaly.exportversions   # web/allocation_v10.json, _v11.json
uv run python -m msqaly.geo      # web/geo.json
uv run python -m pytest          # sync guards
```

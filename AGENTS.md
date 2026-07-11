# Agent contract — mackenzie-scott-qaly

Rules for any coding agent (Claude Code, Codex, or other) working in this repo.
This exists because an agent once hand-edited a *generated* copy of the
parameters and the repos silently diverged.

## Source of truth

- **`data/parameters.yaml` is the single source of truth** for every parameter,
  unit, and source citation. All parameter changes happen there and only there.
- Giving is stored as nominal `meta.giving_tranches`; `meta.total_giving_usd`
  (2026 dollars) is DERIVED by `load_params` and appears in the export — never
  write a stored total.
- `web/params.json` is **generated**. Never hand-edit it. Regenerate with
  `uv run msqaly-export-params`. CI fails if it differs from a fresh export.
- The website copy at `~/maxghenis.com/src/data/mackenzie-qaly-params.json` is a
  **byte-copy of `web/params.json`**. Never hand-edit it either. Flow:
  edit `parameters.yaml` → `uv run msqaly-export-params` → `cp web/params.json`
  to the site → commit both repos.
- The TypeScript port (`~/maxghenis.com/src/lib/mackenzie-qaly.ts`) mirrors
  `src/msqaly/model.py`. A change to the model's math must land in both, with
  the site's vitest suite asserting distributional agreement.

## Typed units and dollar vintages (enforced)

- Every sampled spec in `parameters.yaml` declares `unit`; every
  dollar-denominated spec also declares `dollars_base_year`, which must equal
  `meta.base_year`. `load_params` validates on every load (`src/msqaly/validate.py`).
- Pasting a figure in its publication-year dollars is a **validation error** by
  design: inflate it (e.g. FRED CPI-U), document the conversion in `source`,
  then set `dollars_base_year` to the base year.
- Never resolve a unit mismatch by relabeling the slot — convert the figure and
  show the arithmetic in `source`.

## Citations

- Every quantitative claim in `parameters.yaml`, `SOURCES.md`, and the README
  carries an **inline link**. Write `source:` strings from a fetched source,
  never from recall — this repo has shipped misattributed citations before.
- Model outputs (medians, multiples) are *not* citable facts; label them as
  model outputs.

## Checks before any commit

```bash
uv run ruff check .          # lint
uv run pytest                # full suite, includes schema validation
uv run msqaly-export-params  # then commit web/params.json if it changed
```

- `uv run msqaly` only prints; `uv run msqaly --write` regenerates the committed
  `results/` artifacts and the README results block. Rerun it after any change
  that moves the numbers, and update prose that quotes them.

## Git

- Commit to `main`; never rewrite or force-push published history.
- End commit messages with a `Co-Authored-By:` trailer identifying the agent.

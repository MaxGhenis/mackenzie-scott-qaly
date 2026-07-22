ROLE: Reproducibility referee. VERIFY, don't just read.

PAPER: paper/review/rendered.txt + paper/index.qmd. REPO: current directory.

DO: (a) run .venv/bin/python -m pytest tests/ and report the outcome; (b) identify which tests are sync-guards (params/allocation/geo/version exports vs fresh derivations) and confirm they pass; (c) spot-check at least 8 numbers from the rendered paper against results/summary.json, web/geo.json, and .venv/bin/python -c "from msqaly.allocation import derive_shares; ..." diagnostics; (d) check render reproducibility: paper/_quarto.yml requires a jupyter kernel — is the render command + kernel setup documented anywhere a stranger would find (README? paper/?); are jupyter/matplotlib/pandas/tabulate declared as deps anywhere (pyproject)? (e) confirm data availability in-repo: yieldgiving snapshot, propublica_revenue.jsonl, match_audit.jsonl, geo_audit/geo_audit.jsonl; (f) git tags v2026.07.20 and v2026.07.22 exist and match the paper's description (git tag -n; git show <tag> --stat | head); (g) list everything a replicator would trip on.

WRITE your report to paper/review/round1/reproducibility.md: one-paragraph assessment; numbered findings each with SEVERITY (CRITICAL/MAJOR/MINOR), LOCATION, problem, concrete fix; end with "RECOMMENDATION: Accept|Minor revisions|Major revisions|Reject".

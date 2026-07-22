#!/bin/zsh
set -u
ID="$1"
DIR="$HOME/mackenzie-scott-qaly"
OUT="$DIR/paper/review/round3"
[ -s "$OUT/$ID.md" ] && exit 0
cd "$DIR"
PROMPT="ROUND 3 (final confirmation) of a referee cycle. You are the $ID referee. Your round-2 report: paper/review/round2/$ID.md (for 'redteam' the file is redteam.md). The manuscript was revised again; fresh render: paper/review/rendered.txt; source: paper/index.qmd; bibliography: paper/references.bib.

TASK: verify each item you left PARTIALLY RESOLVED or flagged as NEW in round 2 against the fresh text. The author's standing adjudications (declines/deferrals documented in paper/review/round1/response.md) hold unless factually wrong — judge remaining items by the standard of a good SSRN working paper, not a journal publication. One brief regression glance for anything the newest edits broke.

WRITE to paper/review/round3/$ID.md: a short resolution table for your outstanding items, any NEW findings (SEVERITY/LOCATION/fix), and end with 'RECOMMENDATION: Accept|Minor revisions|Major revisions|Reject'. Accept is appropriate when remaining concerns are documented limitations or reasonable working-paper deferrals."
codex exec -m gpt-5.6-sol -c model_reasoning_effort=high --sandbox danger-full-access --skip-git-repo-check "$PROMPT" < /dev/null > "$DIR/paper/review/sol/$ID.round3.log" 2>&1 || echo "FAIL $ID" >&2

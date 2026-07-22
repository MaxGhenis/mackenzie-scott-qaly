#!/bin/zsh
set -u
ID="$1"
DIR="$HOME/mackenzie-scott-qaly"
OUT="$DIR/paper/review/round4"
[ -s "$OUT/$ID.md" ] && exit 0
cd "$DIR"
PROMPT="ROUND 4 (closing vote) of a referee cycle. You are the $ID referee; your round-3 report is paper/review/round3/$ID.md. The single remaining wording tail (limitations 'high-income-region dollars') has been fixed; fresh render: paper/review/rendered.txt.

TASK: confirm the fix and cast a closing vote at working-paper standard. Documented limitations and reasonable SSRN-draft deferrals are not blockers. WRITE to paper/review/round4/$ID.md: one short paragraph and 'RECOMMENDATION: Accept' — or, if a concrete blocker remains, name it with SEVERITY/LOCATION/fix and vote accordingly."
codex exec -m gpt-5.6-sol -c model_reasoning_effort=medium --sandbox danger-full-access --skip-git-repo-check "$PROMPT" < /dev/null > "$DIR/paper/review/sol/$ID.round4.log" 2>&1 || echo "FAIL $ID" >&2

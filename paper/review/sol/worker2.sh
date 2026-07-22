#!/bin/zsh
set -u
ID="$1"
DIR="$HOME/mackenzie-scott-qaly"
OUT="$DIR/paper/review/round2"
[ -s "$OUT/$ID.md" ] && exit 0
cd "$DIR"
PROMPT="ROUND 2 of a referee cycle. You are the $ID referee. Round-1 reports live in paper/review/round1/ (yours: $ID.md — for 'redteam' read red-team.md; the author's adjudication: response.md). The manuscript has been revised; the fresh render is paper/review/rendered.txt (canonical) with source paper/index.qmd, bibliography paper/references.bib, repo artifacts unchanged paths.

TASK: (1) For EACH of your round-1 findings, verify against the fresh render/source/repo whether it is RESOLVED, PARTIALLY RESOLVED, or UNRESOLVED — checking the actual text, not the response document's claims. Where the response says 'declined' or 'deferred', judge whether the reason is defensible for an SSRN working paper. (2) Do one fresh regression pass over the revised text for NEW problems introduced by the edits (your seat's lens only). Keep severity honest: do not re-litigate adjudicated declines unless the reason is factually wrong.

WRITE your report to paper/review/round2/$ID.md: a finding-by-finding resolution table (round-1 number, status, one-line note); any NEW findings with SEVERITY/LOCATION/problem/fix; end with 'RECOMMENDATION: Accept|Minor revisions|Major revisions|Reject'."
codex exec -m gpt-5.6-sol -c model_reasoning_effort=high --sandbox danger-full-access --skip-git-repo-check "$PROMPT" < /dev/null > "$DIR/paper/review/sol/$ID.round2.log" 2>&1 || echo "FAIL $ID" >&2

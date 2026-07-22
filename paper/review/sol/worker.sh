#!/bin/zsh
set -u
ID="$1"
DIR="$HOME/mackenzie-scott-qaly"
OUT="$DIR/paper/review/round1"
[ -s "$OUT/$ID.md" ] && exit 0
cd "$DIR"
codex exec -m gpt-5.6-sol -c model_reasoning_effort=high --sandbox danger-full-access --skip-git-repo-check "$(cat "$DIR/paper/review/sol/$ID.md")

Work from the repository root ($DIR). Write the report file exactly where instructed." < /dev/null > "$DIR/paper/review/sol/$ID.log" 2>&1 || echo "FAIL $ID" >&2

#!/bin/zsh
DIR="$HOME/mackenzie-scott-qaly/data/yieldgiving/geo_audit"
sed -n 's/.*"id": "\(g[0-9][0-9]\)".*/\1/p' "$DIR/sol_targets.jsonl" | \
  xargs -n1 -P6 env -i PATH="$HOME/.bun/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin" HOME="$HOME" TERM=xterm zsh "$DIR/worker_sol.sh"
echo "sol pass done: $(ls "$DIR/sol_raw" | grep -c '^g[0-9][0-9]\.json$') / 50"

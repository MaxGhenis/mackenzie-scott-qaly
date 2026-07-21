#!/bin/zsh
DIR="$HOME/mackenzie-scott-qaly/data/yieldgiving/geo_audit"
cut -c1-9999 "$DIR/targets.jsonl" | sed -n 's/.*"id": "\(g[0-9][0-9]\)".*/\1/p' | \
  xargs -n1 -P6 env -i PATH="$HOME/.bun/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin" HOME="$HOME" TERM=xterm zsh "$DIR/worker.sh"
echo "sweep done: $(ls "$DIR/raw" | grep -c '^g[0-9][0-9]\.json$') / 50"

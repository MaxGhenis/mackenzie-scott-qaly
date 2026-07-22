#!/bin/zsh
DIR="$HOME/mackenzie-scott-qaly/paper/review/sol"
printf 'redteam\nmethodology\nreproducibility\ncitations\n' | \
  xargs -n1 -P4 env -i PATH="$HOME/.bun/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin" HOME="$HOME" TERM=xterm zsh "$DIR/worker.sh"
ls -la "$HOME/mackenzie-scott-qaly/paper/review/round1/"

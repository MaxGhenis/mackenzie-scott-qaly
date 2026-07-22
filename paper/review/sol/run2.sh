#!/bin/zsh
DIR="$HOME/mackenzie-scott-qaly/paper/review/sol"
printf 'redteam\nmethodology\nreproducibility\ncitations\nneutrality\n' | \
  xargs -n1 -P5 env -i PATH="$HOME/.bun/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin" HOME="$HOME" TERM=xterm zsh "$DIR/worker2.sh"
ls "$HOME/mackenzie-scott-qaly/paper/review/round2/"

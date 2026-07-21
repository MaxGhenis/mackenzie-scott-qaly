#!/bin/zsh
# One geo-audit task. Arg: target id. Reads targets.jsonl, writes raw/<id>.json.
# Sanitized env: launched via env -i (see run.sh) so no credential vars leak
# into codex traces.
set -u
ID="$1"
DIR="$HOME/mackenzie-scott-qaly/data/yieldgiving/geo_audit"
T=$(grep "\"id\": \"$ID\"" "$DIR/targets.jsonl")
[ -z "$T" ] && { echo "no target $ID" >&2; exit 1; }
OUT="$DIR/raw/$ID.json"
[ -s "$OUT" ] && exit 0   # resumable
PROMPT="Research task. Organization from MacKenzie Scott's gift list, which reports its service location only as 'global':

$T

Using the organization's own website, annual report, or grants/where-we-work page, determine its actual operational geography. Output ONLY a JSON object (no prose) with fields:
  id, name,
  class: one of \"global_intermediary\" (regrants/operates worldwide, no dominant region), \"regional\" (work concentrated in specific regions), \"us_inclusive_global\" (global AND materially operates or grants in the US),
  region_shares: object mapping any of [sub_saharan_africa, south_asia, east_asia_pacific, latin_america_caribbean, middle_east_north_africa, europe_central_asia, north_america_us, global_unattributable] to rough decimal shares summing to 1 (use global_unattributable for what you cannot attribute),
  us_share: decimal 0-1 (share of operations/grants in the US; 0 if none found),
  source_url: the specific page you based this on,
  confidence: high|medium|low.
Base shares on program/grant counts or spend if published; otherwise rough qualitative shares with confidence low. Do not guess a region you found no evidence for — use global_unattributable."
cd /tmp
codex exec -m gpt-5.6-terra --sandbox danger-full-access --skip-git-repo-check "$PROMPT" < /dev/null > "$OUT.tmp" 2>"$DIR/raw/$ID.err" && mv "$OUT.tmp" "$OUT" || { echo "FAIL $ID" >&2; exit 1; }

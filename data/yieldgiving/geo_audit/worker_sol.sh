#!/bin/zsh
# Sol adversarial verification of one terra geo-audit row. Arg: id.
set -u
ID="$1"
DIR="$HOME/mackenzie-scott-qaly/data/yieldgiving/geo_audit"
T=$(grep "\"id\": \"$ID\"" "$DIR/sol_targets.jsonl")
[ -z "$T" ] && { echo "no target $ID" >&2; exit 1; }
OUT="$DIR/sol_raw/$ID.json"
[ -s "$OUT" ] && exit 0
PROMPT="Adversarial verification. A prior automated review classified the operational geography of an organization from MacKenzie Scott's gift list (its service location is listed only as 'global'). Your job is to INDEPENDENTLY verify or refute that claim. Work from the organization's own current website, annual report, financials, or grants/where-we-work pages FIRST, forming your own estimate before comparing to the prior claim. Do not anchor on it.

$T

Output ONLY a JSON object:
  id, name,
  verdict: \"confirm\" (class right AND us_share within +-0.15) | \"adjust\" (right direction, magnitude off) | \"refute\" (class wrong or us_share off by >0.30),
  my_class: global_intermediary|regional|us_inclusive_global,
  my_us_share: decimal 0-1,
  my_region_shares: object over [sub_saharan_africa, south_asia, east_asia_pacific, latin_america_caribbean, middle_east_north_africa, europe_central_asia, north_america_us, global_unattributable] summing to 1,
  key_evidence_url: the strongest primary source you used,
  note: <=200 chars on any disagreement.
Use global_unattributable for what primary sources do not let you attribute; never invent regional precision."
cd /tmp
codex exec -m gpt-5.6-sol -c model_reasoning_effort=high --sandbox danger-full-access --skip-git-repo-check "$PROMPT" < /dev/null > "$OUT.tmp" 2>"$DIR/sol_raw/$ID.err" && mv "$OUT.tmp" "$OUT" || { echo "FAIL $ID" >&2; exit 1; }

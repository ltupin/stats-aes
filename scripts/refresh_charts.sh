#!/bin/bash
# Refresh market data and rebuild reports without committing or pushing.
set -uo pipefail

DIR="/Users/minux/Statistiques"
SC="$DIR/scripts"
PY="$DIR/.venv/bin/python"
cd "$SC" || exit 1

GAMES=(
  "samsho1|サムライスピリッツ ネオジオ|サムライスピリッツ"
  "samsho2|真サムライスピリッツ ネオジオ|真サムライスピリッツ"
  "aof|龍虎の拳 ネオジオ|龍虎の拳"
  "aof2|龍虎の拳2 ネオジオ|龍虎の拳2"
  "ffs|餓狼伝説スペシャル ネオジオ|餓狼伝説スペシャル"
  "ff1|餓狼伝説 ネオジオ|餓狼伝説"
  "ff2|餓狼伝説2 ネオジオ|餓狼伝説2"
  "ff3|餓狼伝説3 ネオジオ|餓狼伝説3"
  "wh2|ワールドヒーローズ2 ネオジオ|ワールドヒーローズ2"
  "kof|キングオブファイターズ ネオジオ|キングオブファイターズ"
  "rb1|リアルバウト餓狼伝説 ネオジオ|リアルバウト餓狼伝説"
  "rb2|リアルバウト餓狼伝説2 ネオジオ|リアルバウト餓狼伝説2"
  "samsho3|サムライスピリッツ斬紅郎 ネオジオ|サムライスピリッツ斬紅郎"
  "samsho4|サムライスピリッツ天草降臨 ネオジオ|サムライスピリッツ天草降臨"
)

country=$("$SC/vpn.sh" status | /usr/bin/jq -r '.countryCode // empty')
if [[ "$country" != JP ]]; then
  "$SC/vpn.sh" up || exit 1
fi

for entry in "${GAMES[@]}"; do
  IFS='|' read -r key mercari_kw yahoo_kw <<< "$entry"
  printf '\n=== %s ===\n' "$key"
  "$PY" "$SC/fetch.py" "$key" "$mercari_kw" "$yahoo_kw" --source both || exit 1
done

"$SC/vpn.sh" down || exit 1
"$PY" "$SC/ebay_fetch.py" --all --pages 2 || exit 1
"$PY" "$SC/report.py" --all || exit 1
"$PY" "$SC/build_index.py" || exit 1
"$PY" "$SC/build_global.py" || exit 1
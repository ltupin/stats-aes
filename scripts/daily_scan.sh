#!/bin/bash
# Scan quotidien autonome : eBay+Mercari (IP FR) puis Yahoo (IP JP via vpn.sh),
# régénération, push git, et récap des nouvelles ventes. Conçu pour cron/launchd.
set -uo pipefail
DIR="/Users/minux/Statistiques"
SC="$DIR/scripts"
PY="$DIR/.venv/bin/python"
SNAP="/tmp/snap_daily.json"
cd "$SC" || exit 1

# 10 recherches : clé | mot-clé Mercari | mot-clé Yahoo
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

echo "===== daily_scan $(date '+%Y-%m-%d %H:%M') ====="

# 0) instantané d'avant scan (pour le récap)
"$PY" - "$SNAP" <<'PY'
import report, json, sys
snap={}
for k,cfg in report.GAMES.items():
    mer,yh=report.gather(k,cfg); eb=report.gather_ebay(k)
    snap[k]={"mer":[p["url"] for p in mer],"yh":[p["url"] for p in yh],"eb":[p["url"] for p in eb]}
json.dump(snap, open(sys.argv[1],"w"))
PY

# 1) IP FR garantie
"$SC/vpn.sh" down >/dev/null 2>&1 || true

# 2) Phase France : eBay.fr (marché France)
echo "--- Phase FR : eBay.fr ---"
"$PY" ebay_fetch.py --all --pages 2 2>&1 | grep -E '=>' || true

# 3) Phase Japon : Mercari + Yahoo sous VPN JP (certaines annonces Mercari
#    ne sont visibles que depuis une IP japonaise) → VPN up → fetch → down
echo "--- VPN up (JP) ---"
if "$SC/vpn.sh" up; then
  echo "--- Phase JP : Mercari + Yahoo ---"
  for g in "${GAMES[@]}"; do IFS='|' read -r k mk yk <<< "$g"
    "$PY" fetch.py "$k" "$mk" "$yk" --source both 2>&1 | grep -E '=>|⚠️' || true
  done
  "$SC/vpn.sh" down || true
else
  echo "⚠️ VPN JP indisponible — Mercari+Yahoo sautés. Repli Mercari en IP FR :"
  for g in "${GAMES[@]}"; do IFS='|' read -r k mk yk <<< "$g"
    "$PY" fetch.py "$k" "$mk" "$yk" --source mercari 2>&1 | grep -E '=>|⚠️' || true
  done
fi

# 4) Régénération
echo "--- Régénération ---"
"$PY" report.py --all >/dev/null 2>&1
"$PY" build_index.py >/dev/null
"$PY" build_global.py >/dev/null

# 5) Récap des nouvelles ventes (vs instantané)
echo "===== RÉCAP nouvelles ventes ====="
"$PY" - "$SNAP" <<'PY'
import report, json, sys, datetime as dt
def d(x): return dt.datetime.fromtimestamp(x/1000,dt.timezone.utc).date().isoformat()
snap=json.load(open(sys.argv[1]))
labels={"mer":"🟡 Mercari","yh":"🔵 Yahoo","eb":"🇫🇷 eBay.fr"}
tot=0
for src in ("mer","yh","eb"):
    rows=[]
    for k,cfg in report.GAMES.items():
        mer,yh=report.gather(k,cfg); eb=report.gather_ebay(k)
        pts={"mer":mer,"yh":yh,"eb":eb}[src]; before=set(snap.get(k,{}).get(src,[]))
        cur="€" if src=="eb" else "¥"
        for p in pts:
            if p["url"] not in before: rows.append((cfg["label"],cur,p["y"],d(p["x"])))
    tot+=len(rows)
    print(f"{labels[src]} : {len(rows)}")
    for lab,cur,pr,dd in sorted(rows,key=lambda r:-r[2]):
        print(f"   {cur}{pr:<7} {dd}  {lab}")
print(f"TOTAL nouvelles ventes : {tot}")
PY

# 6) Commit + push
cd "$DIR" || exit 1
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -q -m "Scan quotidien automatique $(date '+%Y-%m-%d')" || true
  git push 2>&1 | tail -1 || true
else
  echo "(rien à committer)"
fi
echo "===== fin daily_scan ====="

#!/usr/bin/env python3
"""Vue d'ensemble du marché France (eBay.fr), 18 jeux agrégés → reports/france_global.html

Un seul graphe : volume de ventes/semaine (barres) + indice de prix normalisé
(chaque vente ÷ médiane post-annonce de son jeu, 1.0 = prix typique) en ligne,
avec la ligne Plaion. Neutralise le mélange de titres bon marché / chers.

    ../.venv/bin/python build_france_global.py
"""
import json, statistics, datetime as dt
from pathlib import Path

import report

OUT = report.ROOT / "reports" / "france_global.html"


def isoweek(x):
    d = dt.datetime.fromtimestamp(x / 1000, dt.timezone.utc)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def main():
    # baseline par jeu = médiane post-annonce (≥4 ventes), sinon médiane globale
    base, pts = {}, []
    for k in report.GAMES:
        eb = report.gather_ebay(k)
        post = [p["y"] for p in eb if p["x"] >= report.announce_x]
        allp = [p["y"] for p in eb]
        if len(post) >= 4:
            base[k] = statistics.median(post)
        elif allp:
            base[k] = statistics.median(allp)
        for p in eb:
            pts.append((k, p["x"], p["y"]))

    # agrégat par semaine
    weeks = {}
    for k, x, y in pts:
        w = isoweek(x)
        b = weeks.setdefault(w, {"n": 0, "ratios": []})
        b["n"] += 1
        if k in base and base[k]:
            b["ratios"].append(y / base[k])
    order = sorted(weeks)
    labels = order
    vol = [weeks[w]["n"] for w in order]
    idx = [round(statistics.median(weeks[w]["ratios"]), 3) if len(weeks[w]["ratios"]) >= 2
           else None for w in order]
    announce_w = isoweek(report.announce_x)

    # stats d'en-tête
    pre = [y / base[k] for k, x, y in pts if x < report.announce_x and k in base and base[k]]
    post = [y / base[k] for k, x, y in pts if x >= report.announce_x and k in base and base[k]]
    n_pre = sum(1 for _, x, _ in pts if x < report.announce_x)
    n_post = sum(1 for _, x, _ in pts if x >= report.announce_x)
    pre_idx = round(statistics.median(pre), 2) if pre else None
    post_idx = round(statistics.median(post), 2) if post else None

    data = {"labels": labels, "vol": vol, "idx": idx, "announce": announce_w}
    now = dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y")
    header = HEADER.format(now=now, total=len(pts), npre=n_pre, npost=n_post,
                           preidx=pre_idx if pre_idx is not None else "—",
                           postidx=post_idx if post_idx is not None else "—")
    html = HEAD + header + "<script>const DATA=" + json.dumps(data, ensure_ascii=False) + ";</script>\n" + CHART_JS
    OUT.write_text(html, encoding="utf-8")
    print(f"=> {OUT}  ({len(pts)} ventes France, {len(labels)} semaines)")


HEAD = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Marché France (eBay.fr) — vue d'ensemble</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f6fa;color:#1a1a2e;margin:0;padding:28px 20px 56px}
  .wrap{max-width:1000px;margin:0 auto}
  h1{font-size:1.5rem;margin:0 0 4px}
  .sub{color:#777;font-size:.85rem;margin:0 0 18px}
  .cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
  .stat{background:#fff;border-radius:10px;padding:12px 16px;box-shadow:0 1px 4px rgba(0,0,0,.07);min-width:130px}
  .stat .v{font-size:1.4rem;font-weight:700}
  .stat .l{color:#888;font-size:.76rem}
  .card{background:#fff;border-radius:14px;padding:18px 20px 10px;box-shadow:0 1px 4px rgba(0,0,0,.07)}
  .legend{font-size:.8rem;color:#666;margin:8px 2px 0}
  .note{color:#888;font-size:.78rem;margin-top:14px;line-height:1.5}
</style></head><body><div class="wrap">
"""

HEADER = """<h1>🇫🇷 Marché France (eBay.fr) — vue d'ensemble · 18 jeux Neo Geo AES</h1>
<p class="sub">Données du {now} · agrégat de tous les titres, prix normalisés</p>
<div class="cards">
  <div class="stat"><div class="v">{total}</div><div class="l">ventes totales</div></div>
  <div class="stat"><div class="v">{npre}</div><div class="l">avant 16/04</div></div>
  <div class="stat"><div class="v">{npost}</div><div class="l">depuis 16/04</div></div>
  <div class="stat"><div class="v">{preidx} → {postidx}</div><div class="l">indice prix (avant → depuis)</div></div>
</div>
<div class="card">
  <div style="height:460px;position:relative"><canvas id="c"></canvas></div>
  <div class="legend">Barres = nombre de ventes/semaine · Ligne = indice de prix
  (1.00 = prix typique post-annonce du jeu). Trait rouge = annonce Plaion (16/04).</div>
</div>
<p class="note">Lecture : l'indice neutralise le mélange de jeux (un KOF 2002 à 600€ et
un World Heroes 2 à 150€ comptent pareil, à 1.00 = « prix normal de ce jeu »). Un indice
qui monte = ventes au-dessus du prix habituel ; un volume qui retombe = activité qui se calme.
Les semaines à moins de 2 ventes n'ont pas de point d'indice (trop peu fiable).</p>
</div>
"""

CHART_JS = """<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js"></script>
<script>
const ai = DATA.labels.indexOf(DATA.announce);
const annoLine = { id:'anno', afterDatasetsDraw(ch){
  if(ai<0) return; const x=ch.scales.x.getPixelForValue(ai); const c=ch.ctx;
  c.save(); c.strokeStyle='#dc2626'; c.lineWidth=2; c.setLineDash([6,4]);
  c.beginPath(); c.moveTo(x,ch.chartArea.top); c.lineTo(x,ch.chartArea.bottom); c.stroke(); c.setLineDash([]);
  c.fillStyle='rgba(220,38,38,.9)'; c.font='bold 11px sans-serif';
  c.fillText('📣 Plaion 16/04', x+6, ch.chartArea.top+14); c.restore();
}};
new Chart(document.getElementById('c').getContext('2d'),{
  data:{ labels:DATA.labels, datasets:[
    { type:'bar', label:'Ventes / semaine', yAxisID:'y', data:DATA.vol,
      backgroundColor: DATA.labels.map((w)=> w>=DATA.announce ? 'rgba(37,99,235,.55)':'rgba(150,150,160,.45)') },
    { type:'line', label:'Indice de prix', yAxisID:'y1', data:DATA.idx, spanGaps:true,
      borderColor:'#dc2626', backgroundColor:'#dc2626', borderWidth:2, pointRadius:3, tension:.2 } ]},
  options:{ responsive:true, maintainAspectRatio:false,
    plugins:{ legend:{position:'top'},
      tooltip:{ callbacks:{ label:c=> c.dataset.type==='bar'
        ? ` ${c.raw} ventes` : (c.raw!=null?` indice ${c.raw.toFixed(2)}`:'') } } },
    scales:{
      y:{ position:'left', title:{display:true,text:'ventes / semaine'}, beginAtZero:true },
      y1:{ position:'right', title:{display:true,text:'indice de prix'}, grid:{drawOnChartArea:false},
           suggestedMin:0.6, suggestedMax:1.3 },
      x:{ ticks:{ maxRotation:90, minRotation:60, font:{size:9} } } } }
});
</script></body></html>
"""


if __name__ == "__main__":
    main()

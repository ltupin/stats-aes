#!/usr/bin/env python3
"""Vues d'ensemble agrégées (18 jeux) par marché → reports/{france,japan}_global.html

Un seul graphe par marché : volume de ventes/semaine (barres) + indice de prix
normalisé (chaque vente ÷ médiane post-annonce de son jeu, 1.0 = prix typique)
+ ligne Plaion. Neutralise le mélange de titres bon marché / chers.

- France : eBay.fr (€)
- Japon  : Yahoo Auctions (¥) — dates de vente réelles (Mercari exclu de la
  série temporelle car sa date est la mise en ligne, pas la vente).

    ../.venv/bin/python build_global.py
"""
import json, statistics, datetime as dt

import report


def isoweek(x):
    d = dt.datetime.fromtimestamp(x / 1000, dt.timezone.utc)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def ebay_points(k):
    return [(p["x"], p["y"]) for p in report.gather_ebay(k)]


def yahoo_points(k):
    _, yh = report.gather(k, report.GAMES[k])
    return [(p["x"], p["y"]) for p in yh]


MARKETS = {
    "france": {"file": "france_global.html", "flag": "🇫🇷", "cur": "€",
               "market": "France (eBay.fr)", "src": ebay_points,
               "note_src": "eBay.fr (ventes terminées)"},
    "japan":  {"file": "japan_global.html", "flag": "🇯🇵", "cur": "¥",
               "market": "Japon (Yahoo Auctions)", "src": yahoo_points,
               "note_src": "Yahoo Auctions (enchères clôturées, dates de vente réelles)"},
}


def generate(cfg):
    base, pts = {}, []
    for k in report.GAMES:
        sales = cfg["src"](k)
        post = [y for x, y in sales if x >= report.announce_x]
        allp = [y for x, y in sales]
        if len(post) >= 4:
            base[k] = statistics.median(post)
        elif allp:
            base[k] = statistics.median(allp)
        for x, y in sales:
            pts.append((k, x, y))

    weeks = {}
    for k, x, y in pts:
        b = weeks.setdefault(isoweek(x), {"n": 0, "ratios": []})
        b["n"] += 1
        if base.get(k):
            b["ratios"].append(y / base[k])
    order = sorted(weeks)
    data = {
        "labels": order,
        "vol": [weeks[w]["n"] for w in order],
        "idx": [round(statistics.median(weeks[w]["ratios"]), 3)
                if len(weeks[w]["ratios"]) >= 2 else None for w in order],
        "announce": isoweek(report.announce_x),
    }
    pre = [y / base[k] for k, x, y in pts if x < report.announce_x and base.get(k)]
    post = [y / base[k] for k, x, y in pts if x >= report.announce_x and base.get(k)]
    h = {
        "now": dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y"),
        "flag": cfg["flag"], "market": cfg["market"], "note_src": cfg["note_src"],
        "total": len(pts),
        "npre": sum(1 for _, x, _ in pts if x < report.announce_x),
        "npost": sum(1 for _, x, _ in pts if x >= report.announce_x),
        "preidx": round(statistics.median(pre), 2) if pre else "—",
        "postidx": round(statistics.median(post), 2) if post else "—",
    }
    html = HEAD + HEADER.format(**h) + "<script>const DATA=" \
        + json.dumps(data, ensure_ascii=False) + ";</script>\n" + CHART_JS
    out = report.RPT_DIR / cfg["file"]
    out.write_text(html, encoding="utf-8")
    print(f"=> {out}  ({len(pts)} ventes, {len(order)} semaines)")


HEAD = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vue d'ensemble — marché</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f6fa;color:#1a1a2e;margin:0;padding:28px 20px 56px}
  .wrap{max-width:1000px;margin:0 auto}
  h1{font-size:1.5rem;margin:0 0 4px}
  .sub{color:#777;font-size:.85rem;margin:0 0 18px}
  .cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
  .stat{background:#fff;border-radius:10px;padding:12px 16px;box-shadow:0 1px 4px rgba(0,0,0,.07);min-width:120px}
  .stat .v{font-size:1.35rem;font-weight:700}
  .stat .l{color:#888;font-size:.76rem}
  .card{background:#fff;border-radius:14px;padding:18px 20px 10px;box-shadow:0 1px 4px rgba(0,0,0,.07)}
  .legend{font-size:.8rem;color:#666;margin:8px 2px 0}
  .note{color:#888;font-size:.78rem;margin-top:14px;line-height:1.5}
  .nav{font-size:.82rem;margin-bottom:14px}
  .nav a{color:#2563eb;text-decoration:none}
</style></head><body><div class="wrap">
<div class="nav"><a href="../index.html">← sommaire</a> · <a href="france_global.html">🇫🇷 France</a> · <a href="japan_global.html">🇯🇵 Japon</a></div>
"""

HEADER = """<h1>{flag} Marché {market} — vue d'ensemble · 18 jeux Neo Geo AES</h1>
<p class="sub">Données du {now} · agrégat de tous les titres, prix normalisés · source : {note_src}</p>
<div class="cards">
  <div class="stat"><div class="v">{total}</div><div class="l">ventes totales</div></div>
  <div class="stat"><div class="v">{npre}</div><div class="l">avant 16/04</div></div>
  <div class="stat"><div class="v">{npost}</div><div class="l">depuis 16/04</div></div>
  <div class="stat"><div class="v">{preidx} → {postidx}</div><div class="l">indice prix (avant → depuis)</div></div>
</div>
<div class="card">
  <div style="height:460px;position:relative"><canvas id="c"></canvas></div>
  <div class="legend">Barres = ventes/semaine · Ligne = indice de prix
  (1.00 = prix typique post-annonce du jeu). Trait rouge = annonce Plaion (16/04).</div>
</div>
<p class="note">L'indice neutralise le mélange de jeux : chaque vente est rapportée à la médiane
post-annonce de SON titre, donc un opus à 600 et un autre à 150 comptent pareil (1.00 = « prix normal »).
Indice qui monte = ventes au-dessus du prix habituel ; volume qui retombe = activité qui se calme.
Les semaines à moins de 2 ventes n'ont pas de point d'indice.</p>
</div>
"""

CHART_JS = """<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js"></script>
<script>
const annoLine = { id:'anno', afterDatasetsDraw(ch){
  const ai=DATA.labels.indexOf(DATA.announce); if(ai<0) return;
  const x=ch.scales.x.getPixelForValue(ai); const c=ch.ctx;
  c.save(); c.strokeStyle='#dc2626'; c.lineWidth=2; c.setLineDash([6,4]);
  c.beginPath(); c.moveTo(x,ch.chartArea.top); c.lineTo(x,ch.chartArea.bottom); c.stroke(); c.setLineDash([]);
  c.fillStyle='rgba(220,38,38,.9)'; c.font='bold 11px sans-serif';
  c.fillText('📣 Plaion 16/04', x+6, ch.chartArea.top+14); c.restore();
}};
new Chart(document.getElementById('c').getContext('2d'),{
  data:{ labels:DATA.labels, datasets:[
    { type:'bar', label:'Ventes / semaine', yAxisID:'y', data:DATA.vol,
      backgroundColor: DATA.labels.map(w=> w>=DATA.announce ? 'rgba(37,99,235,.55)':'rgba(150,150,160,.45)') },
    { type:'line', label:'Indice de prix', yAxisID:'y1', data:DATA.idx, spanGaps:true,
      borderColor:'#dc2626', backgroundColor:'#dc2626', borderWidth:2, pointRadius:3, tension:.2 } ]},
  options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{position:'top'},
      tooltip:{ callbacks:{ label:c=> c.dataset.type==='bar' ? ` ${c.raw} ventes`
        : (c.raw!=null?` indice ${c.raw.toFixed(2)}`:'') } } },
    scales:{ y:{ position:'left', title:{display:true,text:'ventes / semaine'}, beginAtZero:true },
      y1:{ position:'right', title:{display:true,text:'indice de prix'}, grid:{drawOnChartArea:false}, suggestedMin:0.6, suggestedMax:1.3 },
      x:{ ticks:{ maxRotation:90, minRotation:60, font:{size:9} } } },
  plugins:[annoLine] }});
</script></body></html>
"""


def main():
    for cfg in MARKETS.values():
        generate(cfg)


if __name__ == "__main__":
    main()

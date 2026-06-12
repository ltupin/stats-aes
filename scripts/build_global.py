#!/usr/bin/env python3
"""Vues d'ensemble agrégées (tous les jeux) par marché → reports/{france,japan}_global.html

Chart 1 : volume de ventes/semaine (barres) + indice de prix normalisé (ligne).
Chart 2 (Japon/Yahoo seulement) : offre vs demande — enchères terminées/semaine,
empilées vendues (≥1 offre / achat immédiat) + invendues (0 offre), + taux de vente.
eBay n'expose que les ventes → pas de chart 2 côté France.

    ../.venv/bin/python build_global.py
"""
import csv, json, statistics, datetime as dt
from datetime import timezone, timedelta

import report

RAW = report.RAW_DIR
ANN = report.announce_x


def monday_ms(x):
    d = dt.datetime.fromtimestamp(x / 1000, timezone.utc)
    m = (d - timedelta(days=d.isoweekday() - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(m.timestamp() * 1000)


def lbl(ms):
    return dt.datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%d/%m")


def ebay_points(k):
    return [(p["x"], p["y"]) for p in report.gather_ebay(k)]


def parse_yh_date(s):
    try:
        return int(dt.datetime.strptime(s.replace(" +0900", "").strip(), "%Y-%m-%d %H:%M")
                   .replace(tzinfo=timezone(timedelta(hours=9))).timestamp() * 1000)
    except Exception:
        return None


# ── Marché France : ventes eBay (chart 1 seulement) ─────────────────────────
def compute_sales(cfg):
    base, pts = {}, []
    for k in report.GAMES:
        sales = cfg["src"](k)
        post = [y for x, y in sales if x >= ANN]
        allp = [y for x, y in sales]
        base[k] = statistics.median(post) if len(post) >= 4 else (statistics.median(allp) if allp else None)
        for x, y in sales:
            pts.append((k, x, y))
    start_x = cfg.get("start_x", report.start_x)
    weeks = {}
    for k, x, y in pts:
        if x < start_x:
            continue
        b = weeks.setdefault(monday_ms(x), {"n": 0, "ratios": []})
        b["n"] += 1
        if base.get(k):
            b["ratios"].append(y / base[k])
    order = sorted(weeks)
    pre = [y / base[k] for k, x, y in pts if x < ANN and base.get(k)]
    post = [y / base[k] for k, x, y in pts if x >= ANN and base.get(k)]
    return {
        "labels": [lbl(w) for w in order],
        "vol": [weeks[w]["n"] for w in order],
        "idx": [round(statistics.median(weeks[w]["ratios"]), 3) if len(weeks[w]["ratios"]) >= 2 else None
                for w in order],
        "announce_idx": sum(1 for w in order if w < ANN),
        "total": len(pts),
        "npre": sum(1 for _, x, _ in pts if x < ANN),
        "npost": sum(1 for _, x, _ in pts if x >= ANN),
        "preidx": round(statistics.median(pre), 2) if pre else "—",
        "postidx": round(statistics.median(post), 2) if post else "—",
    }


# ── Marché Japon : Yahoo (chart 1 ventes + chart 2 offre/demande) ───────────
def compute_yahoo():
    # base prix par jeu = médiane post-annonce des ventes (>= plancher)
    base = {}
    for k, gcfg in report.GAMES.items():
        _, yh = report.gather(k, gcfg)
        post = [p["y"] for p in yh if p["x"] >= ANN]
        if len(post) >= 4:
            base[k] = statistics.median(post)
    weeks = {}  # ms -> sold, unsold, ratios
    n_sold = n_pre = n_post = 0
    pre_r, post_r = [], []
    for k, gcfg in report.GAMES.items():
        keep = report.build_filter(gcfg, k)
        path = RAW / f"{gcfg.get('raw', k)}_yahoo.csv"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            rd = csv.reader(f, delimiter=";"); next(rd, None)
            for row in rd:
                if len(row) < 6:
                    continue
                title, url, ps, bs, kind, ends = row
                if not keep(title, url):
                    continue
                x = parse_yh_date(ends)
                if not x or x < report.start_x:
                    continue
                try:
                    bid = int(bs)
                except ValueError:
                    bid = 0
                sold = bid >= 1 or kind == "Buy-Now"
                try:
                    price = int(ps.replace("¥", "").replace(",", ""))
                except ValueError:
                    price = 0
                w = monday_ms(x)
                b = weeks.setdefault(w, {"sold": 0, "unsold": 0, "ratios": []})
                if sold and price >= report.PRICE_FLOOR:
                    b["sold"] += 1; n_sold += 1
                    if base.get(k):
                        r = price / base[k]
                        b["ratios"].append(r)
                        (pre_r if x < ANN else post_r).append(r)
                    if x < ANN: n_pre += 1
                    else: n_post += 1
                elif not sold:
                    b["unsold"] += 1
    order = sorted(weeks)
    return {
        "labels": [lbl(w) for w in order],
        "vol": [weeks[w]["sold"] for w in order],
        "idx": [round(statistics.median(weeks[w]["ratios"]), 3) if len(weeks[w]["ratios"]) >= 2 else None
                for w in order],
        "sold": [weeks[w]["sold"] for w in order],
        "unsold": [weeks[w]["unsold"] for w in order],
        "announce_idx": sum(1 for w in order if w < ANN),
        "total": n_sold,
        "npre": n_pre, "npost": n_post,
        "preidx": round(statistics.median(pre_r), 2) if pre_r else "—",
        "postidx": round(statistics.median(post_r), 2) if post_r else "—",
    }


def compute_mercari_supply():
    """Offre Mercari par semaine de MISE EN LIGNE (date 'Created') : annonces
    déjà vendues (SOLD_OUT) vs encore en vente (ON_SALE/TRADING)."""
    weeks = {}
    for k, gcfg in report.GAMES.items():
        keep = report.build_filter(gcfg, k)
        path = RAW / f"{gcfg.get('raw', k)}_mercari.csv"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            rd = csv.reader(f, delimiter=";"); next(rd, None)
            for row in rd:
                if len(row) < 5:
                    continue
                title, url, ps, status, cs = row
                if not keep(title, url):
                    continue
                try:
                    p = int(ps.replace("¥", "").replace(",", ""))
                except ValueError:
                    continue
                if p < report.PRICE_FLOOR or p > 5_000_000:
                    continue
                try:
                    x = int(dt.datetime.strptime(cs, "%Y-%m-%d %H:%M UTC")
                            .replace(tzinfo=timezone.utc).timestamp() * 1000)
                except ValueError:
                    continue
                if x < report.start_x:
                    continue
                b = weeks.setdefault(monday_ms(x), {"sold": 0, "onsale": 0})
                if status == "SOLD_OUT":
                    b["sold"] += 1
                else:
                    b["onsale"] += 1
    order = sorted(weeks)
    return {"labels2": [lbl(w) for w in order],
            "sold2": [weeks[w]["sold"] for w in order],
            "onsale2": [weeks[w]["onsale"] for w in order],
            "announce_idx2": sum(1 for w in order if w < ANN)}


MARKETS = {
    "france": {"file": "france_global.html", "flag": "🇫🇷", "market": "France (eBay.fr)",
               "src": ebay_points, "note_src": "eBay.fr (ventes terminées)",
               "start_x": int(dt.datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)},
    "japan":  {"file": "japan_global.html", "flag": "🇯🇵", "market": "Japon (Yahoo Auctions)",
               "supply": True, "note_src": "Yahoo Auctions (enchères clôturées)"},
}


def market_scale():
    """Part de Mercari dans les ventes → facteur pour estimer l'offre totale."""
    m = y = e = 0
    for k, cfg in report.GAMES.items():
        mer, yh = report.gather(k, cfg)
        m += len(mer); y += len(yh); e += len(report.gather_ebay(k))
    tot = m + y + e
    return (round(100 * m / tot) if tot else 0, round(tot / m, 1) if m else 1)


def generate(cfg):
    data = compute_yahoo() if cfg.get("supply") else compute_sales(cfg)
    chart2 = CHART2_NOTE
    if cfg.get("supply"):
        data.update(compute_mercari_supply())
        share, K = market_scale()
        chart2 = CHART2_HTML.format(share=share, K=str(K).replace(".", ","))
    h = {"now": dt.datetime.now(timezone.utc).strftime("%d/%m/%Y"),
         "flag": cfg["flag"], "market": cfg["market"], "note_src": cfg["note_src"],
         "total": data["total"], "npre": data["npre"], "npost": data["npost"],
         "preidx": data["preidx"], "postidx": data["postidx"],
         "chart2": chart2}
    html = HEAD + HEADER.format(**h) + "<script>const DATA=" \
        + json.dumps(data, ensure_ascii=False) + ";</script>\n" + CHART_JS
    (report.RPT_DIR / cfg["file"]).write_text(html, encoding="utf-8")
    print(f"=> {cfg['file']}  ({data['total']} ventes, {len(data['labels'])} semaines"
          + (", + offre/demande" if cfg.get("supply") else "") + ")")


HEAD = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vue d'ensemble — marché</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f6fa;color:#1a1a2e;margin:0;padding:28px 20px 56px}
  .wrap{max-width:1000px;margin:0 auto}
  h1{font-size:1.5rem;margin:0 0 4px} .sub{color:#777;font-size:.85rem;margin:0 0 18px}
  .cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
  .stat{background:#fff;border-radius:10px;padding:12px 16px;box-shadow:0 1px 4px rgba(0,0,0,.07);min-width:120px}
  .stat .v{font-size:1.35rem;font-weight:700} .stat .l{color:#888;font-size:.76rem}
  .card{background:#fff;border-radius:14px;padding:18px 20px 10px;box-shadow:0 1px 4px rgba(0,0,0,.07);margin-bottom:18px}
  .card h2{font-size:1.05rem;margin:0 0 2px} .card .cap{color:#888;font-size:.8rem;margin:0 0 10px}
  .legend{font-size:.8rem;color:#666;margin:8px 2px 0}
  .note{color:#888;font-size:.82rem;line-height:1.5;background:#fff;border-radius:14px;padding:16px 20px;box-shadow:0 1px 4px rgba(0,0,0,.07);margin-bottom:18px}
  .nav{font-size:.82rem;margin-bottom:14px} .nav a{color:#2563eb;text-decoration:none}
</style></head><body><div class="wrap">
<div class="nav"><a href="../index.html">← sommaire</a> · <a href="france_global.html">🇫🇷 France</a> · <a href="japan_global.html">🇯🇵 Japon</a></div>
"""

HEADER = """<h1>{flag} Marché {market} — vue d'ensemble</h1>
<p class="sub">Données du {now} · agrégat de tous les jeux · source : {note_src}</p>
<div class="cards">
  <div class="stat"><div class="v">{total}</div><div class="l">ventes totales</div></div>
  <div class="stat"><div class="v">{npre}</div><div class="l">avant 16/04</div></div>
  <div class="stat"><div class="v">{npost}</div><div class="l">depuis 16/04</div></div>
  <div class="stat"><div class="v">{preidx} → {postidx}</div><div class="l">indice prix (avant → depuis)</div></div>
</div>
<div class="card">
  <h2>Ventes & niveau de prix</h2>
  <p class="cap">Barres = ventes/semaine · Ligne = indice de prix (1.00 = prix typique post-annonce). Trait rouge = annonce Plaion.</p>
  <div style="height:380px;position:relative"><canvas id="c"></canvas></div>
</div>
{chart2}
</div>
"""

CHART2_HTML = """<div class="card">
  <h2>Offre — annonces Mercari mises en vente / semaine</h2>
  <p class="cap">🔵 déjà vendues + ⬜ encore en vente = offre Mercari (par semaine de mise en ligne). Les annonces récentes n'ont pas encore eu le temps de se vendre.</p>
  <p class="cap">📐 Estimation marché : Mercari ≈ {share}% des ventes → offre totale du marché ≈ <b>ces barres × {K}</b> (Yahoo/eBay ne datent pas les mises en vente, d'où l'extrapolation).</p>
  <div style="height:360px;position:relative"><canvas id="c2"></canvas></div>
</div>"""

CHART2_NOTE = """<div class="note">ℹ️ Offre non affichée ici : côté France on ne collecte pour
l'instant que les <i>ventes terminées</i> eBay (pas encore les annonces actives invendues).
Voir la <a href="japan_global.html">vue Japon</a> (offre Mercari).</div>"""

CHART_JS = """<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js"></script>
<script>
const AIDX = DATA.announce_idx;
function plaion(chart, idx){
  const bars = chart.getDatasetMeta(0).data;
  if (idx <= 0 || idx > bars.length || !bars.length) return;
  let x; if (idx < bars.length){ const b=bars[idx]; x=b.x-(b.width?b.width/2:0)-2; }
  else { const b=bars[bars.length-1]; x=b.x+(b.width?b.width/2:0); }
  const c=chart.ctx, top=chart.chartArea.top, bot=chart.chartArea.bottom;
  c.save(); c.strokeStyle='#dc2626'; c.lineWidth=2; c.setLineDash([6,4]);
  c.beginPath(); c.moveTo(x,top); c.lineTo(x,bot); c.stroke(); c.setLineDash([]);
  c.fillStyle='rgba(220,38,38,.9)'; const l='📣 Plaion AES+'; c.font='bold 11px sans-serif';
  c.fillRect(x+4,top+4,c.measureText(l).width+12,22); c.fillStyle='#fff'; c.fillText(l,x+10,top+19); c.restore();
}
const makeAnno = idx => ({ id:'anno'+idx, afterDatasetsDraw:ch=>plaion(ch,idx) });
const annoLine = makeAnno(AIDX);
// Chart 1 : ventes + indice prix
new Chart(document.getElementById('c').getContext('2d'),{
  data:{ labels:DATA.labels, datasets:[
    { type:'bar', label:'Ventes / semaine', yAxisID:'y', data:DATA.vol,
      backgroundColor: DATA.labels.map((_,i)=> i>=AIDX ? 'rgba(37,99,235,.6)':'rgba(150,150,160,.5)'),
      categoryPercentage:0.9, barPercentage:0.95 },
    { type:'line', label:'Indice de prix', yAxisID:'y1', data:DATA.idx, spanGaps:true,
      borderColor:'#dc2626', borderWidth:2, pointRadius:3, tension:.2 } ]},
  options:{ responsive:true, maintainAspectRatio:false,
    plugins:{ legend:{position:'top'}, tooltip:{ callbacks:{
      title:i=>'Semaine du '+i[0].label,
      label:c=> c.dataset.type==='bar'?` ${c.parsed.y} ventes`:(c.parsed.y!=null?` indice ${c.parsed.y.toFixed(2)}`:'') } } },
    scales:{ x:{ticks:{autoSkip:true,maxRotation:0,font:{size:10}},grid:{display:false}},
      y:{position:'left',title:{display:true,text:'ventes / semaine'},beginAtZero:true},
      y1:{position:'right',title:{display:true,text:'indice de prix'},grid:{drawOnChartArea:false},suggestedMin:0.6,suggestedMax:1.3} } },
  plugins:[annoLine] });
// Chart 2 : offre Mercari (mises en vente / semaine, empilées vendues + en vente)
if (DATA.sold2) {
  new Chart(document.getElementById('c2').getContext('2d'),{
    data:{ labels:DATA.labels2, datasets:[
      { type:'bar', label:'Déjà vendues', data:DATA.sold2, backgroundColor:'rgba(37,99,235,.65)', stack:'s', categoryPercentage:0.9, barPercentage:0.95 },
      { type:'bar', label:'Encore en vente', data:DATA.onsale2, backgroundColor:'rgba(180,180,190,.6)', stack:'s', categoryPercentage:0.9, barPercentage:0.95 } ]},
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{position:'top'}, tooltip:{ callbacks:{ title:i=>'Semaine du '+i[0].label } } },
      scales:{ x:{stacked:true,ticks:{autoSkip:true,maxRotation:0,font:{size:10}},grid:{display:false}},
        y:{stacked:true,title:{display:true,text:'annonces mises en vente'},beginAtZero:true} } },
    plugins:[makeAnno(DATA.announce_idx2)] });
}
</script></body></html>
"""


def main():
    for cfg in MARKETS.values():
        generate(cfg)


if __name__ == "__main__":
    main()

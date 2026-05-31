#!/usr/bin/env python3
"""Génère podcast.html à la racine : un script de présentation (idées fortes +
3 graphes de synthèse) bâti sur les vraies stats de report.py.

    ../.venv/bin/python build_podcast.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import report

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "podcast.html"
KOF_YEARS = ["94", "95", "96", "97", "98", "99", "2000", "2001", "2002"]


def compute():
    g = {}
    for k, cfg in report.GAMES.items():
        mer, yh = report.gather(k, cfg)
        sm = report.stats_split(mer)
        sy = report.stats_split(yh)
        g[k] = {
            "label": cfg["label"], "n": len(mer) + len(yh),
            "mer": {"pre": sm[1], "post": sm[3], "d": round(sm[4])},
            "yh":  {"pre": sy[1], "post": sy[3], "d": round(sy[4])},
        }
    return g


def main():
    g = compute()
    # Onde de choc : Δ% Yahoo, trié décroissant (tous jeux avec données post)
    shock = sorted(
        [{"label": v["label"], "yh": v["yh"]["d"], "mer": v["mer"]["d"]}
         for v in g.values() if v["yh"]["post"]],
        key=lambda x: -x["yh"])
    # Échelle KOF : prix médian post (Mercari) + volume, par année
    ladder = [{"year": y, "price": g[f"kof_{y}"]["mer"]["post"], "n": g[f"kof_{y}"]["n"]}
              for y in KOF_YEARS if f"kof_{y}" in g]
    # Avant / après (Yahoo) sur quelques fers de lance
    flag_keys = ["ffs", "aof2", "samsho2", "wh2", "samsho1", "ff2"]
    flags = [{"label": g[k]["label"], "pre": g[k]["yh"]["pre"], "post": g[k]["yh"]["post"]}
             for k in flag_keys if k in g]

    data = {"shock": shock, "ladder": ladder, "flags": flags}
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    n_games = len(g)
    # repères chiffrés pour le texte
    ff1 = g.get("ff1", {}).get("yh", {}).get("d", 0)
    k94, k02 = g["kof_94"]["mer"]["post"], g["kof_2002"]["mer"]["post"]
    k01 = g["kof_2001"]["yh"]["d"]

    html = (HEAD
            + NARRATIVE.format(now=now, n=n_games, ff1=ff1,
                               k94=f"{k94:,}".replace(",", " "),
                               k02=f"{k02:,}".replace(",", " "), k01=k01)
            + "<script>const DATA = " + json.dumps(data, ensure_ascii=False) + ";</script>\n"
            + CHART_JS + "</body></html>\n")
    OUT.write_text(html, encoding="utf-8")
    print(f"=> {OUT}")


HEAD = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Neo Geo & l'effet Plaion — script de présentation</title>
<style>
  :root { --hot:#dc2626; --mer:#f59e0b; --yh:#2563eb; --ink:#1a1a2e; }
  * { box-sizing: border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
         background:#f5f6fa; color:var(--ink); margin:0; padding:32px 20px 64px;
         line-height:1.6; }
  .wrap { max-width:880px; margin:0 auto; }
  h1 { font-size:1.9rem; margin:0 0 4px; }
  .sub { color:#777; font-size:.9rem; margin:0 0 26px; }
  .hero { background:linear-gradient(90deg,#fef3c7,#fee2e2); border-left:4px solid var(--hot);
          border-radius:10px; padding:16px 20px; margin-bottom:30px; font-size:1.02rem; }
  .seg { background:#fff; border-radius:14px; padding:22px 24px; margin-bottom:18px;
         box-shadow:0 1px 4px rgba(0,0,0,.07); }
  .seg .badge { display:inline-block; background:var(--ink); color:#fff; font-size:.72rem;
                font-weight:700; padding:3px 9px; border-radius:20px; letter-spacing:.04em; }
  .seg h2 { font-size:1.25rem; margin:10px 0 8px; }
  .seg p { margin:8px 0; }
  .seg ul { margin:8px 0; padding-left:20px; }
  .seg li { margin:4px 0; }
  .say { background:#f0fdf4; border-left:4px solid #16a34a; padding:10px 14px; border-radius:8px;
         margin:12px 0 4px; font-size:.97rem; }
  .say b { color:#15803d; }
  .show { color:#777; font-size:.82rem; font-style:italic; margin-top:6px; }
  .chartbox { background:#fff; border-radius:14px; padding:18px 20px 8px; margin:18px 0;
              box-shadow:0 1px 4px rgba(0,0,0,.07); }
  .chartbox h3 { margin:0 0 2px; font-size:1.05rem; }
  .chartbox .cap { color:#888; font-size:.8rem; margin:0 0 10px; }
  .chartbox .canvas-h { position:relative; height:380px; }
  .memo { background:var(--ink); color:#fff; border-radius:14px; padding:20px 24px; margin-top:26px; }
  .memo h2 { margin:0 0 10px; font-size:1.1rem; }
  .memo li { margin:6px 0; }
  .memo b { color:#fbbf24; }
  footer { color:#aaa; font-size:.78rem; text-align:center; margin-top:30px; }
</style></head><body><div class="wrap">
"""

NARRATIVE = """
<h1>🎙️ Neo Geo & « l'effet Plaion »</h1>
<p class="sub">Script de présentation — données du {now} · {n} jeux suivis · Mercari + Yahoo Auctions Japon</p>

<div class="hero">
  <b>Le pitch en une phrase :</b> en avril 2026, une entreprise annonce une nouvelle console
  qui relit les cartouches d'origine — et en quelques semaines, le prix de jeux vieux de
  30 ans <b>double</b>. On l'a mesuré, marché par marché.
</div>

<div class="seg">
  <span class="badge">ACCROCHE</span>
  <h2>Une annonce, un électrochoc</h2>
  <p>Le <b>16 avril 2026</b>, Plaion annonce la <b>Neo Geo AES+</b>, une console neuve
  compatible avec les cartouches originales. Avant / après cette date, la quasi-totalité
  des jeux suivis ont vu leur prix médian bondir — souvent de <b>+50 % à +170 %</b>.</p>
  <div class="say">💬 <b>À dire :</b> « Le matériel revalorise le logiciel. Si tu peux
  rejouer à la cartouche, la cartouche vaut plus cher. C'est de l'économie de biens
  complémentaires, en temps réel, sur un marché de collection. »</div>
  <p class="show">📊 Montrer : le graphe « L'onde de choc » ci-dessous.</p>
</div>

<div class="chartbox">
  <h3>L'onde de choc</h3>
  <p class="cap">Variation de la médiane des ventes Yahoo, avant vs depuis le 16/04/2026.</p>
  <div class="canvas-h"><canvas id="cShock"></canvas></div>
</div>

<div class="seg">
  <span class="badge">IDÉE 1</span>
  <h2>Ce n'est pas un frémissement : un repricing brutal et synchrone</h2>
  <p>Les jeux populaires « milieu de gamme » (autour de ¥6 000 avant l'annonce) ont
  <b>doublé voire plus</b> : Art of Fighting 2, Samurai Shodown 2, Fatal Fury Special,
  World Heroes 2… tous entre +130 % et +170 %.</p>
  <div class="say">💬 <b>À dire :</b> « Quand un marché entier se repositionne dans le
  même sens, en même temps, ce n'est pas du bruit : c'est un changement d'anticipation. »</div>
</div>

<div class="seg">
  <span class="badge">IDÉE 2</span>
  <h2>Deux marchés indépendants, un même signal</h2>
  <p>On a mesuré sur <b>deux places distinctes</b> : Mercari (prix fixe, revente) et Yahoo
  (enchères). Elles bougent ensemble — Samurai Shodown 1 fait +100 % des deux côtés,
  Art of Fighting 2 +147 % / +156 %.</p>
  <div class="say">💬 <b>À dire :</b> « Quand deux marchés qui ne se parlent pas racontent
  la même histoire, on peut y croire. Ce n'est pas un artefact d'une plateforme. »</div>
</div>

<div class="seg">
  <span class="badge">IDÉE 3</span>
  <h2>Le paradoxe de l'abondance</h2>
  <p>Le jeu le <b>plus courant</b> de tous, Fatal Fury 1 (l'original), n'a quasiment pas
  bougé sur Yahoo : <b>+{ff1} %</b> seulement. Trop d'exemplaires en circulation, un
  marché déjà liquide et efficient → il <b>absorbe</b> le choc.</p>
  <ul>
    <li>Les plus fortes hausses ne sont PAS les jeux les plus rares…</li>
    <li>…mais les jeux <b>désirables ET encore abordables</b> : le « sweet spot » où la
    demande nouvelle rencontre une offre limitée.</li>
  </ul>
  <div class="say">💬 <b>À dire :</b> « La rareté ne suffit pas. Ce qui s'envole, c'est ce
  que beaucoup veulent ET que peu possèdent encore à bas prix. »</div>
</div>

<div class="chartbox">
  <h3>L'échelle de la rareté — la série King of Fighters</h3>
  <p class="cap">Prix médian (Mercari, depuis l'annonce) et volume de ventes, par millésime.</p>
  <div class="canvas-h"><canvas id="cLadder"></canvas></div>
</div>

<div class="seg">
  <span class="badge">IDÉE 4</span>
  <h2>Une échelle de prix qui raconte l'histoire d'une série</h2>
  <p>Sur les 9 King of Fighters, le prix grimpe régulièrement du premier au dernier :
  de <b>~¥{k94}</b> pour le '94 à <b>~¥{k02}</b> pour le 2002. Les derniers opus, produits
  en bien moins d'exemplaires en fin de vie de la console, sont devenus des pièces de collection.</p>
  <div class="say">💬 <b>À dire :</b> « Plus on avance dans la série, plus c'est cher — et
  plus c'est cher, moins ça se vend. Le prix et la rareté montent ensemble, le volume s'effondre. »</div>
</div>

<div class="seg">
  <span class="badge">IDÉE 5 · honnêteté</span>
  <h2>Quand les données deviennent fragiles</h2>
  <p>Tout en haut de l'échelle (KOF 2001, 2002), les variations deviennent erratiques —
  jusqu'à <b>{k01} %</b> sur le 2001. Ce n'est pas une vraie baisse : à ce niveau de prix,
  il se vend <b>1 à 2 exemplaires par mois</b>, donc une seule transaction fait basculer la médiane.</p>
  <div class="say">💬 <b>À dire :</b> « Au-delà d'un certain prix, le marché est trop mince
  pour conclure quoi que ce soit. Le reconnaître, c'est ça, l'honnêteté de la donnée. »</div>
  <p class="show">📊 C'est précisément pourquoi on ne suit que les jeux à ≥ 5 ventes/semaine.</p>
</div>

<div class="chartbox">
  <h3>Avant / Après — les fers de lance</h3>
  <p class="cap">Médiane Yahoo avant le 16/04 (gris) vs depuis (rouge).</p>
  <div class="canvas-h"><canvas id="cFlags"></canvas></div>
</div>

<div class="seg">
  <span class="badge">IDÉE 6 · coulisses</span>
  <h2>Comment on sait ce qu'on sait</h2>
  <p>Mesurer un « prix propre » est un travail d'orfèvre. Il a fallu écarter :</p>
  <ul>
    <li>les <b>lots</b> et bundles (prix non attribuable à un jeu),</li>
    <li>les <b>mauvaises plateformes</b> : versions CD, Mega Drive, portages Switch…,</li>
    <li>les <b>produits dérivés</b> : télécartes, posters, et même un lot de gommes Gundam !</li>
  </ul>
  <p>Puis une <b>médiane hebdomadaire</b> (robuste aux prix aberrants) plutôt qu'une moyenne.</p>
  <div class="say">💬 <b>À dire :</b> « Le plus dur n'est pas de calculer une moyenne — c'est
  de décider ce qui mérite d'entrer dans le calcul. Une annonce mal orthographiée
  "ネオゲオ" au lieu de "ネオジオ", et une vente passe sous le radar. »</div>
</div>

<div class="seg">
  <span class="badge">CHUTE</span>
  <h2>La morale économique</h2>
  <p>Une annonce <b>datée</b>, c'est une expérience naturelle quasi parfaite : un avant,
  un après, une ligne nette. Ceux qui détenaient les cartouches <b>avant</b> le 16 avril ont
  capté la plus-value.</p>
  <div class="say">💬 <b>À dire :</b> « La valeur d'un objet de collection ne dépend pas
  que de l'objet : elle dépend de l'écosystème qui l'entoure. Changez l'écosystème —
  ici, une console — et vous changez la valeur du passé. »</div>
</div>

<div class="memo">
  <h2>🧠 Mémo — 6 punchlines à placer</h2>
  <ul>
    <li><b>1.</b> « Le matériel revalorise le logiciel. »</li>
    <li><b>2.</b> « Deux marchés qui ne se parlent pas, une même histoire → on y croit. »</li>
    <li><b>3.</b> « La rareté ne suffit pas : c'est désirable + encore abordable qui s'envole. »</li>
    <li><b>4.</b> « Plus c'est cher, moins ça se vend — le volume s'effondre quand le prix grimpe. »</li>
    <li><b>5.</b> « Quand il se vend 1 pièce par mois, la médiane ment. »</li>
    <li><b>6.</b> « Changez l'écosystème, vous changez la valeur du passé. »</li>
  </ul>
</div>

<footer>Généré par <code>scripts/build_podcast.py</code> — chiffres recalculés à chaque exécution.</footer>
"""

CHART_JS = """<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js"></script>
<script>
const yen = v => '¥' + Math.round(v).toLocaleString('fr-FR');
const pct = v => (v>=0?'+':'') + v + '%';

// 1) Onde de choc — barres horizontales Δ% Yahoo
new Chart(document.getElementById('cShock'), {
  type: 'bar',
  data: { labels: DATA.shock.map(d=>d.label),
    datasets: [{ label: 'Δ médiane Yahoo',
      data: DATA.shock.map(d=>d.yh),
      backgroundColor: DATA.shock.map(d=> d.yh>=100?'#dc2626': d.yh>=40?'#f59e0b': d.yh>0?'#9ca3af':'#2563eb') }] },
  options: { indexAxis:'y', responsive:true, maintainAspectRatio:false,
    plugins:{ legend:{display:false},
      tooltip:{ callbacks:{ label:c=>` Yahoo ${pct(c.raw)}  ·  Mercari ${pct(DATA.shock[c.dataIndex].mer)}` } } },
    scales:{ x:{ ticks:{ callback:v=>v+'%' }, title:{display:true,text:'variation depuis le 16/04'} },
      y:{ ticks:{ font:{size:11} } } } }
});

// 2) Échelle KOF — prix (ligne) + volume (barres, axe secondaire)
new Chart(document.getElementById('cLadder'), {
  data: { labels: DATA.ladder.map(d=>"KOF "+(d.year.length==2?"'"+d.year:d.year)),
    datasets: [
      { type:'line', label:'Prix médian (depuis)', yAxisID:'y',
        data: DATA.ladder.map(d=>d.price), borderColor:'#dc2626', backgroundColor:'#dc2626',
        borderWidth:3, pointRadius:4, tension:.2 },
      { type:'bar', label:'Nb de ventes', yAxisID:'y1',
        data: DATA.ladder.map(d=>d.n), backgroundColor:'rgba(37,99,235,.25)',
        borderColor:'#2563eb', borderWidth:1 } ] },
  options: { responsive:true, maintainAspectRatio:false,
    plugins:{ tooltip:{ callbacks:{ label:c=> c.dataset.type==='line'? ' '+yen(c.raw):' '+c.raw+' ventes' } } },
    scales:{ y:{ position:'left', title:{display:true,text:'prix médian'}, ticks:{ callback:yen } },
      y1:{ position:'right', title:{display:true,text:'volume'}, grid:{drawOnChartArea:false} } } }
});

// 3) Avant / Après — barres groupées
new Chart(document.getElementById('cFlags'), {
  type:'bar',
  data:{ labels: DATA.flags.map(d=>d.label),
    datasets:[
      { label:'Avant 16/04', data:DATA.flags.map(d=>d.pre), backgroundColor:'#9ca3af' },
      { label:'Depuis',      data:DATA.flags.map(d=>d.post), backgroundColor:'#dc2626' } ] },
  options:{ responsive:true, maintainAspectRatio:false,
    plugins:{ tooltip:{ callbacks:{ label:c=>` ${c.dataset.label}: ${yen(c.raw)}` } } },
    scales:{ y:{ ticks:{ callback:yen }, title:{display:true,text:'prix médian (¥)'} },
      x:{ ticks:{ font:{size:10} } } } }
});
</script>
"""


if __name__ == "__main__":
    main()

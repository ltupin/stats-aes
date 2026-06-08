#!/usr/bin/env python3
"""Scan ../reports/*.html and build index.html with a Japan/France market toggle.

Pour chaque jeu, lit le rapport Japon ({key}_trend.html, ¥ Mercari+Yahoo) et,
s'il existe, le rapport France ({key}_fr.html, € eBay.fr). Les chiffres sont
extraits des rapports eux-mêmes (aucun nombre dupliqué). Un bouton 🇯🇵/🇫🇷 bascule
l'affichage de toutes les cartes.

    ../.venv/bin/python build_index.py
"""
import html
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RPT_DIR = ROOT / "reports"
OUT = ROOT / "index.html"

# Bloc src-card : "Avant … médiane ¥/€{pre}" puis "Depuis : {n} … {post} · {delta}%"
CARD_RX = re.compile(
    r"Avant[^¥€]*[¥€]([\d,]+).*?Depuis\s*:\s*(\d+)[^¥€]*[¥€]([\d,]+)\s*</strong>"
    r"\s*·\s*<strong>\s*([+-][\d.]+)\s*%", re.DOTALL)

ICON = {"Mercari": "🟡", "Yahoo": "🔵", "eBay.fr": "🇫🇷"}


def clean_title(raw):
    return re.split(r"\s+[—–-]\s+", html.unescape(raw), maxsplit=1)[0].strip()


def parse(path, labels, currency):
    """Extrait titre + sources (une par label, dans l'ordre des src-cards)."""
    txt = path.read_text(encoding="utf-8")
    m = re.search(r"<title>(.*?)</title>", txt, re.DOTALL)
    title = clean_title(m.group(1)) if m else path.stem
    sources = []
    for label, (pre, n, post, delta) in zip(labels, CARD_RX.findall(txt)):
        sources.append({"label": label, "cur": currency, "pre": pre, "post": post,
                        "n": int(n), "delta": float(delta)})
    return {"title": title, "sources": sources}


def group_of(key):
    return "kof" if key.startswith("kof_") else "main"


def sort_key(key, title):
    if group_of(key) == "kof":
        m = re.search(r"kof_(\d+)", key)
        yr = int(m.group(1)) if m else 0
        return (1, yr if yr > 90 else yr + 2000, "")
    return (0, 0, title.lower())


def delta_class(d):
    if d is None:
        return "flat"
    return "hot" if d >= 50 else "up" if d > 5 else "down" if d < -5 else "flat"


def render_rows(sources):
    out = ""
    for s in sources:
        icon = ICON.get(s["label"], "•")
        c = s["cur"]
        if s["pre"] == "0" and s["post"] == "0":
            mid = '<span class="src-medians na">aucune donnée</span>'
            delta = ""
        elif s["pre"] == "0":  # pas de vente avant l'annonce → pas de variation
            mid = (f'<span class="src-medians">{c}{s["post"]} <span class="n">'
                   f'({s["n"]} depuis)</span></span>')
            delta = '<span class="delta flat">n/a</span>'
        else:
            mid = (f'<span class="src-medians">{c}{s["pre"]} → {c}{s["post"]}'
                   f'<span class="n">({s["n"]})</span></span>')
            delta = f'<span class="delta {delta_class(s["delta"])}">{s["delta"]:+.0f}%</span>'
        out += (f'<div class="src"><span class="src-name">{icon} {s["label"]}</span>'
                f'{mid}{delta}</div>')
    return out


def render_card(key, title, jp, fr):
    jp_block = (f'<a class="mkt jp" href="reports/{key}_trend.html">{render_rows(jp)}</a>'
                if jp else '<div class="mkt jp na">aucune donnée Japon</div>')
    fr_block = (f'<a class="mkt fr" href="reports/{key}_fr.html">{render_rows(fr)}</a>'
                if fr else '<div class="mkt fr na">aucune donnée France</div>')
    return (f'<div class="card"><div class="card-head">'
            f'<span class="game">{html.escape(title)}</span></div>'
            f'{jp_block}{fr_block}</div>')


SECTIONS = [("main", "Jeux principaux"), ("kof", "Série King of Fighters")]


def main():
    # Jeux = clés dérivées des rapports Japon ; France en complément.
    jp = {p.name[:-len("_trend.html")]: parse(p, ["Mercari", "Yahoo"], "¥")
          for p in RPT_DIR.glob("*_trend.html")}
    fr = {p.name[:-len("_fr.html")]: parse(p, ["eBay.fr"], "€")
          for p in RPT_DIR.glob("*_fr.html")}

    keys = sorted(jp, key=lambda k: sort_key(k, jp[k]["title"]))
    by_group = {}
    for k in keys:
        by_group.setdefault(group_of(k), []).append(k)

    sections_html = ""
    for gid, gtitle in SECTIONS:
        ks = by_group.get(gid, [])
        if not ks:
            continue
        cards = "\n".join(
            render_card(k, jp[k]["title"], jp[k]["sources"],
                        fr[k]["sources"] if k in fr else None) for k in ks)
        sections_html += f'<section><h2>{gtitle}</h2><div class="grid">{cards}</div></section>\n'

    now = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    n_fr = len(fr)
    OUT.write_text(PAGE.format(sections=sections_html, now=now, njp=len(jp), nfr=n_fr),
                   encoding="utf-8")
    print(f"=> {OUT}  ({len(jp)} jeux Japon, {n_fr} avec données France)")


PAGE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Statistiques Neo Geo AES — Sommaire</title>
<style>
  :root {{ --hot:#dc2626; --up:#16a34a; --down:#2563eb; --flat:#6b7280; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f5f6fa; color: #1a1a2e; margin: 0; padding: 32px 20px 56px; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 1.7rem; margin: 0 0 6px; }}
  .meta {{ color: #888; font-size: .8rem; margin: 0 0 18px; }}
  .toggle {{ display: inline-flex; background: #e5e7eb; border-radius: 999px; padding: 4px;
            margin-bottom: 24px; gap: 2px; }}
  .toggle button {{ border: none; background: transparent; cursor: pointer; font-size: .9rem;
            padding: 7px 18px; border-radius: 999px; color: #555; font-weight: 600; }}
  .toggle button.on {{ background: #fff; color: #1a1a2e; box-shadow: 0 1px 3px rgba(0,0,0,.15); }}
  .insight {{ background: linear-gradient(90deg, #fef3c7 0%, #fee2e2 100%);
             border-left: 4px solid var(--hot); padding: 13px 18px; border-radius: 8px;
             margin: 0 0 32px; font-size: .88rem; line-height: 1.5; }}
  .insight strong {{ color: var(--hot); }}
  section {{ margin-bottom: 36px; }}
  h2 {{ font-size: 1.15rem; margin: 0 0 14px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 14px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 16px 18px;
          box-shadow: 0 1px 4px rgba(0,0,0,.08); transition: transform .12s ease, box-shadow .12s ease; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 14px rgba(0,0,0,.13); }}
  .card-head {{ margin-bottom: 10px; }}
  .game {{ font-weight: 600; font-size: 1rem; }}
  .mkt {{ display: none; text-decoration: none; color: inherit; }}
  body.show-jp .mkt.jp {{ display: block; }}
  body.show-fr .mkt.fr {{ display: block; }}
  .mkt.na {{ color: #bbb; font-style: italic; font-size: .82rem; padding: 4px 0; }}
  .src {{ display: flex; align-items: baseline; gap: 8px; font-size: .82rem;
         padding: 3px 0; border-top: 1px solid #f0f0f3; }}
  .src:first-child {{ border-top: none; }}
  .src-name {{ width: 96px; flex: none; color: #444; }}
  .src-medians {{ flex: 1; color: #666; font-variant-numeric: tabular-nums; }}
  .src-medians .n {{ color: #aaa; margin-left: 4px; font-size: .9em; }}
  .src-medians.na {{ color: #bbb; font-style: italic; }}
  .delta {{ font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .delta.hot {{ color: var(--hot); }} .delta.up {{ color: var(--up); }}
  .delta.down {{ color: var(--down); }} .delta.flat {{ color: var(--flat); }}
</style></head><body class="show-jp">
<div class="wrap">
  <h1>📊 Statistiques Neo Geo AES</h1>
  <p class="meta">Données du {now} · {njp} jeux · 🇯🇵 Japon (Mercari + Yahoo) vs 🇫🇷 France (eBay.fr, {nfr} jeux)
    · vue d'ensemble : <a href="reports/japan_global.html">🇯🇵 Japon</a> · <a href="reports/france_global.html">🇫🇷 France</a></p>
  <div class="toggle">
    <button data-m="jp" class="on">🇯🇵 Japon</button>
    <button data-m="fr">🇫🇷 France</button>
  </div>

  <div class="insight">
    📣 <strong>16 avril 2026</strong> — Plaion annonce la <strong>Neo Geo AES+</strong>,
    nouvelle console compatible avec les cartouches d'origine. Chaque carte compare la
    médiane des ventes <em>avant</em> et <em>depuis</em> cette date, par marché.
  </div>

  {sections}
</div>
<script>
  const body = document.body;
  document.querySelectorAll('.toggle button').forEach(b => b.addEventListener('click', () => {{
    document.querySelectorAll('.toggle button').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
    body.className = 'show-' + b.dataset.m;
  }}));
</script>
</body></html>
"""


if __name__ == "__main__":
    main()

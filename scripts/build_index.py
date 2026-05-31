#!/usr/bin/env python3
"""Scan ../reports/*.html and build a summary index.html at the repo root.

Extracts each report's title and the Plaion pre/post medians + deltas straight
from its insight box, so the index always reflects whatever the reports
currently say (no duplicated numbers to keep in sync).

    ../.venv/bin/python build_index.py
"""
import html
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RPT_DIR = ROOT / "reports"
OUT = ROOT / "index.html"

# A src-card block: "Avant … médiane ¥{pre}" then "Depuis : {n} … ¥{post} · {delta}%".
# Matches both the current pipeline reports and the KOF ones (same template).
CARD_RX = re.compile(
    r"Avant[^¥]*¥([\d,]+).*?Depuis\s*:\s*(\d+)[^¥]*¥([\d,]+)\s*</strong>"
    r"\s*·\s*<strong>\s*([+-][\d.]+)\s*%",
    re.DOTALL,
)
# Legacy mono-source reports ("médiane: +133.4%").
LEGACY_RX = re.compile(r"médiane:\s*([+-][\d.]+)\s*%")
SUB_RX = re.compile(r"Mercari\s+(\d+)\s+ventes\s*·\s*Yahoo\s+(\d+)\s+ventes")


def clean_title(raw):
    """'Fatal Fury Special AES — Mercari & Yahoo…' -> 'Fatal Fury Special AES'."""
    t = html.unescape(raw)
    return re.split(r"\s+[—–-]\s+", t, maxsplit=1)[0].strip()


def parse(path):
    txt = path.read_text(encoding="utf-8")
    m = re.search(r"<title>(.*?)</title>", txt, re.DOTALL)
    title = clean_title(m.group(1)) if m else path.stem
    cards = CARD_RX.findall(txt)  # [(pre, n, post, delta), …] Mercari then Yahoo
    sources = []
    for label, (pre, n, post, delta) in zip(("Mercari", "Yahoo"), cards):
        sources.append({"label": label, "pre": pre, "post": post,
                        "n": int(n), "delta": float(delta)})
    if not sources:  # legacy mono-source fallback
        lm = LEGACY_RX.search(txt)
        if lm:
            label = "Yahoo" if "yahoo" in path.name else "Mercari"
            sources.append({"label": label, "pre": None, "post": None,
                            "n": None, "delta": float(lm.group(1))})
    sub = SUB_RX.search(txt)
    total = (int(sub.group(1)) + int(sub.group(2))) if sub else None
    return {"file": path.name, "title": title, "sources": sources, "total": total}


# Grouping by filename. Order within each group is explicit where it matters.
def group_of(name):
    if name.startswith("kof_"):
        return "kof"
    if name.endswith("_only.html"):
        return "legacy"
    return "main"


def sort_key(rep):
    """Jeux principaux : ordre alphabétique par label. KOF : par année."""
    g = group_of(rep["file"])
    if g == "kof":
        m = re.search(r"kof_(\d+)", rep["file"])
        yr = int(m.group(1)) if m else 0
        return (1, yr if yr > 90 else yr + 2000, "")
    if g == "legacy":
        return (2, 0, rep["title"].lower())
    return (0, 0, rep["title"].lower())  # main, alphabétique


def delta_class(d):
    if d is None:
        return "flat"
    if d >= 50:
        return "hot"
    if d > 5:
        return "up"
    if d < -5:
        return "down"
    return "flat"


def render_card(rep):
    srcs = ""
    for s in rep["sources"]:
        icon = "🟡" if s["label"] == "Mercari" else "🔵"
        # Source sans aucune vente (ex. Yahoo géo-bloqué, jamais fetché).
        if s["pre"] == "0" and s["post"] == "0":
            srcs += (f'<div class="src"><span class="src-name">{icon} {s["label"]}</span>'
                     f'<span class="src-medians na">aucune donnée</span></div>')
            continue
        cls = delta_class(s["delta"])
        if s["pre"] is not None:
            line = (f'<span class="src-name">{icon} {s["label"]}</span>'
                    f'<span class="src-medians">¥{s["pre"]} → ¥{s["post"]}'
                    f'<span class="n">({s["n"]})</span></span>')
        else:
            line = f'<span class="src-name">{icon} {s["label"]}</span><span class="src-medians">médiane</span>'
        srcs += (f'<div class="src">{line}'
                 f'<span class="delta {cls}">{s["delta"]:+.0f}%</span></div>')
    if not rep["sources"]:
        srcs = '<div class="src"><span class="src-medians">—</span></div>'
    total = f'<span class="total">{rep["total"]} ventes</span>' if rep["total"] else ""
    return (f'<a class="card" href="reports/{rep["file"]}">'
            f'<div class="card-head"><span class="game">{html.escape(rep["title"])}</span>{total}</div>'
            f'<div class="srcs">{srcs}</div></a>')


SECTIONS = [
    ("main", "Jeux principaux", "Pipeline courant — Mercari + Yahoo, médiane glissante 3 semaines."),
    ("kof", "Série King of Fighters", "Vue globale + par opus (1994 → 2002)."),
]


def main():
    reports = sorted((parse(p) for p in RPT_DIR.glob("*.html")), key=sort_key)
    by_group = {}
    for r in reports:
        by_group.setdefault(group_of(r["file"]), []).append(r)

    sections_html = ""
    for gid, gtitle, gsub in SECTIONS:
        items = by_group.get(gid, [])
        if not items:
            continue
        cards = "\n".join(render_card(r) for r in items)
        sections_html += (f'<section><h2>{gtitle}</h2>'
                          f'<div class="grid">{cards}</div></section>\n')

    now = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    n = len(reports)
    OUT.write_text(PAGE.format(sections=sections_html, now=now, n=n), encoding="utf-8")
    print(f"=> {OUT}  ({n} rapports)")


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
  .lede {{ color: #555; font-size: .92rem; line-height: 1.5; margin: 0 0 8px; }}
  .meta {{ color: #888; font-size: .8rem; margin: 0 0 28px; }}
  .insight {{ background: linear-gradient(90deg, #fef3c7 0%, #fee2e2 100%);
             border-left: 4px solid var(--hot); padding: 13px 18px; border-radius: 8px;
             margin: 0 0 32px; font-size: .88rem; line-height: 1.5; }}
  .insight strong {{ color: var(--hot); }}
  section {{ margin-bottom: 36px; }}
  h2 {{ font-size: 1.15rem; margin: 0 0 2px; }}
  .sec-sub {{ color: #888; font-size: .82rem; margin: 0 0 14px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 14px; }}
  .card {{ display: block; background: #fff; border-radius: 12px; padding: 16px 18px;
          box-shadow: 0 1px 4px rgba(0,0,0,.08); text-decoration: none; color: inherit;
          transition: transform .12s ease, box-shadow .12s ease; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 14px rgba(0,0,0,.13); }}
  .card-head {{ display: flex; justify-content: space-between; align-items: baseline;
               gap: 8px; margin-bottom: 10px; }}
  .game {{ font-weight: 600; font-size: 1rem; }}
  .total {{ color: #999; font-size: .72rem; white-space: nowrap; }}
  .src {{ display: flex; align-items: baseline; gap: 8px; font-size: .82rem;
         padding: 3px 0; border-top: 1px solid #f0f0f3; }}
  .src:first-child {{ border-top: none; }}
  .src-name {{ width: 92px; flex: none; color: #444; }}
  .src-medians {{ flex: 1; color: #666; font-variant-numeric: tabular-nums; }}
  .src-medians .n {{ color: #aaa; margin-left: 4px; font-size: .9em; }}
  .src-medians.na {{ color: #bbb; font-style: italic; }}
  .delta {{ font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .delta.hot {{ color: var(--hot); }}
  .delta.up {{ color: var(--up); }}
  .delta.down {{ color: var(--down); }}
  .delta.flat {{ color: var(--flat); }}
  footer {{ color: #aaa; font-size: .78rem; margin-top: 40px; text-align: center; }}
  footer a {{ color: #888; }}
</style></head><body>
<div class="wrap">
  <h1>📊 Statistiques Neo Geo AES</h1>
  <p class="meta">Données du {now}</p>

  <div class="insight">
    📣 <strong>16 avril 2026</strong> — Plaion annonce la <strong>Neo Geo AES+</strong>,
    nouvelle console compatible avec les cartouches d'origine. Chaque rapport
    compare la médiane des ventes <em>avant</em> et <em>depuis</em> cette date.
  </div>

  {sections}
</div>
</body></html>
"""


if __name__ == "__main__":
    main()

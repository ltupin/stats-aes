#!/usr/bin/env python3
"""Sonde des jeux Neo Geo AES candidats et mesure leur cadence de ventes/semaine
sur 2026, pour repérer ceux qui « sortent » assez (≥ TARGET/sem).

N'écrit RIEN dans data/raw : tout est mesuré en mémoire. Réutilise les filtres
de report.py (plancher prix, exclusions communes, CD, lots…).

    ../.venv/bin/python discover.py            # tous les candidats
    ../.venv/bin/python discover.py samsho2    # un seul
"""
import re, sys
from datetime import datetime, timezone

import fetch
import report

TARGET = 5.0  # ventes/semaine visées
NOW = datetime.now(timezone.utc)
WEEKS = max(1.0, (NOW - report.START).days / 7.0)


def _clean(title):
    """Reprend les exclusions génériques de report.keep (hors INCLUDE/EXCLUDE_GAME)."""
    tl = title.lower()
    if report.SET_RX.search(title) or report.NB_HON_RX.search(title) \
       or report.BOX_ONLY_RX.search(title) or report.CD_RX.search(title):
        return False
    return not any(e in tl for e in report.EXCLUDE_COMMON_LC)


def count(items_mer, items_yh, inc, exg):
    exg = [e.lower() for e in exg]

    def ok(title):
        if not inc.search(title):
            return False
        if not _clean(title):
            return False
        tl = title.lower()
        return not any(e in tl for e in exg)

    mer = 0
    for it in items_mer:
        if "SOLD_OUT" not in (it.get("status") or ""):
            continue
        try:
            p = int(it.get("price"))
        except Exception:
            continue
        if p < report.PRICE_FLOOR:
            continue
        try:
            dt = datetime.fromtimestamp(int(it.get("created")), tz=timezone.utc)
        except Exception:
            continue
        if dt < report.START:
            continue
        if ok((it.get("name") or "")):
            mer += 1
    yh = 0
    for it in items_yh:
        if (it.get("bidCount") or 0) < 1 and not it.get("isFixedPrice"):
            continue  # enchère sans offre = invendu
        p = it.get("price") or it.get("buyNowPrice") or 0
        try:
            p = int(p)
        except Exception:
            continue
        if p < report.PRICE_FLOOR:
            continue
        try:
            dt = datetime.fromisoformat(it.get("endTime", "")).astimezone(timezone.utc)
        except Exception:
            continue
        if dt < report.START:
            continue
        if ok((it.get("title") or "")):
            yh += 1
    return mer, yh


# Candidats : (clé, label, mots-clés Mercari/Yahoo, INCLUDE, EXCLUDE versions/franchises)
_SNK_OTHERS = ["キングオブファイターズ", "KOF", "King of Fighters", "メタルスラッグ",
               "Metal Slug"]
CANDIDATES = [
    ("samsho2", "Samurai Shodown 2 (真サムライスピリッツ)", "真サムライスピリッツ ネオジオ",
     "真サムライスピリッツ", re.compile(r"真[\s　]*サムライスピリッツ|真[\s　]*侍魂|SAMURAI\s*SHODOWN\s*(?:2|II)", re.I),
     ["サムライスピリッツ3", "サムライスピリッツ4", "斬紅郎", "天草降臨", "零", "ゼロ", "六番勝負"] + _SNK_OTHERS),
    ("ff1", "Fatal Fury 1 (餓狼伝説)", "餓狼伝説 ネオジオ", "餓狼伝説",
     re.compile(r"餓狼伝説(?![\s　]*[2-9２-９]|[\s　]*スペシャル|[\s　]*SPECIAL|[\s　]*III|[\s　]*II)", re.I),
     ["餓狼伝説2", "餓狼伝説3", "スペシャル", "SPECIAL", "リアルバウト", "Real Bout", "MARK OF THE WOLVES",
      "餓狼 MARK", "ウルブズ"] + _SNK_OTHERS),
    ("rbff", "Real Bout Fatal Fury (リアルバウト餓狼伝説)", "リアルバウト餓狼伝説 ネオジオ",
     "リアルバウト餓狼伝説", re.compile(r"リアルバウト|Real\s*Bout|REALBOUT", re.I),
     _SNK_OTHERS),
    ("lastblade", "The Last Blade (月華の剣士)", "月華の剣士 ネオジオ", "月華の剣士",
     re.compile(r"月華の剣士|Last\s*Blade", re.I), ["月華の剣士2", "月華の剣士 2"] + _SNK_OTHERS),
    ("aof2", "Art of Fighting 2 (龍虎の拳2)", "龍虎の拳2 ネオジオ", "龍虎の拳2",
     re.compile(r"龍虎の拳[\s　]*[2２]|Art\s*of\s*Fighting\s*2", re.I),
     ["龍虎の拳3", "龍虎外伝"] + _SNK_OTHERS),
    ("worldheroes2", "World Heroes 2 (ワールドヒーローズ2)", "ワールドヒーローズ2 ネオジオ",
     "ワールドヒーローズ2", re.compile(r"ワールドヒーローズ[\s　]*[2２]", re.I),
     ["ワールドヒーローズ2JET", "パーフェクト", "ジェット"] + _SNK_OTHERS),
    ("kotm", "King of the Monsters (キングオブザモンスターズ)", "キングオブザモンスターズ ネオジオ",
     "キングオブザモンスターズ", re.compile(r"キングオブザモンスターズ|King\s*of\s*the\s*Monsters", re.I),
     _SNK_OTHERS),
    ("magicianlord", "Magician Lord (マジシャンロード)", "マジシャンロード ネオジオ", "マジシャンロード",
     re.compile(r"マジシャンロード|Magician\s*Lord", re.I), _SNK_OTHERS),
    ("windjammers", "Windjammers (フライングパワーディスク)", "フライングパワーディスク ネオジオ",
     "フライングパワーディスク", re.compile(r"フライングパワーディスク|Windjammers", re.I), _SNK_OTHERS),
    ("blazingstar", "Blazing Star (ブレイジングスター)", "ブレイジングスター ネオジオ", "ブレイジングスター",
     re.compile(r"ブレイジングスター|Blazing\s*Star", re.I), _SNK_OTHERS),
]


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    cands = [c for c in CANDIDATES if not only or c[0] in only]
    print(f"Période : {report.START.date()} → {NOW.date()}  ({WEEKS:.1f} semaines)")
    print(f"Cible : ≥ {TARGET:.0f} ventes/semaine (Mercari SOLD_OUT + Yahoo vendus)\n")
    print(f"{'jeu':<42}{'Mer':>5}{'Yh':>5}{'tot':>5}{'/sem':>7}  verdict")
    print("-" * 76)
    rows = []
    for key, label, mkw, ykw, inc, exg in cands:
        import asyncio
        mer = asyncio.run(fetch.fetch_mercari(mkw))
        yh, _, blocked = fetch.fetch_yahoo(ykw)
        cm, cy = count(mer, yh, inc, exg)
        tot = cm + cy
        per = tot / WEEKS
        verdict = "✅" if per >= TARGET else "·"
        if blocked:
            verdict = "🚧 Yahoo bloqué"
        rows.append((per, label, cm, cy, tot, verdict))
        print(f"{label:<42}{cm:>5}{cy:>5}{tot:>5}{per:>7.1f}  {verdict}")
    print("\nClassement (par ventes/semaine) :")
    for per, label, cm, cy, tot, verdict in sorted(rows, reverse=True):
        print(f"  {per:>5.1f}/sem  {verdict:<3} {label}")


if __name__ == "__main__":
    main()

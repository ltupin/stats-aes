#!/usr/bin/env python3
"""Interactive validation of fetched listings — drop false positives.

Reads data/raw/KEY_*.csv (post-filter via report.gather), surfaces suspect
items, prompts the user to keep/drop each. Drops are appended to
data/exclude_urls/KEY.txt so they persist across re-fetches.

Usage:
    ../.venv/bin/python validate.py KEY                # outliers only
    ../.venv/bin/python validate.py KEY --all          # review every kept item
    ../.venv/bin/python validate.py KEY --low          # only suspect low prices
    ../.venv/bin/python validate.py KEY --high         # only suspect high prices

After validation, re-run `report.py KEY` to regenerate the HTML with the
new exclusions applied.
"""
import argparse, statistics, sys, webbrowser
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXC_DIR = ROOT / "data" / "exclude_urls"

# Reuse report.py's filter + gather logic so the suspect list matches exactly
# what would land in the HTML.
import report

# Outlier thresholds — relative to median price across all kept items.
HIGH_RATIO = 2.0   # > 2× median → suspect (often a different bundle/limited ed.)
LOW_RATIO  = 0.5   # < 0.5× median → suspect (often loose, manual-only, port)


def classify(points):
    """Return dict: high outliers, low outliers, normal (sorted by date)."""
    if not points:
        return {"high": [], "low": [], "normal": []}
    prices = sorted(p["y"] for p in points)
    med = statistics.median(prices)
    high = [p for p in points if p["y"] > HIGH_RATIO * med]
    low  = [p for p in points if p["y"] < LOW_RATIO  * med]
    normal = [p for p in points if LOW_RATIO * med <= p["y"] <= HIGH_RATIO * med]
    for lst in (high, low, normal):
        lst.sort(key=lambda x: x["x"])
    return {"high": high, "low": low, "normal": normal, "median": med}


def fmt_date(epoch_ms):
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def append_drops(key, urls, reason=""):
    """Append URLs to data/exclude_urls/KEY.txt, idempotent."""
    if not urls:
        return
    EXC_DIR.mkdir(parents=True, exist_ok=True)
    path = EXC_DIR / f"{key}.txt"
    existing = report.load_exclude_urls(key)
    new = [u for u in urls if u not in existing]
    if not new:
        return
    with open(path, "a", encoding="utf-8") as f:
        if reason:
            f.write(f"\n# {reason} (validate.py, {datetime.now().strftime('%Y-%m-%d %H:%M')})\n")
        for u in new:
            f.write(f"{u}\n")
    print(f"  → {len(new)} URL(s) ajoutée(s) à {path.relative_to(ROOT)}")


def prompt_loop(items, median, open_browser):
    """Walk the user through items. Returns the list of URLs to drop."""
    to_drop = []
    skipped = 0
    print()
    print("Commandes : [k]eep   [d]rop   [o]pen URL (navigateur)   [s]kip   [q]uit\n")
    for i, p in enumerate(items, 1):
        src   = "🟡 Mercari" if p["source"] == "mercari" else "🔵 Yahoo"
        ratio = p["y"] / median if median else 0
        ratio_lbl = f"{ratio:.2f}× médiane"
        if ratio >= HIGH_RATIO:
            ratio_lbl += " ⚠️  HIGH"
        elif ratio <= LOW_RATIO:
            ratio_lbl += " ⚠️  LOW"

        print(f"[{i}/{len(items)}] {src}  ¥{p['y']:,}  {fmt_date(p['x'])}  ({ratio_lbl})")
        print(f"   {p['name'][:110]}")
        print(f"   {p['url']}")
        if open_browser:
            webbrowser.open(p["url"], new=2)

        while True:
            try:
                choice = input("   → [k/d/o/s/q] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n(interrompu)")
                return to_drop, skipped
            if choice in ("k", "keep", ""):
                print("   ✓ gardé")
                break
            if choice in ("d", "drop"):
                print("   ✗ droppé")
                to_drop.append(p["url"])
                break
            if choice in ("o", "open"):
                webbrowser.open(p["url"], new=2)
                print("   (ouvert dans le navigateur — choisis ensuite k/d/s/q)")
                continue
            if choice in ("s", "skip"):
                print("   — skippé")
                skipped += 1
                break
            if choice in ("q", "quit"):
                print("(arrêt — décisions partielles sauvegardées)")
                return to_drop, skipped
            print("   ?  entrée invalide (k/d/o/s/q)")
        print()
    return to_drop, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("key", help="game key (see GAMES in report.py)")
    ap.add_argument("--all",  action="store_true", help="review every kept item (not only outliers)")
    ap.add_argument("--low",  action="store_true", help="only items < 0.5× median")
    ap.add_argument("--high", action="store_true", help="only items > 2× median")
    ap.add_argument("--no-browser", action="store_true", help="ne pas auto-ouvrir l'URL")
    args = ap.parse_args()

    if args.key not in report.GAMES:
        print(f"unknown key: {args.key} (have: {', '.join(report.GAMES)})", file=sys.stderr)
        sys.exit(2)

    cfg = report.GAMES[args.key]
    mer, yh = report.gather(args.key, cfg)
    all_items = mer + yh
    if not all_items:
        print(f"{cfg['label']} : aucun item après filtre. Vérifier d'abord les keywords/INCLUDE.")
        return

    c = classify(all_items)
    median = c["median"]
    print(f"\n=== {cfg['label']} ===")
    print(f"  Total kept  : {len(all_items)} (Mercari {len(mer)} + Yahoo {len(yh)})")
    print(f"  Médiane     : ¥{int(median):,}")
    print(f"  Outliers ↑  : {len(c['high'])}  (> {HIGH_RATIO}× médiane = > ¥{int(median*HIGH_RATIO):,})")
    print(f"  Outliers ↓  : {len(c['low'])}   (< {LOW_RATIO}× médiane = < ¥{int(median*LOW_RATIO):,})")

    if args.all:
        review = c["high"] + c["normal"] + c["low"]
        what = "TOUS les items"
    elif args.low:
        review = c["low"]
        what = f"items < {LOW_RATIO}× médiane"
    elif args.high:
        review = c["high"]
        what = f"items > {HIGH_RATIO}× médiane"
    else:
        review = c["high"] + c["low"]
        what = "outliers (haut + bas)"

    if not review:
        print(f"\n  → 0 item à reviewer dans le mode {what!r}. Rien à faire.")
        return

    print(f"\n  → {len(review)} item(s) à reviewer ({what})")

    to_drop, skipped = prompt_loop(review, median, open_browser=not args.no_browser)

    print(f"\n=== Résumé ===")
    print(f"  Reviewed : {len(review)}")
    print(f"  Dropped  : {len(to_drop)}")
    print(f"  Skipped  : {skipped}")
    print(f"  Kept     : {len(review) - len(to_drop) - skipped}")

    if to_drop:
        append_drops(args.key, to_drop, reason=f"validate.py review ({what})")
        print(f"\n  → Re-lance maintenant le report :")
        print(f"     ../.venv/bin/python report.py {args.key}")


if __name__ == "__main__":
    main()

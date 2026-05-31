#!/usr/bin/env python3
"""Collecteur cumulatif des ventes TERMINÉES eBay.fr (marché France, en €).

Pilote le Chrome installé via Playwright (profil persistant — tu te connectes
toi-même si eBay le demande), navigation lente. Écrit data/raw/{key}_ebay_fr.csv
en FUSION cumulative (clé = URL) : la base ne fait que grandir.

    ../.venv/bin/python ebay_fetch.py samsho1 samsho2
    ../.venv/bin/python ebay_fetch.py --all
    ../.venv/bin/python ebay_fetch.py --all --pages 2
"""
import argparse, csv, random, re, sys, time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROFILE = str(Path.home() / ".cache" / "ebay-probe-profile")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADER = ["Titre", "URL", "Prix", "Date"]
URL_COL = 1

# Mots-clés eBay (latins) par clé RAW. Les versions KOF partagent la clé "kof".
EBAY_KW = {
    "samsho1": "Samurai Shodown Neo Geo AES",
    "samsho2": "Samurai Shodown 2 Neo Geo AES",
    "aof":     "Art of Fighting Neo Geo AES",
    "aof2":    "Art of Fighting 2 Neo Geo AES",
    "ffs":     "Fatal Fury Special Neo Geo AES",
    "ff1":     "Fatal Fury Neo Geo AES",
    "ff2":     "Fatal Fury 2 Neo Geo AES",
    "ff3":     "Fatal Fury 3 Neo Geo AES",
    "wh2":     "World Heroes 2 Neo Geo AES",
    "kof":     "King of Fighters Neo Geo AES",
}

JS_EXTRACT = r"""() => {
  const out = [];
  for (const c of document.querySelectorAll('li.s-item, li.s-card, .s-item')) {
    const t = c.querySelector('.s-item__title, .s-card__title, [class*="title"]');
    const p = c.querySelector('.s-item__price, .s-card__price, [class*="price"]');
    const cap = c.querySelector('.s-item__caption, .s-card__caption, [class*="caption"]');
    const a = c.querySelector('a.s-item__link, a.s-card__link, a[href*="/itm/"]');
    const title = t ? t.innerText.trim() : '';
    if (!title || /Shop on eBay|results|Résultats/i.test(title)) continue;
    out.push({ title, price: p?p.innerText.trim():'', caption: cap?cap.innerText.trim():'',
               url: a?a.href.split('?')[0]:'' });
  }
  return out;
}"""

_FR_MONTHS = {"janv": 1, "févr": 2, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
              "juil": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12}


def parse_price_eur(txt):
    """'199,00 EUR' / '1 199,00 EUR' / '12,00 à 30,00 EUR' -> int euros (premier prix)."""
    m = re.search(r"([\d  .,]+)", txt.replace("EUR", "").replace("€", ""))
    if not m:
        return None
    s = m.group(1).strip().replace(" ", "").replace(" ", "")
    # format FR : virgule décimale, point milliers
    s = s.replace(".", "").replace(",", ".")
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def parse_fr_date(caption):
    """'Vendu le 24 mai 2026' -> '2026-05-24' (ou '' si non reconnu)."""
    m = re.search(r"(\d{1,2})\s+([A-Za-zàûéèç.]+)\.?\s+(\d{4})", caption)
    if not m:
        return ""
    day, mon, year = m.group(1), m.group(2).lower().strip(".")[:4], m.group(3)
    mon = mon.replace("é", "e").replace("è", "e").replace("û", "u").replace("à", "a")
    key = {"janv": 1, "fevr": 2, "mars": 3, "avri": 4, "mai": 5, "juin": 6, "juil": 7,
           "aout": 8, "sept": 9, "octo": 10, "nove": 11, "dece": 12}.get(mon[:4])
    if not key:
        return ""
    return f"{year}-{key:02d}-{int(day):02d}"


def human_pause(a=1.5, b=3.5):
    time.sleep(random.uniform(a, b))


def fetch_ebay_fr(keyword, pages, ctx):
    page = ctx.new_page()
    rows, seen = [], set()
    for pg in range(1, pages + 1):
        url = (f"https://www.ebay.fr/sch/i.html?_nkw={keyword.replace(' ', '+')}"
               f"&LH_Sold=1&LH_Complete=1&_ipg=60&_pgn={pg}&rt=nc")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        human_pause(2, 4)
        for _ in range(3):
            page.mouse.wheel(0, 1800); human_pause(0.5, 1.2)
        if re.search(r"(Error Page|Pardon our interruption|captcha|robot)", page.title(), re.I):
            page.goto(url, wait_until="domcontentloaded", timeout=45000); human_pause(2, 4)
        got = page.evaluate(JS_EXTRACT)
        new = 0
        for r in got:
            if r["url"] and r["url"] not in seen:
                seen.add(r["url"]); rows.append(r); new += 1
        print(f"     page {pg}: +{new} (cumul {len(rows)})")
        if new == 0:
            break
        human_pause(2.5, 5)
    page.close()
    return rows


_SUFFIX_RX = re.compile(
    r"\s*(La page s'ouvre dans une nouvelle fen.tre.*$|Opens in a new window or tab.*$)", re.I)


def clean_title(t):
    return _SUFFIX_RX.sub("", (t or "")).replace("\n", " ").replace(";", ",").strip()


def to_csv_rows(items):
    out = []
    for it in items:
        price = parse_price_eur(it.get("price", ""))
        if price is None:
            continue
        date = parse_fr_date(it.get("caption", ""))
        out.append([clean_title(it.get("title", "")), it.get("url", ""),
                    f"€{price:,}".replace(",", " "), date])
    return out


def merge_write(path, new_rows):
    by_url, order = {}, []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            rd = csv.reader(f, delimiter=";"); next(rd, None)
            for row in rd:
                if len(row) <= URL_COL:
                    continue
                k = row[URL_COL]
                if k not in by_url:
                    order.append(k)
                by_url[k] = row
    added = 0
    for row in new_rows:
        k = row[URL_COL]
        if not k:
            continue
        if k not in by_url:
            order.append(k); added += 1
        by_url[k] = row
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(HEADER)
        for k in order:
            w.writerow(by_url[k])
    return len(order), added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*", help="clés RAW (voir EBAY_KW) ; vide + --all = toutes")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--pages", type=int, default=2)
    args = ap.parse_args()
    keys = list(EBAY_KW) if args.all else args.keys
    keys = [k for k in keys if k in EBAY_KW] or (list(EBAY_KW) if args.all else [])
    if not keys:
        print(f"usage: ebay_fetch.py KEY...  (dispo: {', '.join(EBAY_KW)})", file=sys.stderr)
        sys.exit(2)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            PROFILE, channel="chrome", headless=False, user_agent=UA,
            locale="fr-FR", viewport={"width": 1360, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        for k in keys:
            print(f"\n=== {k} — eBay.fr — '{EBAY_KW[k]}' ===")
            items = fetch_ebay_fr(EBAY_KW[k], args.pages, ctx)
            rows = to_csv_rows(items)
            total, added = merge_write(RAW_DIR / f"{k}_ebay_fr.csv", rows)
            print(f"  => data/raw/{k}_ebay_fr.csv  ({total} lignes, +{added} nouvelles)")
            human_pause(3, 6)
        ctx.close()


if __name__ == "__main__":
    main()

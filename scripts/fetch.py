#!/usr/bin/env python3
"""Fetch Mercari (sold-out) + Yahoo Auctions (closed) for a game keyword.

Usage:
    ../.venv/bin/python fetch.py KEY "MERCARI_KW" "YAHOO_KW"

Writes ../data/raw/KEY_mercari.csv and ../data/raw/KEY_yahoo.csv.

Auto-paginates: Mercari via pageToken (up to ~25 pages × 120 = 3000 items),
Yahoo via offset b= (up to 40 pages × 50 = 2000 items, polite 1s delay).
"""
import asyncio, csv, json, re, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from time import time as now
from urllib.parse import quote

import httpx
from ecdsa import NIST256p, SigningKey
from jose import jws
from jose.backends.ecdsa_backend import ECDSAECKey
from jose.constants import ALGORITHMS

URL_M = "https://api.mercari.jp/v2/entities:search"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def _dpop(url, method, key):
    ec = ECDSAECKey(key, ALGORITHMS.ES256)
    return jws.sign(
        {"iat": int(now()), "jti": str(uuid.uuid4()), "htu": url, "htm": method,
         "uuid": str(uuid.uuid4())},
        key,
        {"typ": "dpop+jwt", "alg": "ES256",
         "jwk": {k: ec.to_dict()[k] for k in ["crv", "kty", "x", "y"]}},
        ALGORITHMS.ES256,
    )


def _mer_body(kw, tk=""):
    return {
        "userId": "", "pageSize": 120, "pageToken": tk,
        "searchSessionId": uuid.uuid4().hex,
        "indexRouting": "INDEX_ROUTING_UNSPECIFIED", "thumbnailTypes": [],
        "searchCondition": {
            "keyword": kw, "sort": "SORT_CREATED_TIME", "order": "ORDER_DESC",
            "status": ["STATUS_ON_SALE", "STATUS_TRADING", "STATUS_SOLD_OUT"],
            "sizeId": [], "categoryId": [], "brandId": [], "sellerId": [],
            "priceMin": 0, "priceMax": 0, "itemConditionId": [],
            "shippingPayerId": [], "shippingFromArea": [], "shippingMethod": [],
            "colorId": [], "hasCoupon": False, "attributes": [],
            "itemTypes": [], "skuIds": [], "excludeKeyword": "",
        },
        "defaultDatasets": [], "serviceFrom": "suruga",
    }


async def fetch_mercari(keyword):
    seen, items, tk = set(), [], ""
    async with httpx.AsyncClient() as c:
        for _ in range(80):  # 80×120 = 9600 max ; s'arrête au dernier pageToken
            key = SigningKey.generate(NIST256p)
            r = await c.post(URL_M, json=_mer_body(keyword, tk),
                             headers={"User-Agent": UA, "X-Platform": "web",
                                      "DPoP": _dpop(URL_M, "POST", key)}, timeout=20)
            r.raise_for_status()
            d = r.json()
            pg = d.get("items", []) or []
            for it in pg:
                iid = it.get("id")
                if iid and iid not in seen:
                    seen.add(iid); items.append(it)
            tk = (d.get("meta") or {}).get("nextPageToken", "") or ""
            if not pg or not tk:
                break
            await asyncio.sleep(0.4)
    return items


def fetch_yahoo(keyword):
    encoded = quote(keyword)
    seen, items = set(), []
    total = None
    blocked = False
    with httpx.Client(headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.9"},
                     timeout=20, follow_redirects=True) as c:
        start = 1
        for _ in range(400):  # 400×50 = 20000 max ; s'arrête à totalResultsAvailable
            url = (f"https://auctions.yahoo.co.jp/closedsearch/closedsearch"
                   f"?p={encoded}&va={encoded}&b={start}&n=50&s1=end&o1=d")
            r = c.get(url)
            if r.status_code != 200:
                # 403 + EEA/UK notice = geo-block (need a JP network/proxy).
                if r.status_code == 403 and ("EEA" in r.text or "欧州経済領域" in r.text):
                    blocked = True
                break
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                          r.text, re.DOTALL)
            if not m:
                break
            d = json.loads(m.group(1))
            try:
                listing = d["props"]["pageProps"]["initialState"]["search"]["items"]["listing"]
            except KeyError:
                break
            pg = listing.get("items", [])
            if total is None:
                total = listing.get("totalResultsAvailable", 0)
            new = 0
            for it in pg:
                aid = it.get("auctionId")
                if aid and aid not in seen:
                    seen.add(aid); items.append(it); new += 1
            if not pg or new == 0:
                break
            if total and len(items) >= total:
                break
            start += 50
            time.sleep(1.0)
    return items, total, blocked


MER_HEADER = ["Titre", "URL", "Prix", "Statut", "Created", "Description"]
YH_HEADER  = ["Titre", "URL", "Prix", "BidCount", "Type", "EndDate"]
URL_COL = 1  # colonne clé (URL) dans les deux schémas — sert au dédoublonnage


def _clean_desc(s):
    return (s or "").replace("\n", " ").replace("\r", " ").replace(";", ",")[:300]


def read_existing_mer_desc(path):
    """{url: description} déjà stockées (pour ne pas re-fetcher le détail)."""
    out = {}
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            rd = csv.reader(f, delimiter=";"); next(rd, None)
            for row in rd:
                if len(row) > 5 and row[5]:
                    out[row[1]] = row[5]
    return out


async def fetch_descriptions(ids, concurrency=6):
    """Récupère la description (page détail) pour une liste d'item ids."""
    out = {}
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as c:
        async def one(iid):
            url = f"https://api.mercari.jp/items/get?id={iid}"
            key = SigningKey.generate(NIST256p)
            try:
                async with sem:
                    r = await c.get(url, headers={"User-Agent": UA, "X-Platform": "web",
                                                  "DPoP": _dpop(url, "GET", key)}, timeout=20)
                out[iid] = ((r.json().get("data") or {}).get("description") or "")
            except Exception:
                out[iid] = ""
        await asyncio.gather(*[one(i) for i in ids])
    return out


def mercari_rows(items, desc=None):
    desc = desc or {}
    rows = []
    for it in items:
        name = (it.get("name", "") or "").replace("\n", " ").replace(";", ",")
        url = f"https://jp.mercari.com/item/{it.get('id', '')}"
        try:
            ps = f"¥{int(it.get('price')):,}"
        except Exception:
            ps = ""
        status = (it.get("status", "") or "").replace("ITEM_STATUS_", "")
        try:
            cs = datetime.fromtimestamp(int(it.get("created")), tz=timezone.utc)\
                         .strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            cs = ""
        rows.append([name, url, ps, status, cs, _clean_desc(desc.get(url, ""))])
    return rows


def yahoo_rows(items):
    rows = []
    for it in items:
        title = (it.get("title", "") or "").replace("\n", " ").replace(";", ",")
        url = f"https://page.auctions.yahoo.co.jp/jp/auction/{it.get('auctionId', '')}"
        price = it.get("price") or it.get("buyNowPrice") or 0
        try:
            ps = f"¥{int(price):,}"
        except Exception:
            ps = ""
        bid = it.get("bidCount", 0)
        kind = "Buy-Now" if it.get("isFixedPrice") else "Auction"
        end = it.get("endTime", "")
        try:
            end_str = datetime.fromisoformat(end).strftime("%Y-%m-%d %H:%M %z")
        except Exception:
            end_str = end
        rows.append([title, url, ps, bid, kind, end_str])
    return rows


def merge_write(path, header, new_rows):
    """Fusion cumulative : conserve toutes les lignes déjà présentes, ajoute les
    nouvelles (clé = URL), et met à jour les lignes existantes avec les données
    fraîches. Ne supprime JAMAIS rien → la base ne fait que grandir.

    Retourne (total, added) : nb de lignes après fusion, dont nouvelles."""
    by_url, order = {}, []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            rd = csv.reader(f, delimiter=";")
            next(rd, None)  # header
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
        if k not in by_url:
            order.append(k); added += 1
        by_url[k] = row  # données fraîches gagnent (ex. statut Mercari mis à jour)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        for k in order:
            w.writerow(by_url[k])
    return len(order), added


def _save(path, rows, header, label, note=""):
    """Fusionne les lignes fetchées dans le CSV existant (cumulatif).

    Si 0 ligne fetchée (ex. Yahoo bloqué), on ne touche pas au fichier : la base
    existante est préservée telle quelle."""
    if not rows:
        if path.exists():
            print(f"  ⚠️  {label}: 0 item{note} — base existante préservée "
                  f"({path.name}, inchangée).", file=sys.stderr)
        else:
            print(f"  ⚠️  {label}: 0 item{note} — rien à écrire (pas de base).",
                  file=sys.stderr)
        return
    total, added = merge_write(path, header, rows)
    print(f"=> {path}  ({total} lignes, +{added} nouvelles)")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Fetch Mercari + Yahoo for a game key "
                                             "(fusion cumulative dans data/raw).")
    ap.add_argument("key")
    ap.add_argument("mercari_kw")
    ap.add_argument("yahoo_kw")
    ap.add_argument("--source", choices=["both", "mercari", "yahoo"], default="both",
                    help="ne collecter qu'une source (ex. mercari sur IP FR, yahoo sur IP JP)")
    args = ap.parse_args()
    key, mer_kw, yh_kw = args.key, args.mercari_kw, args.yahoo_kw
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== {key} ===")

    if args.source in ("both", "mercari"):
        print(f"Mercari keyword: {mer_kw}")
        t0 = time.time()
        try:
            mer = asyncio.run(fetch_mercari(mer_kw))
            print(f"  → {len(mer)} items in {time.time()-t0:.1f}s")
        except Exception as e:
            mer = []
            print(f"  ⚠️ Mercari indisponible ({type(e).__name__}) — base préservée.",
                  file=sys.stderr)
        mer_path = RAW_DIR / f"{key}_mercari.csv"
        descmap = read_existing_mer_desc(mer_path)  # cache des descriptions déjà connues
        # descriptions à récupérer : items VENDUS/EN TRANSACTION encore sans description
        need = []
        for it in mer:
            url = f"https://jp.mercari.com/item/{it.get('id', '')}"
            st = (it.get("status", "") or "").upper()
            if ("SOLD" in st or "TRADING" in st) and not descmap.get(url):
                need.append(it.get("id"))
        if need:
            print(f"  …descriptions à récupérer : {len(need)}")
            fetched = asyncio.run(fetch_descriptions(need))
            for it in mer:
                iid = it.get("id"); url = f"https://jp.mercari.com/item/{iid}"
                if fetched.get(iid):
                    descmap[url] = _clean_desc(fetched[iid])
        _save(mer_path, mercari_rows(mer, descmap), MER_HEADER, "Mercari")

    if args.source in ("both", "yahoo"):
        print(f"Yahoo   keyword: {yh_kw}")
        t0 = time.time()
        try:
            yh, total, blocked = fetch_yahoo(yh_kw)
            print(f"  → {len(yh)}/{total} items in {time.time()-t0:.1f}s")
        except Exception as e:
            yh, total, blocked = [], None, False
            print(f"  ⚠️ Yahoo indisponible ({type(e).__name__}) — base préservée.",
                  file=sys.stderr)
        if blocked:
            print("  🚧 Yahoo géo-bloqué (HTTP 403, EEE/UK) — passe par un proxy/VPN "
                  "japonais. Données Yahoo existantes préservées.", file=sys.stderr)
        _save(RAW_DIR / f"{key}_yahoo.csv", yahoo_rows(yh), YH_HEADER, "Yahoo",
              note=" (bloqué)" if blocked else "")


if __name__ == "__main__":
    main()

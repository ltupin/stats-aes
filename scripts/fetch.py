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
        for _ in range(25):
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
        for _ in range(40):
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


def write_mercari_csv(path, items):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Titre", "URL", "Prix", "Statut", "Created"])
        for it in items:
            name = (it.get("name", "") or "").replace("\n", " ").replace(";", ",")
            iid = it.get("id", "")
            url = f"https://jp.mercari.com/item/{iid}"
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
            w.writerow([name, url, ps, status, cs])


def write_yahoo_csv(path, items):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Titre", "URL", "Prix", "BidCount", "Type", "EndDate"])
        for it in items:
            title = (it.get("title", "") or "").replace("\n", " ").replace(";", ",")
            aid = it.get("auctionId", "")
            url = f"https://page.auctions.yahoo.co.jp/jp/auction/{aid}"
            price = it.get("price") or it.get("buyNowPrice") or 0
            try:
                ps = f"¥{int(price):,}"
            except Exception:
                ps = ""
            bid = it.get("bidCount", 0)
            kind = "Buy-Now" if it.get("isFixedPrice") else "Auction"
            end = it.get("endTime", "")
            try:
                dt = datetime.fromisoformat(end)
                end_str = dt.strftime("%Y-%m-%d %H:%M %z")
            except Exception:
                end_str = end
            w.writerow([title, url, ps, bid, kind, end_str])


def _save(path, items, writer, label, force, note=""):
    """Write items unless empty — an empty result would clobber prior data.

    Returns True if written. With force=True, writes even when empty (use for a
    game that genuinely has 0 sales)."""
    if not items and not force:
        exists = path.exists()
        warn = f"  ⚠️  {label}: 0 item{note} — "
        warn += (f"CSV existant conservé ({path.name}), non écrasé."
                 if exists else "rien à écrire (aucun CSV existant).")
        warn += " Utiliser --force pour écrire un CSV vide."
        print(warn, file=sys.stderr)
        return False
    writer(path, items)
    print(f"=> {path}")
    return True


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Fetch Mercari + Yahoo for a game key.")
    ap.add_argument("key")
    ap.add_argument("mercari_kw")
    ap.add_argument("yahoo_kw")
    ap.add_argument("--force", action="store_true",
                    help="écrire même si 0 résultat (écrase le CSV existant)")
    args = ap.parse_args()
    key, mer_kw, yh_kw = args.key, args.mercari_kw, args.yahoo_kw
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=== {key} ===")
    print(f"Mercari keyword: {mer_kw}")
    t0 = time.time()
    mer = asyncio.run(fetch_mercari(mer_kw))
    print(f"  → {len(mer)} items in {time.time()-t0:.1f}s")

    print(f"Yahoo   keyword: {yh_kw}")
    t0 = time.time()
    yh, total, blocked = fetch_yahoo(yh_kw)
    print(f"  → {len(yh)}/{total} items in {time.time()-t0:.1f}s")
    if blocked:
        print("  🚧 Yahoo géo-bloqué (HTTP 403, EEE/UK) — passe par un proxy/VPN "
              "japonais. Données Yahoo existantes préservées.", file=sys.stderr)

    _save(RAW_DIR / f"{key}_mercari.csv", mer, write_mercari_csv, "Mercari", args.force)
    _save(RAW_DIR / f"{key}_yahoo.csv", yh, write_yahoo_csv, "Yahoo", args.force,
          note=" (bloqué)" if blocked else "")


if __name__ == "__main__":
    main()

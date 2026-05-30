/Users/minux/Merclaude/.venv/bin/python <<'PY' 2>&1
import httpx, re, json, csv, time
from urllib.parse import quote
from datetime import datetime

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
keyword = "餓狼伝説スペシャル ネオジオ"
encoded = quote(keyword)

all_items, seen = [], set()
with httpx.Client(headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.9"}, timeout=20,
                  follow_redirects=True) as client:
    start = 1
    total_expected = None
    for page in range(20):  # safety cap
        url = f"https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={encoded}&va={encoded}&b={start}&n=50&s1=end&o1=d"
        r = client.get(url)
        r.raise_for_status()
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not m: break
        data = json.loads(m.group(1))
        listing = data["props"]["pageProps"]["initialState"]["search"]["items"]["listing"]
        items = listing.get("items", [])
        if total_expected is None:
            total_expected = listing.get("totalResultsAvailable", 0)
            print(f"Total annoncé par Yahoo: {total_expected}")
        new = 0
        for it in items:
            aid = it.get("auctionId")
            if aid and aid not in seen:
                seen.add(aid); all_items.append(it); new += 1
        print(f"  page b={start}: +{new} (total cumulé: {len(all_items)})")
        if not items or new == 0: break
        if total_expected and len(all_items) >= total_expected: break
        start += 50
        time.sleep(1.2)  # politesse

print(f"\nRécupéré: {len(all_items)} items uniques\n")

# Output CSV
with open('/tmp/yahoo_fatal_fury.csv', 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['Titre','URL','Prix','BidCount','Type','EndDate'])
    for it in all_items:
        title = (it.get("title","") or "").replace("\n"," ").replace(";",",")
        aid = it.get("auctionId","")
        url = f"https://page.auctions.yahoo.co.jp/jp/auction/{aid}"
        price = it.get("price") or it.get("buyNowPrice") or 0
        try: price_str = f"¥{int(price):,}"
        except Exception: price_str = ""
        bid = it.get("bidCount",0)
        kind = "Buy-Now" if it.get("isFixedPrice") else "Auction"
        end = it.get("endTime","")
        try:
            dt = datetime.fromisoformat(end)
            end_str = dt.strftime("%Y-%m-%d %H:%M %z")
        except ValueError: end_str = end
        w.writerow([title, url, price_str, bid, kind, end_str])

# Stats
sold = [it for it in all_items if (it.get("bidCount") or 0) >= 1 or it.get("isFixedPrice")]
unsold = [it for it in all_items if not ((it.get("bidCount") or 0) >= 1 or it.get("isFixedPrice"))]
print(f"Vendus (bidCount≥1 ou Buy-Now)  : {len(sold)}")
print(f"Non vendus (auction expirée)    : {len(unsold)}")

# Date range
ends = sorted([datetime.fromisoformat(it["endTime"]) for it in all_items if it.get("endTime")])
print(f"Période end_time: {ends[0].date()} → {ends[-1].date()}")

print(f"\n=> /tmp/yahoo_fatal_fury.csv ({len(all_items)} lignes)")
print("\nÉchantillon (5 premiers):")
for it in all_items[:5]:
    print(f"  ¥{(it.get('price') or 0):>6,} bids={it.get('bidCount',0):>2} {it.get('endTime','')[:10]}  {(it.get('title','') or '')[:65]}")
PY
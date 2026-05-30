cd /Users/minux/Merclaude/watcher && /Users/minux/Merclaude/.venv/bin/python <<'PY'
import asyncio, uuid, csv, time, httpx, re, json
from time import time as now
from urllib.parse import quote
from datetime import datetime, timezone
from ecdsa import NIST256p, SigningKey
from jose import jws
from jose.backends.ecdsa_backend import ECDSAECKey
from jose.constants import ALGORITHMS

URL_M = "https://api.mercari.jp/v2/entities:search"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

def dpop(url, method, key):
    ec_key = ECDSAECKey(key, ALGORITHMS.ES256)
    return jws.sign(
        {"iat":int(now()),"jti":str(uuid.uuid4()),"htu":url,"htm":method,"uuid":str(uuid.uuid4())},
        key,{"typ":"dpop+jwt","alg":"ES256","jwk":{k:ec_key.to_dict()[k] for k in ["crv","kty","x","y"]}},
        ALGORITHMS.ES256)

def mer_body(kw, tk=""):
    return {"userId":"","pageSize":120,"pageToken":tk,"searchSessionId":uuid.uuid4().hex,
            "indexRouting":"INDEX_ROUTING_UNSPECIFIED","thumbnailTypes":[],
            "searchCondition":{"keyword":kw,"sort":"SORT_CREATED_TIME","order":"ORDER_DESC",
                "status":["STATUS_ON_SALE","STATUS_TRADING","STATUS_SOLD_OUT"],
                "sizeId":[],"categoryId":[],"brandId":[],"sellerId":[],"priceMin":0,"priceMax":0,
                "itemConditionId":[],"shippingPayerId":[],"shippingFromArea":[],"shippingMethod":[],
                "colorId":[],"hasCoupon":False,"attributes":[],"itemTypes":[],"skuIds":[],"excludeKeyword":""},
            "defaultDatasets":[],"serviceFrom":"suruga"}

async def fetch_mercari(keyword):
    seen=set(); items=[]; tk=""
    async with httpx.AsyncClient() as c:
        for _ in range(20):
            k = SigningKey.generate(NIST256p)
            r = await c.post(URL_M, json=mer_body(keyword, tk),
                             headers={"User-Agent":UA,"X-Platform":"web","DPoP":dpop(URL_M,"POST",k)}, timeout=20)
            r.raise_for_status()
            d = r.json(); pg = d.get("items",[]) or []
            for it in pg:
                iid = it.get("id")
                if iid and iid not in seen: seen.add(iid); items.append(it)
            tk = (d.get("meta") or {}).get("nextPageToken","") or ""
            if not pg or not tk: break
    return items

def fetch_yahoo(keyword):
    encoded = quote(keyword)
    seen=set(); items=[]
    with httpx.Client(headers={"User-Agent": UA, "Accept-Language":"ja,en;q=0.9"}, timeout=20, follow_redirects=True) as c:
        start = 1; total = None
        for _ in range(40):
            url = f"https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={encoded}&va={encoded}&b={start}&n=50&s1=end&o1=d"
            r = c.get(url); r.raise_for_status()
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
            if not m: break
            d = json.loads(m.group(1))
            listing = d["props"]["pageProps"]["initialState"]["search"]["items"]["listing"]
            pg = listing.get("items", [])
            if total is None: total = listing.get("totalResultsAvailable", 0); print(f"  Yahoo: {total} results annoncés")
            new = 0
            for it in pg:
                aid = it.get("auctionId")
                if aid and aid not in seen: seen.add(aid); items.append(it); new += 1
            if not pg or new == 0: break
            if total and len(items) >= total: break
            start += 50
            time.sleep(1.0)
    return items

keyword = "キングオブファイターズ ネオジオ"

print("=== Mercari fetch ===")
mer_items = asyncio.run(fetch_mercari(keyword))
print(f"  Mercari: {len(mer_items)} items uniques")

print("=== Yahoo fetch ===")
yh_items = fetch_yahoo(keyword)
print(f"  Yahoo: {len(yh_items)} items uniques")

# CSV Mercari
with open('/tmp/kof_mercari.csv','w',encoding='utf-8',newline='') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['Titre','URL','Prix','Statut','Created'])
    for it in mer_items:
        name = (it.get("name","") or "").replace("\n"," ").replace(";",",")
        iid = it.get("id",""); url = f"https://jp.mercari.com/item/{iid}"
        try: ps = f"¥{int(it.get('price')):,}"
        except Exception: ps = ""
        status = (it.get("status","") or "").replace("ITEM_STATUS_","")
        try: cs = datetime.fromtimestamp(int(it.get("created")), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except Exception: cs = ""
        w.writerow([name, url, ps, status, cs])

# CSV Yahoo
with open('/tmp/kof_yahoo.csv','w',encoding='utf-8',newline='') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['Titre','URL','Prix','BidCount','Type','EndDate'])
    for it in yh_items:
        title = (it.get("title","") or "").replace("\n"," ").replace(";",",")
        aid = it.get("auctionId",""); url = f"https://page.auctions.yahoo.co.jp/jp/auction/{aid}"
        price = it.get("price") or it.get("buyNowPrice") or 0
        try: ps = f"¥{int(price):,}"
        except Exception: ps = ""
        bid = it.get("bidCount",0)
        kind = "Buy-Now" if it.get("isFixedPrice") else "Auction"
        end = it.get("endTime","")
        try: end_str = datetime.fromisoformat(end).strftime("%Y-%m-%d %H:%M %z")
        except ValueError: end_str = end
        w.writerow([title, url, ps, bid, kind, end_str])

print(f"\n=> /tmp/kof_mercari.csv ({len(mer_items)} lignes)")
print(f"=> /tmp/kof_yahoo.csv ({len(yh_items)} lignes)")
PY
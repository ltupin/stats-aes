#!/usr/bin/env python3
"""Sonde douce des ventes TERMINÉES eBay via un VRAI Chrome (Playwright).

Pilote le Chrome installé, profil persistant (tu te connectes toi-même si eBay
le demande — le script ne touche jamais au mot de passe), fenêtre visible,
navigation lente facon « vrai utilisateur ».

    ../.venv/bin/python ebay_probe.py "Samurai Shodown Neo Geo" --domains fr,com --pages 1

Test Samurai Shodown 1 (distingue du 2) : voir filtres SS1/SS2 plus bas.
"""
import argparse, random, re, sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = str(Path.home() / ".cache" / "ebay-probe-profile")  # session persistante
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Extraction in-page, robuste aux variantes de markup (.s-item et .s-card)
JS_EXTRACT = r"""() => {
  const out = [];
  const cards = document.querySelectorAll('li.s-item, li.s-card, .s-item, .srp-results .s-card');
  for (const c of cards) {
    const t = c.querySelector('.s-item__title, .s-card__title, [class*="title"]');
    const p = c.querySelector('.s-item__price, .s-card__price, [class*="price"]');
    const cap = c.querySelector('.s-item__caption, .s-card__caption, [class*="caption"], .s-item__title--tagblock');
    const a = c.querySelector('a.s-item__link, a.s-card__link, a[href*="/itm/"]');
    const title = t ? t.innerText.trim() : '';
    if (!title || /Shop on eBay|Résultats|results/i.test(title)) continue;
    out.push({
      title,
      price: p ? p.innerText.trim() : '',
      caption: cap ? cap.innerText.trim() : '',
      url: a ? a.href.split('?')[0] : '',
    });
  }
  return out;
}"""

# ── Filtres SS1 vs SS2 (réutilise l'esprit de report.py mais sur titres EN/FR/JP) ──
SS_INCLUDE = re.compile(r"samurai\s*(shodown|spirits)|サムライスピリッツ|侍魂", re.I)
SS2_MARKERS = re.compile(
    r"\b(2|ii)\b|shodown\s*2|shodown\s*ii|spirits\s*2|shin\s*samurai|真サムライ|真侍魂"
    r"|haohmaru|覇王丸地獄変", re.I)
SS_OTHER = re.compile(
    r"\b(3|iii|4|iv|5|v|6|vi)\b|zero|sen\b|tenka|amakusa|斬紅郎|天草|零|六番"
    r"|2019|2007|neogeo\s*collection|anthology", re.I)
LOT_RX = re.compile(r"\b(lot|bundle|joblot|x\s*\d|\d+\s*games|set of)\b|まとめ|セット", re.I)
PLATFORM_BAD = re.compile(r"\b(mvs|cd|cdz|switch|ps4|ps2|saturn|snes|super\s*nintendo|"
                          r"mega\s*drive|genesis|wii|arcade1up|aca|mini)\b", re.I)


def classify(title):
    if not SS_INCLUDE.search(title):
        return None
    if LOT_RX.search(title) or PLATFORM_BAD.search(title):
        return "skip"
    if SS_OTHER.search(title):
        return "skip"          # SS3/4/5/zero/anthology/remake
    if SS2_MARKERS.search(title):
        return "SS2"
    return "SS1"


def human_pause(a=1.2, b=3.0):
    time.sleep(random.uniform(a, b))


def scan(domain, keyword, pages, ctx):
    page = ctx.new_page()
    items = []
    for pg in range(1, pages + 1):
        url = (f"https://www.ebay.{domain}/sch/i.html?_nkw={keyword.replace(' ', '+')}"
               f"&LH_Sold=1&LH_Complete=1&_ipg=60&_pgn={pg}&rt=nc")
        print(f"  → ebay.{domain} page {pg}: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        human_pause(2, 4)
        # petit scroll pour déclencher le lazy-load
        for _ in range(3):
            page.mouse.wheel(0, 1800); human_pause(0.6, 1.4)
        title = page.title()
        if re.search(r"(Pardon our interruption|Error Page|robot|captcha|vérifi)", title, re.I):
            print(f"     ⚠️ blocage probable (titre page: {title!r}). "
                  f"Connecte-toi dans la fenêtre puis relance.")
            try:
                input("     ↳ Entrée pour réessayer cette page une fois connecté… ")
            except EOFError:
                pass
            page.goto(url, wait_until="domcontentloaded", timeout=45000); human_pause(2, 4)
        rows = page.evaluate(JS_EXTRACT)
        print(f"     {len(rows)} cartes extraites")
        for r in rows:
            r["domain"] = domain
        items += rows
        human_pause(2.5, 5)
    page.close()
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("--domains", default="fr,com")
    ap.add_argument("--pages", type=int, default=1)
    args = ap.parse_args()

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            PROFILE, channel="chrome", headless=False,
            user_agent=UA, locale="fr-FR", viewport={"width": 1360, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        all_items = []
        for dom in [d.strip() for d in args.domains.split(",") if d.strip()]:
            print(f"\n=== ebay.{dom} — '{args.keyword}' ===")
            all_items += scan(dom, args.keyword, args.pages, ctx)
            human_pause(3, 6)
        ctx.close()

    # Classement SS1 / SS2 / skip
    ss1 = [it for it in all_items if classify(it["title"]) == "SS1"]
    ss2 = [it for it in all_items if classify(it["title"]) == "SS2"]
    print(f"\n===== BILAN =====")
    print(f"cartes totales: {len(all_items)}")
    print(f"  Samurai Shodown 1 : {len(ss1)}")
    print(f"  Samurai Shodown 2 : {len(ss2)} (exclus du test SS1)")
    print(f"\nÉchantillon SS1 :")
    for it in ss1[:15]:
        print(f"  [{it['domain']}] {it['price']:<12} {it['caption'][:22]:<22} {it['title'][:60]}")


if __name__ == "__main__":
    main()

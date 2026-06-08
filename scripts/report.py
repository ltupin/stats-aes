#!/usr/bin/env python3
"""Filter raw Mercari+Yahoo CSVs for a game and emit HTML trend report + filtered CSV.

Reads ../data/raw/KEY_mercari.csv + KEY_yahoo.csv.
Writes ../data/filtered/KEY_filtered.csv + ../reports/KEY_trend.html.

Edit GAMES below to add/tune a game. Run:
    ../.venv/bin/python report.py KEY [KEY ...]
    ../.venv/bin/python report.py --all
"""
import csv, json, re, statistics, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
FIL_DIR = ROOT / "data" / "filtered"
RPT_DIR = ROOT / "reports"
EXC_DIR = ROOT / "data" / "exclude_urls"


def load_exclude_urls(key):
    """Read data/exclude_urls/KEY.txt — one URL per line, # comments allowed."""
    f = EXC_DIR / f"{key}.txt"
    if not f.exists():
        return set()
    urls = set()
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            urls.add(line)
    return urls

# Reference dates
ANNOUNCE   = datetime(2026, 4, 16, tzinfo=timezone.utc)  # Plaion AES+ announcement
START      = datetime(2026, 1, 1,  tzinfo=timezone.utc)
announce_x = int(ANNOUNCE.timestamp() * 1000)
start_x    = int(START.timestamp() * 1000)
PRICE_FLOOR = 5000  # ¥ — drop sub-floor as not real cart sales (marché Japon)
EUR_FLOOR   = 30    # € — idem marché France (eBay.fr) : sous 30€ = notices/inserts

# Common excludes — applied case-insensitively to every game.
EXCLUDE_COMMON_LC = [s.lower() for s in [
    "まとめ","ロット","Lot","コンソール","ソフト3本","ソフト2本",
    "攻略本","ガイド","ゲーメスト","ムック","雑誌","必勝","解析本","電波","攻略法",
    "キャップ","パッド","コントローラー","ぬいぐるみ","データファイル","ファイルカード",
    "帯のみ","箱のみ","空箱","説明書のみ","取扱説明書","ポスター","ペン",
    "業務用","販促","パンフレット","フライヤー","チラシ",
    "MVS","NCD","CDZ","CD-ROM","ＣＤ","基板","インスト","インストカード","純正インスト","プラカード",
    "ネオジオCD","ネオジオ CD","ネオジオ・CD","NEOGEO CD","NEO GEO CD","NEO-GEO CD","NEO・GEO CD",
    "NGCD","NG-CD","NEOGEOCD",
    "ネオジオミニ","NEOGEO mini","NEO GEO mini","NEOGEOミニ",
    "ネオジオポケット","NEOGEO POCKET","NEO GEO POCKET","NEOGEOポケット","NGPP",
    "セカンドミッション","2nd MISSION","Second Mission","1st MISSION",
    "ファーストミッション","ベストコレクション","BEST COLLECTION",
    "ネオジオスティック","NEOGEO STICK","NEO GEO STICK","NEOGEOスティック","STICK 2","STICK２",
    "AES 本体","AES本体","ネオジオ本体","NEOGEO 本体","NEOGEO本体","NEO GEO 本体","本体",
    "NEOGEO Arcade","NEOGEO ARCADE","Evercade","SUPER POCKET",
    "アクリル","ダイカット","シール","ステッカー","缶バッジ","缶バッチ","キーホルダー",
    "フィギュア","クリアファイル","ジオラマ","グッズ","ブロマイド","下敷き","ポストカード",
    "ハンカチ","タオル","Tシャツ","Ｔシャツ","缶ケース","プラモデル",
    "ガン消し","ガンケシ","消しゴム","ケシゴム","リペイント","ガチャ","ガシャポン","食玩","カードダス",
    "同人","手描き","手書き","イラスト集","スケッチブック","スケブ","直筆","ラフ画",
    "ボードゲーム","ボード ゲーム","カードゲーム","空ケース","ケースのみ","ジャケットのみ","ジャケットだけ",
    "switch","ネオジオコレクション","neogeo collection","neo geo collection",
    "ギャラクシーファイト","galaxy fight",
    # FR/EN (eBay) — pas une cartouche jouable
    "no game","sans jeu","sans le jeu","without game","box only","boite seule","boîte seule",
    "case only","manual only","notice seule","jaquette seule","empty box","repro","reproduction",
    "bootleg","custom label","aftermarket",
    # coque/PCB seuls (cartouche vide, sans jeu dedans)
    "empty cartridge","cartridge shell","empty shell","shell only","coque vide","coque seule",
    "boitier vide","boîtier vide","no pcb","without pcb","sans pcb","pcb only",
    "アートブック","イラスト集","サウンドトラック","サントラ","OST","オリジナルサウンドトラック",
    "予約特典","特典","ラバーマット","デスクマット","プレイマット",
    "色紙","原画","映画",
    "テレホンカード","テレカ","テレフォンカード","テレフォン カード",
    "新品未使用","新品 未使用","未開封",
    "PS2ソフト","PS4ソフト","Switchソフト","XBOX","スイッチ","アケアカ","ARCADE ARCHIVES","Arcade Archives",
    "ニンテンドー","Nintendo","PlayStation","ドリームキャスト","Dreamcast","DREAMCAST","ドリキャス","DC版",
    "アーケード","ACA NEOGEO","Wii","WII","セガサターン","Saturn",
    "PS2","PS3","PS4","PS5","PSP","NDS",
    # Portages rétro (PAS la version Neo Geo AES) — ex. FF2/FFS sortis sur MD/SFC/PCE
    "メガドライブ","MEGA DRIVE","MEGADRIVE","メガCD","MEGA CD","GENESIS","ジェネシス",
    "スーパーファミコン","スーファミ","SFC","SNES","Super Famicom","Super Nintendo",
    "PCエンジン","PC Engine","PCENGINE","TurboGrafx","ゲームギア","GAME GEAR","GAMEGEAR",
    "X68000","3DO","FM TOWNS","エフエムタウンズ",
    "ディスクのみ",
    "オンラインコレクション","ONLINE COLLECTION",
]]
SET_RX      = re.compile(r"(?<!カ)セット")
NB_HON_RX   = re.compile(r"\d+\s*[本点]")  # N本 / N点 = lot de N articles
# Neuf/scellé japonais (exclu, comme le neuf/scellé eBay) — mais on GARDE
# l'occasion « comme neuf » 新品同様 / ほぼ新品.
JP_NEW_RX = re.compile(r"(?<!ほぼ)新品(?!同様)")
BOX_ONLY_RX = re.compile(r"(?:箱|帯|説明書|インスト)(?:のみ|だけ)")
# NEOGEO CD (≠ AES) — tolère 中黒/espaces ("ネオ・ジオ CD") et le "CD" demi-chasse
# isolé ("CD ソフト", "CD-ROM") que la liste de substrings ne couvrait pas.
CD_RX = re.compile(
    r"ネオ[・･\s]*ジオ[・･\s]*CD|NEO[\s・･-]*GEO[\s・･-]*CD"
    r"|CD[\s]*(?:ソフト|ROM)|CD[-ー]ROM", re.IGNORECASE)
# Versions US/occidentales (≠ AES japonais). Épargne « US seller » (= vendeur US,
# jeu japonais) et « made in japan » seul.
US_RX = re.compile(
    r"\b(?:US|USA)\b(?!\s*seller)|\bNTSC-?U\b|us\s*version|usa\s*version"
    r"|version\s*us\b|am[ée]ricaine|english\s*usa|\beuro\b\s*version", re.IGNORECASE)
# Neuf / scellé (gonfle les prix). NEW_BARE = "new"/"neuf" seuls, SAUF s'il
# s'agit d'un descriptif d'occasion proche du neuf (LIKENEW) → conservé.
SEALED_RX = re.compile(
    r"sealed|brand[\s-]*new|factory\s*sealed|\bnib\b|\bbnib\b|\bnos\b|unopened"
    r"|scell|sous\s*blister|\bblister\b|jamais\s*ouvert|non\s*ouvert|neuf\s*sous|\bneuve\b",
    re.IGNORECASE)
NEW_BARE_RX = re.compile(r"\bnew\b|\bneuf\b", re.IGNORECASE)
# Titre qui COMMENCE par un mot de paperasse = c'est la notice/le manuel seul,
# pas le jeu (ex. "Notice Manual The King Of Fighters 95"). Tolère "NOUVELLE
# ANNONCE" / "New listing" qu'eBay colle parfois en tête.
MANUAL_LEAD_RX = re.compile(
    r"^\s*(?:nouvelle annonce|new listing)?\s*"
    r"(?:notice|manual|manuel|livret|inserts?|jaquette|booklet)\b", re.IGNORECASE)
# Combo paperasse au milieu du titre = notice/insert seuls (ex. "AES insert et
# notice KOF95"), pas la cartouche.
PAPERWORK_RX = re.compile(
    r"inserts?[\s,]+(?:et\s+|and\s+|&\s+)?notice|notice[\s,]+(?:et\s+|and\s+|&\s+)?inserts?",
    re.IGNORECASE)
LIKENEW_RX  = re.compile(
    r"like[\s-]*new|comme\s*neuf|proche\s*du\s*neuf|[ée]tat\s*neuf|quasi[\s-]*neuf"
    r"|presque\s*neuf|near\s*mint", re.IGNORECASE)

# Per-game config. INCLUDE = regex the title MUST match. EXCLUDE_GAME = extra
# substrings (case-insensitive) to drop. exclude_urls = manual URL drops.
GAMES = {
    "samsho1": {
        "label": "Samurai Shodown 1",
        "INCLUDE": re.compile(r"(サムライスピリッツ|侍魂|SAMURAI\s*SHODOWN|"
                              r"Samurai\s*Shodown|SAMURAI\s*SPIRITS)", re.IGNORECASE),
        "EXCLUDE_GAME": [
            "真サムライスピリッツ","真サムライ","真侍魂","真SAMURAI","真 SAMURAI",
            "覇王丸地獄変","覇王丸","斬紅郎","斬紅郎無双剣","天草降臨","アマクサ",
            "零","ゼロ","ゼロSP","零SP","零SPECIAL","六番勝負","6番勝負","羅刹",
            "SAMURAI SHODOWN II","SAMURAI SHODOWN 2","SAMURAI SHODOWN III","SAMURAI SHODOWN IV",
            "SAMURAI SHODOWN V","SAMURAI SHODOWN VI",
            "サムライスピリッツ2","サムライスピリッツ3","サムライスピリッツ4","サムライスピリッツ5","サムライスピリッツ6",
            "餓狼伝説","リアルバウト","キングオブファイターズ","KOF","King of Fighters",
            "龍虎の拳","メタルスラッグ","Metal Slug","ワールドヒーローズ","ブレイカーズ","風雲","アテナ",
        ],
        "exclude_urls": set(),
    },
    "aof": {
        "label": "Art of Fighting 1",
        "INCLUDE": re.compile(r"(龍虎の拳|Art\s*of\s*Fighting|ART\s*OF\s*FIGHTING|AOF)",
                              re.IGNORECASE),
        "EXCLUDE_GAME": [
            "龍虎の拳2","龍虎の拳3","龍虎2","龍虎3","龍虎II","龍虎III",
            "Art of Fighting 2","Art of Fighting 3","AOF2","AOF3","AOF II","AOF III","外伝",
            "餓狼伝説","リアルバウト","キングオブファイターズ","KOF","King of Fighters",
            "サムライスピリッツ","侍魂","メタルスラッグ","Metal Slug",
            "ワールドヒーローズ","ブレイカーズ","風雲","アテナ",
        ],
        "exclude_urls": set(),
    },
    "ffs": {
        "label": "Fatal Fury Special",
        "INCLUDE": re.compile(
            r"(餓狼伝説[\s　]*スペシャル|餓狼伝説[\s　]*SPECIAL"
            r"|餓狼[\s　]*スペシャル|餓狼[\s　]*SPECIAL"
            r"|FATAL\s*FURY\s*SPECIAL|Fatal\s*Fury\s*Special)", re.IGNORECASE),
        "EXCLUDE_GAME": [
            # Real Bout FF Special (1997) — jeu DIFFÉRENT, principal faux positif
            "リアルバウト","Real Bout","REALBOUT","REAL BOUT","RB餓狼","ＲＢ",
            # Autres opus / franchises Fatal Fury
            "餓狼伝説1","餓狼伝説2","餓狼伝説3","餓狼 MARK","MARK OF THE WOLVES","MOTW",
            "ウルブズ","ウルヴズ","ウルブス","City of the Wolves","COTW",
            # Autres franchises SNK
            "キングオブファイターズ","KOF","King of Fighters","KING OF FIGHTERS",
            "サムライスピリッツ","侍魂","龍虎の拳","メタルスラッグ","Metal Slug",
            "ワールドヒーローズ","ブレイカーズ","風雲","アテナ","ATHENA","月華",
        ],
        "exclude_urls": set(),
    },
    "ff2": {
        "label": "Fatal Fury 2",
        # Le « 2 » après 餓狼伝説 distingue du Special (餓狼伝説スペシャル, sans chiffre).
        # (?![0-9０-９]) évite 20周年 / 2本 etc.
        "INCLUDE": re.compile(
            r"(餓狼伝説[\s　]*[2２](?![0-9０-９])"
            r"|餓狼伝説[\s　]*II(?!I)"
            r"|Fatal\s*Fury\s*2|FATAL\s*FURY\s*2)", re.IGNORECASE),
        "EXCLUDE_GAME": [
            # NE PAS confondre avec les autres opus
            "餓狼伝説3","餓狼伝説SPECIAL","餓狼伝説スペシャル","SPECIAL","スペシャル",
            "餓狼 MARK","MARK OF THE WOLVES","MOTW","ウルブズ","City of the Wolves","COTW",
            # Real Bout 餓狼伝説2 (リアルバウト餓狼伝説2) = jeu DIFFÉRENT
            "リアルバウト","Real Bout","REALBOUT","REAL BOUT","RB餓狼","ＲＢ",
            # Autres franchises SNK
            "キングオブファイターズ","KOF","King of Fighters","KING OF FIGHTERS",
            "サムライスピリッツ","侍魂","龍虎の拳","メタルスラッグ","Metal Slug",
            "ワールドヒーローズ","ブレイカーズ","風雲","アテナ","ATHENA","月華",
        ],
        "exclude_urls": set(),
    },
    "ff3": {
        "label": "Fatal Fury 3",
        # Le « 3 » après 餓狼伝説, ou le sous-titre 遥かなる闘い (Road to Final Victory).
        "INCLUDE": re.compile(
            r"(餓狼伝説[\s　]*[3３](?![0-9０-９])"
            r"|餓狼伝説[\s　]*III"
            r"|Fatal\s*Fury\s*3|FATAL\s*FURY\s*3"
            r"|餓狼伝説[\s　]*遥かなる闘い|遥かなる闘い)", re.IGNORECASE),
        "EXCLUDE_GAME": [
            "餓狼伝説1","餓狼伝説2","餓狼伝説SPECIAL","餓狼伝説スペシャル","SPECIAL","スペシャル",
            "餓狼 MARK","MARK OF THE WOLVES","MOTW","ウルブズ","City of the Wolves","COTW",
            "リアルバウト","Real Bout","REALBOUT","REAL BOUT","RB餓狼","ＲＢ",
            "キングオブファイターズ","KOF","King of Fighters","KING OF FIGHTERS",
            "サムライスピリッツ","侍魂","龍虎の拳","メタルスラッグ","Metal Slug",
            "ワールドヒーローズ","ブレイカーズ","風雲","アテナ","ATHENA","月華",
        ],
        "exclude_urls": set(),
    },
    "wh2": {
        "label": "World Heroes 2",
        # Le « 2 » après ワールドヒーローズ. Exclure WH2 JET et WH Perfect (jeux ≠).
        "INCLUDE": re.compile(r"ワールドヒーローズ[\s　]*[2２](?![0-9０-９])"
                              r"|World\s*Heroes\s*2", re.IGNORECASE),
        "EXCLUDE_GAME": [
            "JET","ジェット","パーフェクト","PERFECT",          # WH2 JET / WH Perfect
            "ワールドヒーローズ2JET","ワールドヒーローズ2 JET",
            "キングオブファイターズ","KOF","King of Fighters","KING OF FIGHTERS",
            "餓狼伝説","リアルバウト","サムライスピリッツ","侍魂","龍虎の拳",
            "メタルスラッグ","Metal Slug","ブレイカーズ","風雲","アテナ","月華",
        ],
        "exclude_urls": set(),
    },
    "samsho2": {
        "label": "Samurai Shodown 2",
        # SS2 = 真サムライスピリッツ (préfixe 真). Le « 真 » distingue de SS1.
        "INCLUDE": re.compile(
            r"真[\s　]*サムライスピリッツ|真[\s　]*侍魂|真[\s　]*SAMURAI"
            r"|SAMURAI\s*SHODOWN\s*(?:2|II)(?!I)|SAMURAI\s*SPIRITS\s*(?:2|II)(?!I)"
            r"|覇王丸地獄変", re.IGNORECASE),
        "EXCLUDE_GAME": [
            # Autres Samurai Shodown
            "斬紅郎","無双剣","天草降臨","アマクサ","零","ゼロ","六番勝負","6番勝負","羅刹",
            "サムライスピリッツ3","サムライスピリッツ4","サムライスピリッツ5","サムライスピリッツ6",
            "SAMURAI SHODOWN III","SAMURAI SHODOWN IV","SAMURAI SHODOWN V","SAMURAI SHODOWN VI",
            # Autres franchises SNK
            "キングオブファイターズ","KOF","King of Fighters","餓狼伝説","リアルバウト",
            "龍虎の拳","メタルスラッグ","Metal Slug","ワールドヒーローズ","ブレイカーズ",
            "風雲","アテナ","月華",
        ],
        "exclude_urls": set(),
    },
    "aof2": {
        "label": "Art of Fighting 2",
        "INCLUDE": re.compile(r"龍虎の拳[\s　]*[2２](?![0-9０-９])"
                              r"|龍虎の拳[\s　]*II(?!I)|Art\s*of\s*Fighting\s*2",
                              re.IGNORECASE),
        "EXCLUDE_GAME": [
            "龍虎の拳3","龍虎3","龍虎III","Art of Fighting 3","AOF3","外伝",
            "キングオブファイターズ","KOF","King of Fighters","餓狼伝説","リアルバウト",
            "サムライスピリッツ","侍魂","メタルスラッグ","Metal Slug",
            "ワールドヒーローズ","ブレイカーズ","風雲","アテナ","月華",
        ],
        "exclude_urls": set(),
    },
    "ff1": {
        "label": "Fatal Fury 1",
        # FF1 = 餓狼伝説 SANS chiffre 2-9, sans Special, ni Real Bout/MOTW.
        # « 餓狼伝説1 » (explicite) reste accepté (le lookahead n'exclut que 2-9).
        "INCLUDE": re.compile(
            r"餓狼伝説(?![\s　]*[2-9２-９]|[\s　]*スペシャル|[\s　]*SPECIAL"
            r"|[\s　]*III|[\s　]*II)|FATAL\s*FURY(?!\s*(?:2|3|SPECIAL|II|III))",
            re.IGNORECASE),
        "EXCLUDE_GAME": [
            "餓狼伝説2","餓狼伝説3","スペシャル","SPECIAL","リアルバウト","Real Bout",
            "REALBOUT","REAL BOUT","RB餓狼","ＲＢ","餓狼 MARK","MARK OF THE WOLVES",
            "MOTW","ウルブズ","ウルヴズ","City of the Wolves","COTW",
            "キングオブファイターズ","KOF","King of Fighters","サムライスピリッツ","侍魂",
            "龍虎の拳","メタルスラッグ","Metal Slug","ワールドヒーローズ","ブレイカーズ",
            "風雲","アテナ","月華",
        ],
        "exclude_urls": set(),
    },
}

# ── KOF : versions régénérables (affectation UNIQUE par titre) ───────────────
# La version = le nombre collé au nom de la franchise (ファイターズ96, KOF95,
# ファイターズ2000, KOF02→2002). On capture CE nombre-là, pas n'importe quel
# nombre du titre, pour qu'un titre n'aille que dans UNE version.
KOF_BASE_RX = re.compile(
    r"(?:THE\s*)?KING\s*OF\s*FIGHTERS|キング[・･\s]*オブ[・･\s]*ファイターズ"
    r"|キングオブファイターズ|ザ[・･\s]*キング|KOF|ＫＯＦ", re.IGNORECASE)
# Nombre (demi- ou pleine-chasse) collé au mot de franchise, tolérant les
# séparateurs courants (espaces, ・ ' ’ ` * _ - …).
KOF_VER_RX = re.compile(
    r"(?:ファイターズ|FIGHTERS|ＦＩＧＨＴＥＲＳ|KOF|ＫＯＦ)"
    r"[\s　'’‘・･*`＊~_\-]*([0-9０-９]{2,4})", re.IGNORECASE)
_FW = str.maketrans("０１２３４５６７８９", "0123456789")  # pleine-chasse → ASCII
_KOF_SHORT = {"00": "2000", "01": "2001", "02": "2002"}
KOF_VERSIONS = ["94", "95", "96", "97", "98", "99", "2000", "2001", "2002"]


def kof_version(title):
    """Retourne la version KOF ('94'…'2002') d'un titre, ou None.
    Affectation unique : le 1er nombre collé au nom de franchise gagne."""
    if not KOF_BASE_RX.search(title):
        return None
    m = KOF_VER_RX.search(title)
    if not m:
        return None
    num = m.group(1).translate(_FW)
    if len(num) == 4:
        return num if num in KOF_VERSIONS else None
    if len(num) == 2:
        num = _KOF_SHORT.get(num, num)
        return num if num in KOF_VERSIONS else None
    return None  # 3 chiffres ou autre → ambigu, on ne classe pas


_KOF_OTHER_FRANCHISES = [
    "餓狼伝説", "リアルバウト", "Real Bout", "MARK OF THE WOLVES", "餓狼 MARK",
    "サムライスピリッツ", "侍魂", "龍虎の拳", "Art of Fighting", "メタルスラッグ",
    "Metal Slug", "ワールドヒーローズ", "ブレイカーズ", "風雲", "アテナ", "月華",
]
for _v in KOF_VERSIONS:
    GAMES[f"kof_{_v}"] = {
        "label": f"KOF {('’' + _v) if len(_v) == 2 else _v}",
        "raw": "kof",  # lit kof_mercari.csv / kof_yahoo.csv
        "INCLUDE": (lambda ver: (lambda title: kof_version(title) == ver))(_v),
        "EXCLUDE_GAME": _KOF_OTHER_FRANCHISES,
        "exclude_urls": set(),
    }


# ── Marché France (eBay.fr) ─────────────────────────────────────────────────
# Filtres eBay (titres latins) par jeu : INCLUDE + EXCLUDE (regex, gère les n°
# de version au bord de mot). La distinction SS1/SS2 reprend la logique validée.
EBAY = {
    "samsho1": {
        "INCLUDE": re.compile(r"samurai\s*(?:shodown|spirits|showdown)", re.I),
        "EXCLUDE": re.compile(r"\b(2|ii|3|iii|4|iv|5|v|6|vi)\b|shin|真|zankuro|斬紅郎"
                              r"|amakusa|天草|tenka|\bzero\b|\bsen\b|anthology|collection"
                              r"|perfect|special", re.I),
    },
    "samsho2": {
        "INCLUDE": re.compile(r"shin\s*samurai|真サムライ|真侍魂|haohmaru|覇王丸地獄変"
                              r"|samurai\s*(?:shodown|spirits|showdown)\s*(?:2|ii)\b", re.I),
        "EXCLUDE": re.compile(r"\b(3|iii|4|iv|5|v|6|vi)\b|zankuro|amakusa|\bzero\b"
                              r"|anthology|collection"
                              # autre franchise présente = lot/erreur (ex. lot de notices)
                              r"|fatal\s*fury|garou|餓狼|king\s*of\s*fighters|\bkof\b"
                              r"|metal\s*slug|world\s*heroes|art\s*of\s*fighting|龍虎", re.I),
    },
    "ffs": {
        "INCLUDE": re.compile(r"(?:fatal\s*fury|garou\s*densetsu|餓狼伝説)\s*"
                              r"(?:special|spécial|スペシャル)", re.I),
        "EXCLUDE": re.compile(r"real\s*bout|realbout|リアルバウト|\b(2|3)\b"
                              r"|mark\s*of\s*the\s*wolves|wolves", re.I),
    },
    "ff1": {
        "INCLUDE": re.compile(r"fatal\s*fury|garou\s*densetsu|餓狼伝説", re.I),
        "EXCLUDE": re.compile(r"\b(2|ii|3|iii)\b|special|spécial|スペシャル|real\s*bout"
                              r"|realbout|リアルバウト|mark\s*of\s*the\s*wolves|wolves"
                              r"|\bmotw\b|wild\s*ambition", re.I),
    },
    "ff2": {
        "INCLUDE": re.compile(r"(?:fatal\s*fury|garou\s*densetsu|餓狼伝説)\s*(?:2|ii)\b", re.I),
        "EXCLUDE": re.compile(r"special|spécial|スペシャル|real\s*bout|realbout|リアルバウト"
                              r"|\b3\b|\biii\b|mark\s*of\s*the\s*wolves|wolves", re.I),
    },
    "ff3": {
        "INCLUDE": re.compile(r"(?:fatal\s*fury|garou\s*densetsu|餓狼伝説)\s*(?:3|iii)\b"
                              r"|road\s*to\s*the\s*final|遥かなる闘い", re.I),
        "EXCLUDE": re.compile(r"special|spécial|スペシャル|real\s*bout|realbout|リアルバウト"
                              r"|\b2\b|\bii\b|mark\s*of\s*the\s*wolves|wolves", re.I),
    },
    "aof": {
        "INCLUDE": re.compile(r"art\s*of\s*fighting|ryuuko|ryūko|龍虎の拳", re.I),
        "EXCLUDE": re.compile(r"\b(2|ii|3|iii)\b|外伝", re.I),
    },
    "aof2": {
        "INCLUDE": re.compile(r"art\s*of\s*fighting\s*(?:2|ii)\b|龍虎の拳\s*[2２]", re.I),
        "EXCLUDE": re.compile(r"\b(3|iii)\b|外伝", re.I),
    },
    "wh2": {
        "INCLUDE": re.compile(r"world\s*heroes\s*(?:2|ii)\b|ワールドヒーローズ\s*[2２]", re.I),
        "EXCLUDE": re.compile(r"\bjet\b|perfect|gorgeous|\b(1|3|iii)\b", re.I),
    },
}


def build_ebay_filter(key):
    EX_URLS = load_exclude_urls(key + "_fr")
    if key.startswith("kof_"):           # versions KOF : classifieur (marche en latin)
        ver = key[len("kof_"):]
        inc, exc = (lambda t: kof_version(t) == ver), None
    else:
        cfg = EBAY[key]
        inc, exc = cfg["INCLUDE"].search, cfg["EXCLUDE"]

    def keep(title, url):
        if url in EX_URLS:
            return False
        if not inc(title):
            return False
        if exc and exc.search(title):
            return False
        tl = title.lower()
        if SET_RX.search(title) or NB_HON_RX.search(title) or BOX_ONLY_RX.search(title):
            return False
        if JP_NEW_RX.search(title): return False  # neuf/scellé (garde 新品同様)
        if CD_RX.search(title) or US_RX.search(title):  # CD ou version US/occidentale
            return False
        if SEALED_RX.search(title):                      # neuf / scellé
            return False
        if NEW_BARE_RX.search(title) and not LIKENEW_RX.search(title):
            return False
        if MANUAL_LEAD_RX.search(title) or PAPERWORK_RX.search(title):  # notice/insert seul
            return False
        return not any(e in tl for e in EXCLUDE_COMMON_LC)
    return keep


def gather_ebay(key):
    """Lit data/raw/{raw}_ebay_fr.csv → points € filtrés (>= EUR_FLOOR, >= START)."""
    if key not in EBAY and not key.startswith("kof_"):
        return []
    keep = build_ebay_filter(key)
    raw_key = GAMES[key].get("raw", key)
    path = RAW_DIR / f"{raw_key}_ebay_fr.csv"
    if not path.exists():
        return []
    pts = []
    with open(path, encoding="utf-8") as f:
        rd = csv.reader(f, delimiter=";"); next(rd, None)
        for row in rd:
            if len(row) < 4:
                continue
            title, url, ps, ds = row
            try:
                p = int(ps.replace("€", "").replace(" ", "").replace(",", ""))
            except ValueError:
                continue
            if p < EUR_FLOOR or p > 50000:
                continue
            try:
                dt = datetime.strptime(ds.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if dt < START:
                continue
            if not keep(title, url):
                continue
            pts.append({"x": int(dt.timestamp() * 1000), "y": p,
                        "name": title, "url": url, "source": "ebay"})
    return pts


# ── Filter ────────────────────────────────────────────────────────────────

def build_filter(cfg, key):
    INC = cfg["INCLUDE"]
    # INCLUDE peut être une regex (.search) ou un prédicat callable(title)->bool.
    inc_match = INC if callable(INC) else INC.search
    EXG = [e.lower() for e in cfg["EXCLUDE_GAME"]]
    # Merge in-code exclusions with persistent file from data/exclude_urls/KEY.txt
    EX_URLS = cfg.get("exclude_urls", set()) | load_exclude_urls(key)
    def keep(title, url):
        if url in EX_URLS: return False
        if not inc_match(title): return False
        tl = title.lower()
        if SET_RX.search(title) or NB_HON_RX.search(title) or BOX_ONLY_RX.search(title):
            return False
        if JP_NEW_RX.search(title): return False  # neuf/scellé (garde 新品同様)
        if CD_RX.search(title): return False  # NEOGEO CD (≠ AES)
        if any(e in tl for e in EXCLUDE_COMMON_LC): return False
        if any(e in tl for e in EXG):               return False
        return True
    return keep


def gather(key, cfg):
    keep = build_filter(cfg, key)
    mer, yh = [], []
    # Une source peut manquer (ex. Yahoo géo-bloqué, jamais fetché) → liste vide.
    # cfg["raw"] permet à plusieurs jeux de partager un même CSV brut
    # (ex. les 9 versions KOF lisent toutes kof_mercari.csv / kof_yahoo.csv).
    raw_key  = cfg.get("raw", key)
    mer_path = RAW_DIR / f"{raw_key}_mercari.csv"
    yh_path  = RAW_DIR / f"{raw_key}_yahoo.csv"
    if mer_path.exists():
      with open(mer_path, encoding="utf-8") as f:
        rd = csv.reader(f, delimiter=";"); next(rd)
        for row in rd:
            if len(row) < 5: continue
            title, url, ps, status, cs = row
            if status != "SOLD_OUT": continue
            try: p = int(ps.replace("¥", "").replace(",", ""))
            except: continue
            if p < PRICE_FLOOR or p > 5_000_000: continue
            try:
                dt = datetime.strptime(cs, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
            except: continue
            if dt < START: continue
            if not keep(title, url): continue
            mer.append({"x": int(dt.timestamp()*1000), "y": p,
                        "name": title, "url": url, "status": status, "source": "mercari"})
    if yh_path.exists():
      with open(yh_path, encoding="utf-8") as f:
        rd = csv.reader(f, delimiter=";"); next(rd)
        for row in rd:
            if len(row) < 6: continue
            title, url, ps, bs, kind, end_str = row
            try: p = int(ps.replace("¥", "").replace(",", ""))
            except: continue
            if p < PRICE_FLOOR or p > 5_000_000: continue
            try:
                dt = datetime.strptime(end_str.replace(" +0900", ""), "%Y-%m-%d %H:%M")\
                             .replace(tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
            except: continue
            if dt < START: continue
            if not keep(title, url): continue
            try: bid = int(bs)
            except: bid = 0
            yh.append({"x": int(dt.timestamp()*1000), "y": p, "name": title, "url": url,
                       "bid": bid, "kind": kind, "source": "yahoo"})
    return mer, yh


def stats_split(points):
    pre  = [p["y"] for p in points if p["x"] <  announce_x]
    post = [p["y"] for p in points if p["x"] >= announce_x]
    pm   = int(statistics.median(pre))  if pre  else 0
    qm   = int(statistics.median(post)) if post else 0
    delta = (qm - pm) / pm * 100 if pm and post else 0
    return len(pre), pm, len(post), qm, delta


# ── HTML report ───────────────────────────────────────────────────────────

# Weekly median: median of each ISO week's prices (no cross-week pooling).
# A week is plotted as soon as it has >= MIN_WEEK sales.
_MIN_WEEK = 2
_ROLLING_FN = "const MIN_WEEK = " + str(_MIN_WEEK) + ";\n" + r"""function weeklyTrend(points) {
  const buckets = new Map();
  for (const p of points) {
    const d = new Date(p.x);
    const tmp = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    tmp.setUTCDate(tmp.getUTCDate() + 3 - (tmp.getUTCDay() + 6) % 7);
    const weekYear = tmp.getUTCFullYear();
    const week1 = new Date(Date.UTC(weekYear, 0, 4));
    const week = 1 + Math.round(((tmp - week1) / 86400000 - 3 + (week1.getUTCDay() + 6) % 7) / 7);
    const key = `${weekYear}-W${String(week).padStart(2,'0')}`;
    if (!buckets.has(key)) buckets.set(key, { prices: [], dates: [] });
    buckets.get(key).prices.push(p.y); buckets.get(key).dates.push(p.x);
  }
  const sortedKeys = [...buckets.keys()].sort();
  const out = [];
  for (const key of sortedKeys) {
    const prices = buckets.get(key).prices;
    const dates  = buckets.get(key).dates;
    if (prices.length < MIN_WEEK) continue;
    const s = [...prices].sort((a,b)=>a-b);
    const med = s.length % 2 ? s[(s.length-1)/2] : (s[s.length/2-1]+s[s.length/2])/2;
    const midX = dates.sort((a,b)=>a-b)[Math.floor(dates.length/2)];
    out.push({ x: midX, y: med, count: prices.length, label: key });
  }
  return out;
}"""


def gen_html(label, mer, yh):
    s_m = stats_split(mer); s_y = stats_split(yh)
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>{label} — Mercari & Yahoo Auctions — 2026</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f6fa; color: #1a1a2e; padding: 24px; max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 4px 0; }}
  p.sub {{ color: #666; font-size: .85rem; margin: 0 0 20px 0; }}
  .card {{ background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 20px; }}
  .controls {{ display: flex; gap: 14px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; font-size: .85rem; }}
  .controls label {{ display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }}
  canvas {{ max-width: 100%; }}
  .insight {{ background: linear-gradient(90deg, #fef3c7 0%, #fee2e2 100%); border-left: 4px solid #dc2626; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px; }}
  .insight h3 {{ margin: 0 0 6px 0; font-size: 1rem; }}
  .insight p  {{ margin: 0; font-size: .88rem; line-height: 1.5; }}
  .insight strong {{ color: #dc2626; font-size: 1.05em; }}
  .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }}
  .src-card {{ background: rgba(255,255,255,.75); padding: 10px 14px; border-radius: 6px; font-size: .82rem; }}
  .src-card.mer {{ border-left: 3px solid #f59e0b; }}
  .src-card.yh  {{ border-left: 3px solid #2563eb; }}
  .errbox {{ background: #fee; border: 1px solid #c33; padding: 10px; font-family: monospace; font-size: .8rem; color: #c00; display: none; margin: 10px 0; border-radius: 6px; }}
</style></head><body>

<h1>{label} — Mercari &amp; Yahoo Auctions — 2026</h1>
<p class="sub">Mercari {len(mer)} ventes · Yahoo {len(yh)} ventes · données du {datetime.now(timezone.utc).strftime('%d/%m/%Y')}</p>

<div class="insight">
  <div class="split">
    <div class="src-card mer">
      <strong>🟡 Mercari</strong><br>
      Avant 16/04 : {s_m[0]} ventes · médiane ¥{s_m[1]:,}<br>
      Depuis : {s_m[2]} · médiane <strong>¥{s_m[3]:,}</strong> · <strong>{s_m[4]:+.1f}%</strong>
    </div>
    <div class="src-card yh">
      <strong>🔵 Yahoo</strong><br>
      Avant 16/04 : {s_y[0]} ventes · médiane ¥{s_y[1]:,}<br>
      Depuis : {s_y[2]} · médiane <strong>¥{s_y[3]:,}</strong> · <strong>{s_y[4]:+.1f}%</strong>
    </div>
  </div>
</div>

<div id="err" class="errbox"></div>

<div class="card">
  <div class="controls">
    <label><input type="checkbox" id="show-mer" checked> 🟡 Mercari</label>
    <label><input type="checkbox" id="show-yh"  checked> 🔵 Yahoo</label>
    <label><input type="checkbox" id="show-mer-trend" checked> ↗ Tendance Mercari</label>
    <label><input type="checkbox" id="show-yh-trend"  checked> ↗ Tendance Yahoo</label>
    <label><input type="checkbox" id="log-scale"> Échelle log Y</label>
  </div>
  <div style="height:560px;position:relative"><canvas id="chart"></canvas></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js"></script>
<script>
const MER = {json.dumps(mer, ensure_ascii=False)};
const YH  = {json.dumps(yh,  ensure_ascii=False)};
const ANNOUNCE_X = {announce_x};
const START_X    = {start_x};

function showErr(m){{const e=document.getElementById('err');e.style.display='block';e.textContent=(e.textContent?e.textContent+' | ':'')+m;console.error(m);}}
window.addEventListener('error', ev => showErr(`JS error: ${{ev.message}} @ ${{ev.lineno}}`));

{_ROLLING_FN}

try {{
  if (typeof Chart === 'undefined') {{ showErr('Chart.js failed'); throw new Error('no Chart'); }}
  const ctx = document.getElementById('chart').getContext('2d');
  const annoLinePlugin = {{
    id: 'annoLine',
    afterDatasetsDraw(chart) {{
      const x = chart.scales.x.getPixelForValue(ANNOUNCE_X);
      if (isNaN(x)) return;
      const c = chart.ctx;
      const top = chart.chartArea.top, bot = chart.chartArea.bottom;
      c.save();
      c.strokeStyle = '#dc2626'; c.lineWidth = 2; c.setLineDash([6,4]);
      c.beginPath(); c.moveTo(x, top); c.lineTo(x, bot); c.stroke();
      c.setLineDash([]);
      c.fillStyle = 'rgba(220,38,38,.9)';
      const lbl = '📣 Plaion AES+';
      c.font = 'bold 11px sans-serif';
      const w = c.measureText(lbl).width + 12;
      c.fillRect(x + 4, top + 4, w, 22);
      c.fillStyle = '#fff'; c.fillText(lbl, x + 10, top + 19);
      c.restore();
    }}
  }};
  let chart;
  function makeChart(yType) {{
    if (chart) chart.destroy();
    const merTrend = weeklyTrend(MER);
    const yhTrend  = weeklyTrend(YH);
    chart = new Chart(ctx, {{
      type: 'scatter',
      data: {{ datasets: [
        {{ label: 'Mercari', data: MER, backgroundColor: 'rgba(245,158,11,.55)', pointRadius: 4, pointStyle: 'circle' }},
        {{ label: 'Yahoo',   data: YH,  backgroundColor: 'rgba(37,99,235,.65)',  pointRadius: 5, pointStyle: 'triangle' }},
        {{ label: 'Tendance Mercari', data: merTrend, type: 'line',
          borderColor: '#f59e0b', backgroundColor: '#f59e0b', borderWidth: 2, borderDash: [5,4],
          pointRadius: 3, pointBackgroundColor: '#fff', pointBorderColor: '#f59e0b', showLine: true, tension: 0.15 }},
        {{ label: 'Tendance Yahoo', data: yhTrend, type: 'line',
          borderColor: '#1e40af', backgroundColor: '#1e40af', borderWidth: 2,
          pointRadius: 3, pointBackgroundColor: '#fff', pointBorderColor: '#1e40af', showLine: true, tension: 0.15 }},
      ]}},
      options: {{
        responsive: true, maintainAspectRatio: false,
        parsing: {{ xAxisKey: 'x', yAxisKey: 'y' }},
        plugins: {{
          legend: {{ position: 'top' }},
          tooltip: {{ callbacks: {{
            title: items => new Date(items[0].parsed.x).toLocaleDateString('fr-FR', {{ year: 'numeric', month: 'short', day: 'numeric' }}),
            label: c => {{
              const p = c.raw;
              if (p.source === 'mercari') return [`🟡 Mercari ¥${{p.y.toLocaleString()}} — ${{p.status}}`, p.name.slice(0, 60)];
              if (p.source === 'yahoo')   return [`🔵 Yahoo ¥${{p.y.toLocaleString()}} — ${{p.kind}} (${{p.bid}} bids)`, p.name.slice(0, 60)];
              if (p.label) return `${{p.label}} : médiane ¥${{Math.round(p.y).toLocaleString()}} (${{p.count}})`;
              return `¥${{Math.round(p.y).toLocaleString()}}`;
            }}
          }} }}
        }},
        scales: {{
          x: {{ type: 'linear', min: START_X,
               ticks: {{ callback: v => new Date(v).toLocaleDateString('fr-FR', {{month:'short', day:'2-digit'}}) }},
               title: {{ display: true, text: 'Date' }} }},
          y: {{ type: yType, title: {{ display: true, text: 'Prix (¥)' }},
               ticks: {{ callback: v => '¥' + v.toLocaleString() }} }},
        }},
        onClick: (evt, items) => {{ if (items.length) {{ const p = items[0].element.$context.raw; if (p.url) window.open(p.url, '_blank'); }} }},
      }},
      plugins: [annoLinePlugin],
    }});
    refreshVisibility();
  }}
  function refreshVisibility() {{
    if (!chart) return;
    chart.setDatasetVisibility(0, document.getElementById('show-mer').checked);
    chart.setDatasetVisibility(1, document.getElementById('show-yh').checked);
    chart.setDatasetVisibility(2, document.getElementById('show-mer-trend').checked);
    chart.setDatasetVisibility(3, document.getElementById('show-yh-trend').checked);
    chart.update();
  }}
  makeChart('linear');
  ['show-mer','show-yh','show-mer-trend','show-yh-trend'].forEach(id =>
    document.getElementById(id).addEventListener('change', refreshVisibility));
  document.getElementById('log-scale').addEventListener('change', e => makeChart(e.target.checked ? 'logarithmic' : 'linear'));
}} catch(e) {{ showErr(`Exception: ${{e.message}}`); }}
</script></body></html>
"""


def gen_fr_html(label, eb):
    s = stats_split(eb)
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>{label} — eBay.fr — 2026</title>
<style>
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#f5f6fa; color:#1a1a2e; padding:24px; max-width:1400px; margin:0 auto; }}
  h1 {{ font-size:1.4rem; margin:0 0 4px; }} p.sub {{ color:#666; font-size:.85rem; margin:0 0 20px; }}
  .card {{ background:#fff; border-radius:12px; padding:20px; box-shadow:0 1px 4px rgba(0,0,0,.08); margin-bottom:20px; }}
  .insight {{ background:linear-gradient(90deg,#dbeafe,#ede9fe); border-left:4px solid #2563eb; padding:14px 18px; border-radius:8px; margin-bottom:20px; }}
  .src-card {{ background:rgba(255,255,255,.75); padding:10px 14px; border-radius:6px; font-size:.85rem; border-left:3px solid #2563eb; display:inline-block; }}
</style></head><body>
<h1>{label} — 🇫🇷 eBay.fr — 2026</h1>
<p class="sub">eBay.fr (ventes terminées) · {len(eb)} ventes · marché France (€) · données du {datetime.now(timezone.utc).strftime('%d/%m/%Y')}</p>
<div class="insight">
  <div class="src-card">
    <strong>🇫🇷 eBay.fr</strong><br>
    Avant 16/04 : {s[0]} ventes · médiane €{s[1]:,}<br>
    Depuis : {s[2]} · médiane <strong>€{s[3]:,}</strong> · <strong>{s[4]:+.1f}%</strong>
  </div>
</div>
<div class="card">
  <div class="controls" style="display:flex;gap:14px;flex-wrap:wrap;font-size:.85rem;margin-bottom:10px">
    <label><input type="checkbox" id="show-eb" checked> 🇫🇷 eBay.fr</label>
    <label><input type="checkbox" id="show-eb-trend" checked> ↗ Tendance</label>
    <label><input type="checkbox" id="log-scale"> Échelle log Y</label>
  </div>
  <div style="height:540px;position:relative"><canvas id="chart"></canvas></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js"></script>
<script>
const EB = {json.dumps(eb, ensure_ascii=False)};
const ANNOUNCE_X = {announce_x}; const START_X = {start_x};
{_ROLLING_FN}
const annoLine = {{ id:'annoLine', afterDatasetsDraw(ch){{
  const x=ch.scales.x.getPixelForValue(ANNOUNCE_X); if(isNaN(x))return; const c=ch.ctx;
  c.save(); c.strokeStyle='#dc2626'; c.lineWidth=2; c.setLineDash([6,4]);
  c.beginPath(); c.moveTo(x,ch.chartArea.top); c.lineTo(x,ch.chartArea.bottom); c.stroke(); c.setLineDash([]);
  c.fillStyle='rgba(220,38,38,.9)'; c.font='bold 11px sans-serif'; const l='📣 Plaion AES+';
  c.fillRect(x+4,ch.chartArea.top+4,c.measureText(l).width+12,22); c.fillStyle='#fff'; c.fillText(l,x+10,ch.chartArea.top+19); c.restore();
}} }};
const ctx = document.getElementById('chart').getContext('2d');
let chart;
function makeChart(yType) {{
  if (chart) chart.destroy();
  chart = new Chart(ctx, {{
    type:'scatter',
    data:{{ datasets:[
      {{ label:'eBay.fr', data:EB, backgroundColor:'rgba(37,99,235,.6)', pointRadius:4 }},
      {{ label:'Tendance', data:weeklyTrend(EB), type:'line', borderColor:'#1e40af', borderWidth:2,
         pointRadius:3, pointBackgroundColor:'#fff', pointBorderColor:'#1e40af', showLine:true, tension:.15 }} ]}},
    options:{{ responsive:true, maintainAspectRatio:false, parsing:{{xAxisKey:'x',yAxisKey:'y'}},
      plugins:{{ legend:{{position:'top'}}, tooltip:{{ callbacks:{{
        title:i=>new Date(i[0].parsed.x).toLocaleDateString('fr-FR',{{year:'numeric',month:'short',day:'numeric'}}),
        label:c=>{{const p=c.raw; return p.source==='ebay'?[`🇫🇷 €${{p.y.toLocaleString()}}`,p.name.slice(0,60)]:`médiane €${{Math.round(p.y).toLocaleString()}}`;}} }} }} }},
      scales:{{ x:{{ type:'linear', min:START_X, ticks:{{ callback:v=>new Date(v).toLocaleDateString('fr-FR',{{month:'short',day:'2-digit'}}) }}, title:{{display:true,text:'Date'}} }},
        y:{{ type:yType, title:{{display:true,text:'Prix (€)'}}, ticks:{{ callback:v=>'€'+v.toLocaleString() }} }} }},
      onClick:(e,it)=>{{ if(it.length){{const p=it[0].element.$context.raw; if(p.url)window.open(p.url,'_blank');}} }} }},
    plugins:[annoLine] }});
  refreshVisibility();
}}
function refreshVisibility() {{
  if (!chart) return;
  chart.setDatasetVisibility(0, document.getElementById('show-eb').checked);
  chart.setDatasetVisibility(1, document.getElementById('show-eb-trend').checked);
  chart.update();
}}
makeChart('linear');
['show-eb','show-eb-trend'].forEach(id => document.getElementById(id).addEventListener('change', refreshVisibility));
document.getElementById('log-scale').addEventListener('change', e => makeChart(e.target.checked ? 'logarithmic' : 'linear'));
</script></body></html>
"""


def write_filtered_csv(path, mer, yh, currency="¥"):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Source","Titre","URL","Prix","Date"])
        for p in sorted(mer + yh, key=lambda x: x["x"]):
            d = datetime.fromtimestamp(p["x"]/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            w.writerow([p["source"].capitalize(), p["name"], p["url"], f"{currency}{p['y']:,}", d])


def run(key):
    cfg = GAMES[key]
    mer, yh = gather(key, cfg)
    FIL_DIR.mkdir(parents=True, exist_ok=True)
    RPT_DIR.mkdir(parents=True, exist_ok=True)
    write_filtered_csv(FIL_DIR / f"{key}_filtered.csv", mer, yh)
    (RPT_DIR / f"{key}_trend.html").write_text(gen_html(cfg["label"], mer, yh), encoding="utf-8")
    s_m = stats_split(mer); s_y = stats_split(yh)
    line = (f"{cfg['label']:<35} | Mer {len(mer):>3} (¥{s_m[1]:>7,}→¥{s_m[3]:>7,} {s_m[4]:+.0f}%) "
            f"| Yh {len(yh):>3} (¥{s_y[1]:>7,}→¥{s_y[3]:>7,} {s_y[4]:+.0f}%)")
    # Marché France (eBay.fr) — rapport séparé si données présentes
    eb = gather_ebay(key)
    if eb:
        write_filtered_csv(FIL_DIR / f"{key}_fr_filtered.csv", eb, [], currency="€")
        (RPT_DIR / f"{key}_fr.html").write_text(gen_fr_html(cfg["label"], eb), encoding="utf-8")
        s_e = stats_split(eb)
        line += f"  || 🇫🇷 eB {len(eb):>3} (€{s_e[1]:>5,}→€{s_e[3]:>5,} {s_e[4]:+.0f}%)"
    print(line)


def main():
    if len(sys.argv) < 2:
        print("usage: report.py KEY [KEY ...]  |  report.py --all", file=sys.stderr)
        print(f"Available: {', '.join(GAMES)}", file=sys.stderr)
        sys.exit(2)
    keys = list(GAMES) if sys.argv[1] == "--all" else sys.argv[1:]
    for k in keys:
        if k not in GAMES:
            print(f"unknown key: {k} (have: {', '.join(GAMES)})", file=sys.stderr); continue
        run(k)


if __name__ == "__main__":
    main()

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
PRICE_FLOOR = 5000  # ¥ — drop sub-floor as not real cart sales

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
    "アートブック","イラスト集","サウンドトラック","サントラ","OST","オリジナルサウンドトラック",
    "予約特典","特典","ラバーマット","デスクマット","プレイマット",
    "色紙","原画","映画",
    "テレホンカード","テレカ","テレフォンカード","テレフォン カード",
    "新品同様","新品 同様","新品未使用","新品 未使用","未開封",
    "PS2ソフト","PS4ソフト","Switchソフト","XBOX","スイッチ","アケアカ","ARCADE ARCHIVES","Arcade Archives",
    "ニンテンドー","Nintendo","PlayStation","ドリームキャスト","Dreamcast","DREAMCAST","ドリキャス","DC版",
    "アーケード","ACA NEOGEO","Wii","WII","セガサターン","Saturn",
    "PS2","PS3","PS4","PS5","PSP","NDS",
    "ディスクのみ",
    "オンラインコレクション","ONLINE COLLECTION",
]]
SET_RX      = re.compile(r"(?<!カ)セット")
NB_HON_RX   = re.compile(r"\d+本")
BOX_ONLY_RX = re.compile(r"(?:箱|帯|説明書|インスト)(?:のみ|だけ)")

# Per-game config. INCLUDE = regex the title MUST match. EXCLUDE_GAME = extra
# substrings (case-insensitive) to drop. exclude_urls = manual URL drops.
GAMES = {
    "garou": {
        "label": "Garou: Mark of the Wolves AES",
        "INCLUDE": re.compile(
            r"(餓狼.*(MARK|MOTW|ウルブズ|ウルヴズ|ウルブス|ウルヴス))"
            r"|MARK\s*OF\s*THE\s*WOLVES|MOTW|マーク・オブ・ザ", re.IGNORECASE),
        "EXCLUDE_GAME": [
            "City of the Wolves","シティ・オブ・ザ・ウルブズ","CITY OF THE WOLVES","COTW",
            "餓狼伝説2","餓狼伝説3","餓狼伝説SPECIAL","リアルバウト","Real Bout","REALBOUT",
            "キングオブファイターズ","KOF","King of Fighters","KING OF FIGHTERS",
            "サムライスピリッツ","侍魂","龍虎の拳","メタルスラッグ","Metal Slug",
            "ワールドヒーローズ","ブレイカーズ","風雲","アテナ","ATHENA","月華",
        ],
        # Manuelles : data/exclude_urls/garou.txt (validate.py les y ajoute)
        "exclude_urls": set(),
    },
    "samsho1": {
        "label": "Samurai Shodown 1 AES",
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
        "label": "Art of Fighting 1 AES",
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
    "ms": {
        "label": "Metal Slug 1 AES",
        "INCLUDE": re.compile(r"(メタルスラッグ|Metal\s*Slug|METAL\s*SLUG)", re.IGNORECASE),
        "EXCLUDE_GAME": [
            "餓狼伝説","リアルバウト","キングオブファイターズ","KOF","King of Fighters",
            "サムライスピリッツ","侍魂","龍虎の拳","ワールドヒーローズ","ブレイカーズ","風雲","アテナ",
            "メタルスラッグ2","メタルスラッグ3","メタルスラッグ4","メタルスラッグ5","メタルスラッグX","メタルスラッグＸ",
            "Metal Slug 2","Metal Slug 3","Metal Slug 4","Metal Slug 5","Metal Slug X","Metal Slug XX",
            "メタルスラッグ6","メタルスラッグ7","アンソロジー","Anthology",
        ],
        "exclude_urls": set(),
    },
}


# ── Filter ────────────────────────────────────────────────────────────────

def build_filter(cfg, key):
    INC = cfg["INCLUDE"]
    EXG = [e.lower() for e in cfg["EXCLUDE_GAME"]]
    # Merge in-code exclusions with persistent file from data/exclude_urls/KEY.txt
    EX_URLS = cfg.get("exclude_urls", set()) | load_exclude_urls(key)
    def keep(title, url):
        if url in EX_URLS: return False
        if not INC.search(title): return False
        tl = title.lower()
        if SET_RX.search(title) or NB_HON_RX.search(title) or BOX_ONLY_RX.search(title):
            return False
        if any(e in tl for e in EXCLUDE_COMMON_LC): return False
        if any(e in tl for e in EXG):               return False
        return True
    return keep


def gather(key, cfg):
    keep = build_filter(cfg, key)
    mer, yh = [], []
    with open(RAW_DIR / f"{key}_mercari.csv", encoding="utf-8") as f:
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
    with open(RAW_DIR / f"{key}_yahoo.csv", encoding="utf-8") as f:
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

# Rolling 3-week centered median: pools week N-1, N, N+1 prices and takes
# their median. Smooths noise on sparse-data weeks (down to 2-3 sales/week)
# without losing the median's outlier resistance.
_ROLLING_FN = """function weeklyTrend(points) {
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
  for (let i = 0; i < sortedKeys.length; i++) {
    const window = [sortedKeys[i-1], sortedKeys[i], sortedKeys[i+1]].filter(Boolean);
    const pooled = window.flatMap(k => buckets.get(k).prices);
    const dates  = buckets.get(sortedKeys[i]).dates;
    if (pooled.length < 3) continue;
    const s = [...pooled].sort((a,b)=>a-b);
    const med = s.length % 2 ? s[(s.length-1)/2] : (s[s.length/2-1]+s[s.length/2])/2;
    const midX = dates.sort((a,b)=>a-b)[Math.floor(dates.length/2)];
    out.push({ x: midX, y: med, count: pooled.length, label: sortedKeys[i] + ' (±1 sem)' });
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
  <h3>📣 Effet de l'annonce Plaion Neo Geo AES+ (16 avril 2026)</h3>
  <p>Plaion a annoncé le 16/04/2026 la sortie en novembre d'une nouvelle console <strong>Neo Geo AES+</strong> compatible avec les cartouches d'origine.</p>
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


def write_filtered_csv(path, mer, yh):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Source","Titre","URL","Prix","Date"])
        for p in sorted(mer + yh, key=lambda x: x["x"]):
            d = datetime.fromtimestamp(p["x"]/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            w.writerow([p["source"].capitalize(), p["name"], p["url"], f"¥{p['y']:,}", d])


def run(key):
    cfg = GAMES[key]
    mer, yh = gather(key, cfg)
    FIL_DIR.mkdir(parents=True, exist_ok=True)
    RPT_DIR.mkdir(parents=True, exist_ok=True)
    write_filtered_csv(FIL_DIR / f"{key}_filtered.csv", mer, yh)
    (RPT_DIR / f"{key}_trend.html").write_text(gen_html(cfg["label"], mer, yh), encoding="utf-8")
    s_m = stats_split(mer); s_y = stats_split(yh)
    print(f"{cfg['label']:<35} | Mer {len(mer):>3} (¥{s_m[1]:>7,}→¥{s_m[3]:>7,} {s_m[4]:+.0f}%) "
          f"| Yh {len(yh):>3} (¥{s_y[1]:>7,}→¥{s_y[3]:>7,} {s_y[4]:+.0f}%)")


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

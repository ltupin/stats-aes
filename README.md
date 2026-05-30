# Statistiques Neo Geo AES — effet annonce Plaion AES+ (16/04/2026)

Application autonome de scraping + analyse de prix d'occasion sur Mercari
Japan + Yahoo Auctions Japon pour les jeux Neo Geo AES depuis le 01/01/2026,
avec ligne verticale marquant l'annonce Plaion AES+ du 16/04/2026.

**Standalone** : ne dépend d'aucun autre projet. Venv local + requirements.txt
embarqués.

## Structure

```
Statistiques/
├── README.md
├── howto.md                      — pas-à-pas pour créer un nouveau comparatif
├── requirements.txt              — dépendances pip
├── .venv/                        — venv local (Python 3.14)
├── reports/                      — pages HTML autonomes (Chart.js via CDN)
│   ├── garou_trend.html
│   ├── samsho1_trend.html
│   ├── aof_trend.html
│   ├── ms_trend.html
│   ├── kof_{94,95,96,97,98,99,2000,2001,2002}_trend.html
│   ├── kof_all_versions_trend.html      — KOF avec filtre versions
│   └── fatal_fury_special_*.html        — legacy mono-source
├── data/
│   ├── kof_data.json                    — données intermédiaires KOF
│   ├── raw/                             — CSV bruts (Mercari + Yahoo)
│   │   ├── {key}_mercari.csv                Titre;URL;Prix;Statut;Created
│   │   └── {key}_yahoo.csv                  Titre;URL;Prix;BidCount;Type;EndDate
│   ├── filtered/                        — CSV nettoyés (post-filtre)
│   │   └── {key}_filtered.csv               Source;Titre;URL;Prix;Date
│   └── exclude_urls/                    — URLs droppées manuellement (persistant)
│       └── {key}.txt                        une URL par ligne, # = commentaire
└── scripts/
    ├── fetch.py                  — Mercari + Yahoo paginated fetcher
    ├── report.py                 — filtre + générateur HTML
    ├── validate.py               — validation interactive (drop faux positifs)
    └── _archive_*.sh             — scripts shell historiques d'exploration
```

## Installation (premier setup, si .venv absent)

```bash
cd /Users/minux/Statistiques
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Utilisation

Les pages HTML sont autonomes (Chart.js depuis CDN, données inline) —
double-clic pour ouvrir dans le navigateur.

### Régénérer un rapport depuis les CSV existants

```bash
cd /Users/minux/Statistiques/scripts
../.venv/bin/python report.py garou
../.venv/bin/python report.py --all
```

### Re-fetcher les données brutes d'un jeu (mise à jour)

```bash
cd /Users/minux/Statistiques/scripts
../.venv/bin/python fetch.py garou \
  "餓狼 MARK OF THE WOLVES ネオジオ" "餓狼 MARK OF THE WOLVES"
../.venv/bin/python report.py garou
```

### Ajouter un nouveau jeu

Voir **[howto.md](howto.md)** pour le pas-à-pas complet avec exemple
(Fatal Fury 3). Workflow en bref :

```bash
cd /Users/minux/Statistiques/scripts
../.venv/bin/python fetch.py    KEY "KW_MERCARI" "KW_YAHOO"
# … éditer GAMES dans report.py …
../.venv/bin/python report.py   KEY
../.venv/bin/python validate.py KEY --all   # 🛑 OBLIGATOIRE
../.venv/bin/python report.py   KEY
open ../reports/KEY_trend.html
```

L'étape **`validate.py`** est obligatoire : elle surface les outliers (prix
anormalement haut/bas), ouvre les URLs dans le navigateur, te laisse
keep/drop chaque item au clavier. Les drops sont persistés dans
`data/exclude_urls/KEY.txt` et s'appliquent automatiquement aux fetches
suivants.

## Méthodologie

- **Sources** :
  - Mercari Japan, API `entities:search` (DPoP-signed JWT), `STATUS_SOLD_OUT`
    uniquement = ventes finalisées
  - Yahoo Auctions Japon, page `closedsearch` + scraping `__NEXT_DATA__`
- **Période** : à partir du 01/01/2026
- **Plancher** : ¥5,000 (en dessous = télécartes, inst-cards, lots résiduels)
- **Filtres** (case-insensitive) : exclut MVS / NEOGEO CD / Mini / Pocket /
  STICK / PS2 / Switch / Dreamcast / Aké Archives / goodies / lots / manuels
  seuls / télécartes…
- **Outliers** : flagués si > 2× médiane globale, soumis à validation
  utilisateur, droppés par URL si confirmés faux positifs
- **Tendance** : médiane glissante 3 semaines centrée (pool semaines N-1, N,
  N+1) — plus lisse que la médiane hebdo brute sur les jeux à faible volume
  tout en restant robuste aux outliers

## Résultats clés

| Jeu              | Mercari Δ | Yahoo Δ | Lecture |
|------------------|-----------|---------|---------|
| Fatal Fury Sp.   | +163 %    | +134 %  | Bond Plaion massif (jeu pilote) |
| KOF '94          | +112 %    | +86 %   | Premier opus, fortes volumes |
| KOF '95-'97      | +27→+77 % | +32→+77 % | Tendance haussière cohérente |
| KOF '98-2002     | bruité    | bruité  | Volumes minces, conclusions fragiles |
| SamSho 1         | +100 %    | +123 %  | Forte hausse symétrique |
| AOF 1            | +76 %     | +54 %   | Hausse claire malgré faibles volumes |
| Metal Slug 1     | 0 vente   | 0 vente | Très rare ; AES n'apparaît pas en clear  |
| Garou MOTW       | n/a       | -3 %    | **Marché déjà saturé** — pas d'effet Plaion |

## Dépendances

Python ≥ 3.10. Packages (voir `requirements.txt`) :

- `httpx` — client HTTP async (Mercari) + sync (Yahoo)
- `ecdsa` + `python-jose` — signature DPoP requise par Mercari API

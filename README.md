# Statistiques Neo Geo AES — effet annonce Plaion AES+ (16/04/2026)

Application autonome de scraping + analyse de prix d'occasion sur Mercari
Japan + Yahoo Auctions Japon pour les jeux Neo Geo AES depuis le 01/01/2026,
avec ligne verticale marquant l'annonce Plaion AES+ du 16/04/2026.

**Standalone** : ne dépend d'aucun autre projet. Venv local + requirements.txt
embarqués.

> ℹ️ Yahoo Auctions (`closedsearch`) bloque les requêtes depuis l'EEE/UK
> (HTTP 403). Pour re-fetcher Yahoo, sortir via un réseau/proxy japonais.
> Mercari n'est pas géo-bloqué.

## Structure

```
Statistiques/
├── README.md
├── howto.md                      — pas-à-pas pour créer un nouveau comparatif
├── index.html                    — sommaire (liens + chiffres clés de chaque rapport)
├── requirements.txt              — dépendances pip
├── .venv/                        — venv local (Python 3.14)
├── reports/                      — pages HTML autonomes (Chart.js via CDN)
│   ├── ff2_trend.html
│   ├── ffs_trend.html
│   ├── ff3_trend.html
│   ├── samsho1_trend.html
│   ├── aof_trend.html
│   ├── wh2_trend.html
│   └── kof_{94,95,96,97,98,99,2000,2001,2002}_trend.html
├── data/
│   ├── raw/                             — CSV bruts (Mercari + Yahoo), CUMULATIFS
│   │   ├── {key}_mercari.csv                Titre;URL;Prix;Statut;Created
│   │   └── {key}_yahoo.csv                  Titre;URL;Prix;BidCount;Type;EndDate
│   ├── filtered/                        — CSV nettoyés (post-filtre)
│   │   └── {key}_filtered.csv               Source;Titre;URL;Prix;Date
│   └── exclude_urls/                    — URLs droppées manuellement (persistant)
│       └── {key}.txt                        une URL par ligne, # = commentaire
└── scripts/
    ├── fetch.py                  — Mercari + Yahoo fetcher (fusion CUMULATIVE)
    ├── report.py                 — filtre + générateur HTML
    ├── validate.py               — validation interactive (drop faux positifs)
    └── build_index.py            — régénère index.html depuis les rapports
```

## Installation (premier setup, si .venv absent)

```bash
cd Statistiques          # le dépôt cloné
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Utilisation

Ouvrir **`index.html`** à la racine : sommaire de tous les rapports avec les
variations clés. Les pages HTML sont autonomes (Chart.js depuis CDN, données
inline) — double-clic pour ouvrir dans le navigateur.

### Régénérer un rapport depuis les CSV existants

```bash
cd scripts
../.venv/bin/python report.py ffs
../.venv/bin/python report.py --all
# puis rafraîchir le sommaire :
../.venv/bin/python build_index.py
```

### Re-fetcher les données brutes d'un jeu (mise à jour)

```bash
cd scripts
../.venv/bin/python fetch.py ffs \
  "餓狼伝説スペシャル ネオジオ" "餓狼伝説スペシャル"
../.venv/bin/python report.py ffs
../.venv/bin/python build_index.py
```

### Ajouter un nouveau jeu

Voir **[howto.md](howto.md)** pour le pas-à-pas complet avec exemple
(Fatal Fury 3). Workflow en bref :

```bash
cd scripts
../.venv/bin/python fetch.py    KEY "KW_MERCARI" "KW_YAHOO"
# … éditer GAMES dans report.py …
../.venv/bin/python report.py   KEY
../.venv/bin/python validate.py KEY --all   # 🛑 OBLIGATOIRE
../.venv/bin/python report.py   KEY
../.venv/bin/python build_index.py
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
- **Tendance** : **médiane hebdomadaire** (par semaine ISO ; une semaine est
  tracée dès ≥ 2 ventes) — `_MIN_WEEK` dans `report.py`
- **Données cumulatives** : `fetch.py` **fusionne** dans les CSV existants
  (clé = URL) et ne supprime jamais rien → la base ne fait que grandir, même
  si Yahoo retire une vieille annonce de sa fenêtre `closedsearch`
- **KOF** : les 9 versions (’94→2002) sont régénérables — un classifieur
  d'affectation unique (`kof_version`) lit le n° collé au nom de la franchise
  et alimente `data/raw/kof_*.csv` partagé (champ `raw` dans `GAMES`)

## Résultats clés

| Jeu              | Mercari Δ | Yahoo Δ | Lecture |
|------------------|-----------|---------|---------|
| Fatal Fury 2     | +119 %    | n/a*    | Forte hausse ; *Yahoo non fetché (géo-bloc) |
| Fatal Fury Sp.   | +168 %    | +135 %  | Bond Plaion massif (jeu pilote) |
| Fatal Fury 3     | +19 %     | n/a*    | Hausse modérée, déjà cher/rare ; *Mercari only |
| KOF '94          | +112 %    | +86 %   | Premier opus, fortes volumes |
| KOF '95-'97      | +27→+77 % | +32→+77 % | Tendance haussière cohérente |
| KOF '98-2002     | bruité    | bruité  | Volumes minces, conclusions fragiles |
| SamSho 1         | +100 %    | +100 %  | Forte hausse symétrique |
| World Heroes 2   | +150 %    | +91 %   | Ajouté via discover.py (≈5 ventes/sem) |
| AOF 1            | +76 %     | +54 %   | Hausse claire malgré faibles volumes |

## Dépendances

Python ≥ 3.10. Packages (voir `requirements.txt`) :

- `httpx` — client HTTP async (Mercari) + sync (Yahoo)
- `ecdsa` + `python-jose` — signature DPoP requise par Mercari API

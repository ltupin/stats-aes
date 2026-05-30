# Comment générer un nouveau comparatif

Exemple complet : créer la page **Fatal Fury 3** (Garou Densetsu 3) de zéro.

Le workflow tient en **5 étapes**, dont une **étape 4 de validation manuelle
interactive** qui est **obligatoire** pour éviter de polluer la médiane avec
des faux positifs (cartes d'instruction, télécartes, MVS, ports Switch, etc.
qui passent à travers les filtres génériques).

---

## Étape 1 — Récupérer les keywords japonais

Aller sur Mercari ou Yahoo et chercher le titre japonais canonique du jeu.
Pour Fatal Fury 3 → 餓狼伝説3 (ou 餓狼伝説 3).

Choisis 2 keywords :

| Plateforme | Keyword conseillé |
|---|---|
| Mercari | `餓狼伝説3 ネオジオ` — ajouter "ネオジオ" cible mieux l'AES |
| Yahoo   | `餓狼伝説3` — Yahoo a une longue tail, mot-clé plus large OK |

Astuce : si tu hésites, fetch d'abord avec un keyword large puis affine via
l'étape 4 (validation). Le filtrage par regex se fera dans `report.py`.

---

## Étape 2 — Fetch des données brutes

```bash
cd /Users/minux/Statistiques/scripts
../.venv/bin/python fetch.py ff3 \
  "餓狼伝説3 ネオジオ" "餓狼伝説3"
```

Sortie : `data/raw/ff3_mercari.csv` + `data/raw/ff3_yahoo.csv`.

Ces CSV contiennent **tout ce que les APIs retournent** — bien plus que ce
qu'on veut garder. Le filtrage vient ensuite.

---

## Étape 3 — Déclarer le jeu dans `report.py`

Édite `scripts/report.py`, ajoute une entrée dans le dict `GAMES` :

```python
"ff3": {
    "label": "Fatal Fury 3 AES",
    # INCLUDE : regex que le titre DOIT matcher (jeu cible + variantes graphies)
    "INCLUDE": re.compile(
        r"(餓狼伝説[\s　]*[3３III]|Fatal\s*Fury\s*3|FATAL\s*FURY\s*3"
        r"|餓狼伝説\s*遥かなる闘い)",
        re.IGNORECASE),
    # EXCLUDE_GAME : substrings à exclure SPÉCIFIQUES (autres opus de la série,
    # franchises concurrentes). Les exclusions communes (CD/Mini/MVS/PS2/etc.)
    # sont dans EXCLUDE_COMMON_LC et s'appliquent à tous les jeux.
    "EXCLUDE_GAME": [
        # Autres Fatal Fury à filtrer
        "餓狼伝説1","餓狼伝説2","餓狼伝説SPECIAL","餓狼SPECIAL",
        "リアルバウト","Real Bout","REALBOUT","REAL BOUT",
        "餓狼 MARK","MARK OF THE WOLVES","City of the Wolves",
        # Autres franchises SNK
        "キングオブファイターズ","KOF","King of Fighters",
        "サムライスピリッツ","侍魂","龍虎の拳","メタルスラッグ","Metal Slug",
        "ワールドヒーローズ","ブレイカーズ","風雲","アテナ","月華",
    ],
    "exclude_urls": set(),  # validate.py les ajoute via data/exclude_urls/ff3.txt
},
```

**Conseils regex INCLUDE** :
- Couvre les graphies pleine-largeur (`３` japonais) ET demi-largeur (`3`).
- Mets `[\s　]*` (avec l'espace japonais 　 U+3000) pour gérer les espaces variables.
- Si le jeu a un sous-titre (ici `遥かなる闘い`), inclus-le.

**Conseils EXCLUDE_GAME** :
- Pense aux opus voisins (FF1, FF2, FF Special, Real Bout, MOTW).
- Liste les franchises SNK proches (KOF, SS, etc.) — ils apparaissent souvent
  dans les lots ou descriptions multi-jeux.

---

## Étape 4 — Rapport initial + validation interactive 🛑 OBLIGATOIRE

### 4a. Première génération

```bash
../.venv/bin/python report.py ff3
```

Regarde la sortie console : nombre de ventes Mercari/Yahoo, médiane avant/après
16/04, delta Plaion. Si les volumes sont trop bas (< 20 ventes total), c'est
qu'il faut élargir les keywords ou que le jeu est trop rare.

### 4b. Validation interactive (le cœur du processus)

```bash
../.venv/bin/python validate.py ff3
```

Le script affiche pour **chaque outlier** (> 2× médiane ou < 0.5× médiane) :

```
[3/12] 🟡 Mercari  ¥8,861  2026-03-23  (0.05× médiane ⚠️ LOW)
   ＳＮＫ／ネオジオ MARK OF THE WOLVES 餓狼
   https://page.auctions.yahoo.co.jp/jp/auction/w1223617338
   → [k/d/o/s/q]
```

Touches :

| Touche | Action |
|---|---|
| `k` ou Entrée | **Keep** — l'item est légitime, on le garde |
| `d` | **Drop** — c'est un faux positif, on le droppe |
| `o` | **Open** — ouvre l'URL dans le navigateur pour vérifier visuellement |
| `s` | **Skip** — passe sans décider (à revoir plus tard) |
| `q` | **Quit** — sauvegarde les décisions prises et sort |

L'URL est **auto-ouverte dans le navigateur** par défaut (pour ne pas avoir à
copier-coller). Pour désactiver : `validate.py ff3 --no-browser`.

Les URLs `d`roppées sont écrites dans `data/exclude_urls/ff3.txt` (persistant —
elles seront automatiquement re-droppées la prochaine fois qu'on fetch).

### 4c. Modes de revue

```bash
# Mode par défaut : seulement les outliers (high + low)
../.venv/bin/python validate.py ff3

# Seulement les outliers bas (prix anormalement faibles)
../.venv/bin/python validate.py ff3 --low

# Seulement les outliers hauts
../.venv/bin/python validate.py ff3 --high

# Tout reviewer (utile pour première passe sur un nouveau jeu)
../.venv/bin/python validate.py ff3 --all
```

**Recommandation** : pour un nouveau jeu, faire `--all` la première fois.
Aux fetches suivants (mise à jour), juste le mode par défaut suffit puisque
les anciennes décisions sont déjà persistées.

### 4d. Pattern à identifier comme « drop »

Indicateurs visuels typiques sur la page de l'annonce :

- **Carte d'instruction seule** (インストカード) — pas de jaquette, pas de cartouche
- **Boîte/manuel sans cartouche** (箱のみ, 説明書のみ)
- **Télécartes promotionnelles** (テレカ) — petits cartons SNK
- **Sticker / clearfile / pin / mug** — goodies divers
- **Port Switch/PS2/PS4** — Arcade Archives, ACA NEOGEO
- **NEOGEO CD / Mini / Pocket** — autre plateforme
- **Cartouche MVS** (arcade) — pas la version AES home
- **Lot multi-jeux** (まとめ, セット) — prix non attribuable au jeu cible

### 4e. Re-générer le rapport final

```bash
../.venv/bin/python report.py ff3
open ../reports/ff3_trend.html
```

La médiane sera désormais propre.

---

## Étape 5 — Itérer (optionnel)

Si à l'usage tu repères encore des annonces parasites :

1. Ajoute son URL dans `data/exclude_urls/ff3.txt` (manuellement ou via
   `validate.py ff3 --all`).
2. `report.py ff3` régénère le HTML.

Si tu vois plusieurs faux positifs partageant un mot-clé (ex. "限定版"
limited edition tape souvent x3 le prix médian), ajoute le mot-clé dans
`EXCLUDE_GAME` du dict `GAMES["ff3"]` → c'est plus efficace que de dropper
URL par URL.

---

## Mise à jour récurrente d'un jeu existant

Pour rafraîchir une page existante (ex. tous les 1-2 mois pour suivre
l'effet Plaion qui se propage) :

```bash
cd /Users/minux/Statistiques/scripts
# Re-fetch
../.venv/bin/python fetch.py garou \
  "餓狼 MARK OF THE WOLVES ネオジオ" "餓狼 MARK OF THE WOLVES"
# Re-filter + report (les exclusions persistantes s'appliquent automatiquement)
../.venv/bin/python report.py garou
# Validation rapide des nouveaux outliers seulement
../.venv/bin/python validate.py garou
# Re-report si des nouveaux drops ont été faits
../.venv/bin/python report.py garou
```

---

## Résumé en une commande

Pour un nouveau jeu **après** avoir édité `GAMES` dans `report.py` :

```bash
cd /Users/minux/Statistiques/scripts
../.venv/bin/python fetch.py    KEY "KW_MERCARI" "KW_YAHOO"  && \
../.venv/bin/python report.py   KEY                          && \
../.venv/bin/python validate.py KEY --all                    && \
../.venv/bin/python report.py   KEY                          && \
open ../reports/KEY_trend.html
```

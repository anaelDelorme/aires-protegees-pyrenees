# Atlas des espaces protégés des Pyrénées

Carte statique consultable sur GitHub Pages, France–Espagne–Andorre : recherche, filtres par pays et typologie, fiches sources et export de la sélection en GeoJSON. Leaflet 1.9.4 est livré dans `site/vendor` avec sa licence ; aucune compilation JavaScript n’est nécessaire.

**État : prototype documentaire, inventaire incomplet.** Les 16 points initiaux sont des repères approximatifs de grands parcs et du projet de PNR du Pays basque. Ils ne sont ni des contours officiels ni un inventaire validé en ligne. Réserves, Natura 2000, conservatoires et autres protections restent à compléter. Ne pas utiliser les effectifs pour annoncer le nombre total d’aires protégées des Pyrénées.

## Développer et consulter

Python 3.12 ou ultérieur. Pour le site initial, aucune dépendance Python :

```sh
cd /workspace/aires-protegees-pyrenees
python3 scripts/build_data.py
python3 -m unittest discover -s tests -v
python3 -m http.server 8000 --bind 127.0.0.1 --directory site
```

La carte charge son GeoJSON par HTTP ; une ouverture en `file://` ne suffit pas. Le fond OpenStreetMap nécessite Internet. La carte, les points et les fiches restent utilisables si les tuiles du fond sont indisponibles. Les bibliothèques sont servies localement.

## Actualiser les données

```sh
python3 -m venv /workspace/pyrenees-venv
/workspace/pyrenees-venv/bin/pip install -r requirements.txt
/workspace/pyrenees-venv/bin/python scripts/build_data.py --refresh-osm
```

Cette collecte utilise Overpass (`https://overpass-api.de/api/interpreter`) et les limites/points OpenStreetMap. Elle n’est **pas** une extraction exhaustive des registres officiels. Les catégories sont inférées des tags et noms. Les géométries sans nom restent visibles sous leur identifiant source. Les géométries linéaires sont écartées ; l’emprise est une fenêtre d’étude 42°–43,6° N, 2° O–3,5° E, pas une limite officielle du massif. La géométrie complète des objets intersectant la fenêtre est conservée. Le pays n’est renseigné que si le tag `addr:country` le permet. Le filtre ne prétend pas identifier tous les sites d’un pays lorsque ce tag manque.

La collecte échoue explicitement en cas d’erreur HTTP, de réponse Overpass partielle ou vide. Elle ne remplace pas le GeoJSON publié en cas d’échec. Les réponses brutes et converties sont gardées dans `.cache/` (ignoré par Git). Une reconstruction à partir du cache évite de solliciter le serveur :

```sh
/workspace/pyrenees-venv/bin/python scripts/build_data.py --use-osm-cache
```

Sans option, le programme reconstruit uniquement les repères manuels. Pour maintenir des imports officiels entre reconstructions, fournir les mêmes options `--official` à chaque fois. Seuls les changements explicites du GeoJSON commité sont publiés ; aucune actualisation automatique non contrôlée.

## Compléter avec des inventaires officiels

Sources à consulter et réconcilier :

- France : INPN/PatriNat et services IGN (`data.geopf.fr`) pour les espaces protégés et Natura 2000 ; Fédération des PNR (`www.parcs-naturels-regionaux.fr`) pour les PNR ; Réseau des CEN et conservatoires régionaux pour les sites gérés.
- Espagne : MITECO, IDE autonómicas (Navarre, Aragón, Catalogne, Pays basque) ; toutes les désignations locales ne sont pas identiques aux catégories françaises.
- Natura 2000 : inventaire EEA, en distinguant ZPS et ZSC/SIC. Le réseau européen ne s’applique pas à l’Andorre.
- Andorre : ministère de l’Environnement et gestionnaires des parcs.
- Projet du Pays basque : informations de la Communauté d’agglomération Pays Basque et de la Fédération des PNR. Vérifier le statut avant publication ; ne pas lui attribuer un classement acquis ni inventer un contour.

Les connecteurs vers ces inventaires officiels ne sont **pas encore implémentés ni validés**. L’accès réseau aux sources est bloqué dans la session de création. Le programme accepte déjà des exports GeoJSON **normalisés** (pas les exports bruts de n’importe quel fournisseur) :

```sh
python3 scripts/build_data.py --official data/inpn-normalise.geojson --official data/espagne-normalise.geojson
```

Chaque Feature doit avoir une géométrie WGS84 `[longitude, latitude]` de type Point, Polygon ou MultiPolygon et ces propriétés :

```json
{
  "id": "inpn:IDENTIFIANT_SOURCE",
  "name": "Nom officiel",
  "category": "Réserve naturelle",
  "country": "France",
  "status": "Classé — source officielle",
  "source": "Nom du jeu officiel, version et licence",
  "url": "https://adresse-de-la-fiche-officielle",
  "collected_at": "DATE_REELLE_DE_COLLECTE",
  "reference": "IDENTIFIANT_SOURCE",
  "operator": "Gestionnaire"
}
```

Catégories acceptées : Parc national, PNR, Parc naturel, Réserve naturelle, Natura 2000, Site de conservatoire, Autre protection, Projet de PNR. Les identifiants sont uniques avec un préfixe de source. Préserver le statut juridique original dans `note` pour ne pas le perdre lors de la normalisation. S’assurer de la licence et du périmètre de chaque import. Les importations ne font pas de conversion de projection ni de découpage : préparer les fichiers avant import.

Ne pas confondre un espace et ses désignations superposées. La déduplication entre registres, le comptage des espaces uniques et les surfaces cumulées ne sont pas encore fournis. L’interface affiche des **enregistrements**, sépare le projet, et avertit de l’incomplétude. Les repères manuels sont conservés lors d’une collecte : retirer ceux devenus redondants après rapprochement documenté avec les données officielles.

## Publier sur GitHub Pages

Le dépôt cible est `anaelDelorme/aires-protegees-pyrenees`, sélectionné lors de la création de l’environnement et initialement vide. Le workflow `.github/workflows/pages.yml` teste les données puis publie uniquement `site/` à chaque push sur `main` ou déclenchement manuel.

1. Pousser les fichiers sur la branche `main` du dépôt.
2. Dans **Settings → Pages → Build and deployment**, sélectionner **GitHub Actions**.
3. Lancer ou relancer « Publier la carte » dans Actions.
4. Utiliser l’URL fournie par le déploiement réussi. L’existence du fichier workflow ne prouve pas qu’un déploiement a eu lieu.

**Publication distante non vérifiée dans la session de création.** L’accès Git natif est fourni par le proxy de la plateforme ; ne pas copier de token dans le dépôt. L’API GitHub et le push peuvent avoir des autorisations différentes du simple accès en lecture.

## Tests et licences

`python3 -m unittest discover -s tests -v` vérifie les confusions de typologies, la séparation du projet, les IDs, les liens et la structure des données publiées. `node --check site/app.js` vérifie la syntaxe JavaScript. Les tests navigateur sont documentés dans `tests/browser.cjs` et nécessitent Playwright avec Chromium ; ils interceptent le fond OSM pour tester le fonctionnement indépendamment de la disponibilité des tuiles.

Leaflet : BSD-2-Clause, voir `site/vendor/LICENSE`. Fond OSM et collecte OSM : © contributeurs OpenStreetMap, ODbL. Chaque futur import officiel doit conserver sa licence et son attribution ; aucune licence globale ne remplace celle des jeux importés.

# Pyrénées · Atlas des espaces protégés

Carte interactive France–Espagne–Andorre : filtres, recherche, liste latérale, fiches sur la carte, sources et export GeoJSON. Version mobile avec bascule Carte / Liste. Site statique sans build frontend ; Leaflet 1.9.4 est livré avec sa licence.

## Couverture actuelle

**629 enregistrements avec contours officiels français**, collectés le 30 octobre 2026 auprès du service INPN / PatriNat diffusé par l’IGN. 21 couches interrogées, y compris celles sans résultat dans la fenêtre étudiée :

| Inventaire | Enregistrements |
|---|---:|
| Parc national (cœur et aire d’adhésion distincts) | 2 |
| Parcs naturels régionaux | 5 |
| Parc naturel marin | 1 |
| Réserves naturelles nationales / régionales | 26 |
| Réserves biologiques | 17 |
| Arrêtés de protection de biotope | 47 |
| Natura 2000 — Habitats (SIC / ZSC) | 139 |
| Natura 2000 — Oiseaux (ZPS) | 54 |
| Terrains acquis par les CEN | 74 |
| Conservatoire du littoral | 48 |
| Sites classés au titre du paysage | 212 |
| Réserve nationale de chasse et de faune sauvage | 1 |
| Sites Ramsar | 3 |

**Ce n’est pas un total d’espaces uniques ni un inventaire transfrontalier exhaustif.** Un site Natura 2000, une réserve et le cœur d’un parc peuvent se superposer. Un PNR n’est pas une réserve réglementaire ; un site Ramsar est une reconnaissance internationale. Les catégories et désignations originales restent distinctes.

Les 12 autres entrées sont des **points documentaires approximatifs** : grands parcs espagnols, parcs andorrans et projet de PNR du Pays basque. Les contours et inventaires officiels Espagne/Andorre restent à intégrer. Le projet basque n’est pas présenté comme classé et aucun périmètre de classement n’est inventé.

L’emprise de collecte est une fenêtre WGS84 `[-2, 42, 3.5, 43.6]` (ouest, sud, est, nord). Elle inclut des piémonts et territoires voisins, notamment des PNR de bordure ; ce n’est pas une délimitation officielle du massif. Les contours intersectant la fenêtre sont conservés entiers.

Limites françaises : CEN couvre les **terrains acquis renseignés dans la couche**, pas tous les sites gérés. Les espaces naturels sensibles, autres sites de gestion foncière, protections locales et sites inscrits ne sont pas couverts systématiquement. Les dates de source peuvent être anciennes ; la collecte récente ne confirme pas la validité actuelle des échéances ou un renouvellement de classement. Consulter les fiches et actes officiels.

## Développer et consulter

```sh
cd /workspace/aires-protegees-pyrenees
python3 -m venv /workspace/pyrenees-venv
/workspace/pyrenees-venv/bin/pip install -r requirements.txt
/workspace/pyrenees-venv/bin/python -m unittest discover -s tests -v
node --check site/app.js
python3 -m http.server 8000 --bind 127.0.0.1 --directory site
```

Le GeoJSON se charge par HTTP. Pas de compilation nécessaire. Le fond OpenStreetMap, atténué en niveaux de gris et sans clé API, nécessite Internet ; les contours et fiches restent utilisables sans tuiles. Les données sont dans `site/data/areas.geojson`, les sources françaises normalisées dans `data/france-official.geojson`, la couverture des couches dans `data/france-sources.json`.

## Obtenir les contours officiels et reproduire l’inventaire

On télécharge les **polygones du fournisseur**, plutôt que de tracer des limites à la main. Le connecteur français est implémenté et exécuté :

```sh
/workspace/pyrenees-venv/bin/python scripts/collect_france.py
python3 scripts/build_data.py
```

Le programme utilise `https://data.geopf.fr/wfs/ows` (WFS 2.0), pagination de 100 objets, `CRS:84` explicite (longitude, latitude), sélection spatiale par fenêtre, contrôle du nombre attendu et des identifiants INPN. Les parties portant le même identifiant sont réunies, mais les différentes désignations ne sont pas fusionnées par proximité. Les repères manuels français sont remplacés par leurs identifiants officiels explicites.

Les contours sont validés et simplifiés avec préservation de la topologie (`0.00005°`, environ 4–6 m) pour le Web. Les limites affichées et exportées sont donc **dérivées de sources officielles**, sans valeur de bornage réglementaire. La fiche propose le téléchargement du **contour original non simplifié** via une requête WFS filtrée sur l’identifiant, en plus du lien INPN. Le service accepte le filtre `CQL_FILTER=id_mnhn='IDENTIFIANT'`.

Les réponses brutes, avec date de collecte, sont conservées dans `.cache/inpn/` (ignoré par Git) ; leurs empreintes SHA-256 figurent dans le manifeste de sources. Toute couche déclarée doit réussir : un échec réseau ou une réponse tronquée n’écrase pas les données normalisées. Reconstruction depuis ces réponses, sans réseau :

```sh
/workspace/pyrenees-venv/bin/python scripts/collect_france.py --offline
python3 scripts/build_data.py
```

`build_data.py` intègre par défaut le fichier officiel conservé dans le dépôt : une reconstruction simple ne supprime plus les contours français. Elle ne contacte pas de service distant.

### Espagne et Andorre : prochaines sources

Consulter MITECO et ses services cartographiques, les inventaires des communautés autonomes (Navarre, Aragón, Catalogne, Pays basque), puis les autorités et gestionnaires andorrans. Pour Natura 2000, rapprocher les identifiants européens et distinguer les directives Oiseaux et Habitats. Natura 2000 ne couvre pas l’Andorre.

Les connecteurs officiels pour ces territoires ne sont pas encore implémentés ni exécutés. La collecte OpenStreetMap reste facultative et **ne remplace pas un inventaire officiel** ; le serveur Overpass a répondu HTTP 406 dans la session actuelle. Elle n’est pas utilisée dans le jeu publié :

```sh
/workspace/pyrenees-venv/bin/python scripts/build_data.py --refresh-osm
# Réutiliser une collecte réussie déjà conservée :
/workspace/pyrenees-venv/bin/python scripts/build_data.py --use-osm-cache
```

La collecte conserve son avertissement d’incomplétude, les pays uniquement s’ils figurent dans les tags, et des identifiants préfixés `osm:`. Les doublons OSM / officiels ne sont pas automatiquement rapprochés : vérifier avant publication.

### Importer d’autres exports normalisés

```sh
python3 scripts/build_data.py --official data/espagne-normalise.geojson
```

Les imports doivent être des FeatureCollection WGS84 contenant Point, Polygon ou MultiPolygon, avec propriétés : `id` unique préfixé par la source, `name`, `category`, `status`, `source`. Ajouter `country`, `designation`, `reference`, `operator`, `url`, `collected_at`, `source_modified`, `license`, `evidence` (`official`, `reference` ou `osm`) et `geometry_quality`. Seuls les jeux officiellement sourcés doivent porter `evidence: official`. Les catégories acceptées figurent dans `scripts/build_data.py`. Les imports ne sont pas reprojetés ou découpés implicitement. Fournir les mêmes options à chaque reconstruction.

## Validation et publication

```sh
/workspace/pyrenees-venv/bin/python -m unittest discover -s tests -v
node --check site/app.js
NODE_PATH=/chemin/vers/node_modules node tests/browser.cjs
```

Le test navigateur utilise Playwright et Chromium, avec le serveur local lancé. Il vérifie les listes et contours, les filtres, le remplacement des repères, les liens sources, les fiches, l’export, les sources et la vue mobile. Le fond est intercepté pour isoler le fonctionnement de l’application de la disponibilité des tuiles.

Le dépôt `anaelDelorme/aires-protegees-pyrenees` est configuré en **Settings → Pages → Source → GitHub Actions**. Le workflow `.github/workflows/pages.yml` teste puis publie `site/`. Le contrôle final `scripts/check_public_site.py` vérifie l’URL publique, les données et les assets. Attendre le succès du workflow **pour le commit publié** avant d’annoncer la livraison.

## Sources et licences

- France : INPN / PatriNat, diffusion IGN Géoplateforme. Données INPN sous Licence Ouverte / Open Licence ; chaque fiche conserve ses références et dates.
- PNR : [Fédération des PNR](https://www.parcs-naturels-regionaux.fr/) et fiches INPN ; le registre cartographique fournit les polygones.
- [MITECO](https://www.miteco.gob.es/), autorités régionales espagnoles et [Medi Ambient Andorre](https://www.mediambient.ad/) : sources à intégrer, pas des contours déjà présents.
- Fond OpenStreetMap atténué en niveaux de gris, sans clé API. Données du fond et données OSM éventuelles : © contributeurs OpenStreetMap, ODbL.
- Leaflet 1.9.4 : BSD-2-Clause, voir `site/vendor/LICENSE`.

La date d’un inventaire et sa précision géométrique doivent toujours accompagner son utilisation. Une carte ne permet pas de conclure seule à l’applicabilité d’une règle de protection.

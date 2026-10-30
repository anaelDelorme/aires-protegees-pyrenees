#!/usr/bin/env python3
"""Build the static atlas; optionally collect OSM or import normalized official GeoJSON.
No network access without --refresh-osm. Never replaces the output after a failed fetch.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
BBOX = (-2.0, 42.0, 3.5, 43.6)  # west, south, east, north; a study window, not the massif boundary
CATEGORIES = {'Parc national', 'PNR', 'Parc naturel', 'Réserve naturelle', 'Natura 2000',
              'Site de conservatoire', 'Autre protection', 'Projet de PNR', 'Réserve biologique',
              'Arrêté de protection', 'Conservatoire du littoral', 'Périmètre de protection',
              'Reconnaissance internationale', 'Site classé', 'Parc naturel marin'}


def normalized(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s).lower())
                   if not unicodedata.combining(c))


def classify(tags):
    title = normalized(' '.join(str(tags.get(k, '')) for k in
                               ('name', 'name:fr', 'protection_title', 'designation')))
    if any(tags.get(k) for k in ('ref:natura2000', 'ref:FR:INPN:N2000')) or any(
        term in title for term in ('natura 2000', 'special area of conservation',
                                  'special protection area', 'zona de especial proteccion',
                                  'zona especial de conservacion')):
        return 'Natura 2000'
    if 'conservatoire' in normalized(tags.get('operator', '')):
        return 'Site de conservatoire'
    if 'parc naturel regional' in title:
        return 'PNR'
    if any(term in title for term in ('national park', 'parc national', 'parque nacional', 'parc nacional')):
        return 'Parc national'
    if any(term in title for term in ('reserve', 'reserva')) or tags.get('leisure') == 'nature_reserve':
        return 'Réserve naturelle'
    if any(term in title for term in ('parc naturel', 'parque natural', 'parc natural')):
        return 'Parc naturel'
    return 'Autre protection'


def load(path):
    value = json.loads(Path(path).read_text())
    validate(value)
    return value


def validate(data):
    if data.get('type') != 'FeatureCollection':
        raise ValueError('Expected a GeoJSON FeatureCollection')
    ids = set()
    for f in data['features']:
        p = f['properties']
        if not p.get('id') or p['id'] in ids:
            raise ValueError('Missing or duplicate source ID')
        ids.add(p['id'])
        for key in ('name', 'category', 'status', 'source'):
            if not p.get(key):
                raise ValueError(f'Missing {key} on {p["id"]}')
        if p['category'] not in CATEGORIES:
            raise ValueError(f'Unknown category: {p["category"]}')
        if p.get('url') and not re.match(r'^https?://', p['url']):
            raise ValueError('Source URL must use HTTP(S)')
        if f.get('geometry', {}).get('type') not in ('Point', 'Polygon', 'MultiPolygon'):
            raise ValueError('Only points and polygonal geometries are accepted')
        if not f['geometry'].get('coordinates'):
            raise ValueError('Empty geometry')


def collect_osm():
    import requests
    import osm2geojson
    from shapely.geometry import box, shape
    west, south, east, north = BBOX
    bbox = f'{south},{west},{north},{east}'
    query = (f'[out:json][timeout:180];('
             f'nwr[boundary=protected_area]({bbox});'
             f'nwr[boundary=national_park]({bbox});'
             f'nwr[leisure=nature_reserve]({bbox});'
             f'nwr["ref:natura2000"]({bbox});'
             f');out geom;')
    response = requests.post('https://overpass-api.de/api/interpreter', data={'data': query}, timeout=240)
    response.raise_for_status()
    raw = response.json()
    if raw.get('remark'):
        raise RuntimeError(f'Overpass returned an incomplete result: {raw["remark"]}')
    if not raw.get('elements'):
        raise RuntimeError('No OSM data: refusing to publish an empty collection')
    features = osm2geojson.json2geojson(raw)['features']
    collected = datetime.now(timezone.utc).isoformat()
    result = []
    window = box(*BBOX)
    for f in features:
        original = f['properties']
        tags = original.get('tags', {})
        # Converter can include support members; only retain explicitly protected entities.
        if not (tags.get('boundary') in ('protected_area', 'national_park') or
                tags.get('leisure') == 'nature_reserve' or tags.get('ref:natura2000')):
            continue
        if f['geometry']['type'] not in ('Point', 'Polygon', 'MultiPolygon'):
            continue
        if not shape(f['geometry']).intersects(window):
            continue
        osm_type, osm_id = original['type'], original['id']
        country = {'FR': 'France', 'ES': 'Espagne', 'AD': 'Andorre'}.get(tags.get('addr:country'), '')
        f['properties'] = {
            'id': f'osm:{osm_type}/{osm_id}', 'name': tags.get('name:fr') or tags.get('name') or f'Espace OSM {osm_id}',
            'category': classify(tags), 'country': country, 'status': 'Signalé dans OSM', 'evidence': 'osm',
            'operator': tags.get('operator', ''), 'reference': tags.get('ref:natura2000', tags.get('ref', '')),
            'source': 'OpenStreetMap / Overpass — ODbL',
            'url': f'https://www.openstreetmap.org/{osm_type}/{osm_id}', 'collected_at': collected,
            'note': 'Classification automatique indicative à contrôler. Pays non renseigné si absent des tags. '
                    'Les doublons entre sources et les protections superposées ne sont pas fusionnés.'}
        result.append(f)
    if not result:
        raise RuntimeError('No usable protected entities after conversion')
    cache = ROOT / '.cache'
    cache.mkdir(exist_ok=True)
    (cache / 'overpass.json').write_text(json.dumps(raw))
    return {'type': 'FeatureCollection', 'features': result}


def build(official=(), refresh_osm=False, use_osm_cache=False):
    official_path = ROOT / 'data/france-official.geojson'
    official_features = load(official_path)['features'] if official_path.exists() else []
    official_ids = {f['properties']['reference'] for f in official_features}
    # Explicit official IDs replace documentary points. Do not merge distinct protections by proximity.
    features = [f for f in load(ROOT / 'data/curated.geojson')['features']
                if f['properties'].get('official_reference') not in official_ids]
    features += official_features
    sources = ['INPN / PatriNat — diffusion IGN Géoplateforme' if official_features else '',
               'Repères documentaires Espagne, Andorre et projet de PNR du Pays basque']
    if refresh_osm:
        osm = collect_osm()
        validate(osm)
        cache = ROOT / '.cache/osm.geojson'
        cache.write_text(json.dumps(osm, ensure_ascii=False))
    elif use_osm_cache:
        osm = load(ROOT / '.cache/osm.geojson')
    else:
        osm = None
    if osm:
        features += osm['features']
        sources.append('OpenStreetMap / Overpass (ODbL), collecte datée dans chaque fiche')
    for path in official:
        features += load(path)['features']
        sources.append(f'Import normalisé : {Path(path).name}')
    manifest_path = ROOT / 'data/france-sources.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    n_official = sum(f['properties'].get('evidence') == 'official' for f in features)
    n_points = sum(f['geometry']['type'] == 'Point' for f in features)
    result = {'type': 'FeatureCollection', 'metadata': {
        'bbox': BBOX, 'exhaustive': False, 'official_records': n_official,
        'indicative_points': n_points, 'france_layers': manifest.get('layers', []),
        'coverage': {'France': f'INPN / PatriNat : {len(manifest.get("layers", []))} couches collectées dans la fenêtre d’étude',
                     'Espagne': 'Repères documentaires, inventaires officiels à intégrer',
                     'Andorre': 'Repères documentaires, contours officiels à intégrer'},
        'notice': f'{n_official} contours officiels · {n_points} repères indicatifs. Couverture transfrontalière incomplète.',
        'provenance': ' ; '.join(s for s in sources if s) + '. Sources, dates et statut dans chaque fiche.'},
        'features': sorted(features, key=lambda f: (normalized(f['properties']['name']), f['properties']['id']))}
    validate(result)
    output = ROOT / 'site/data/areas.geojson'
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(output)
    print(f'{len(features)} enregistrements écrits dans {output}; {n_official} officiels, inventaire non exhaustif.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-osm', action='store_true')
    parser.add_argument('--use-osm-cache', action='store_true')
    parser.add_argument('--official', action='append', default=[], help='GeoJSON normalisé, voir README')
    args = parser.parse_args()
    if args.refresh_osm and args.use_osm_cache:
        parser.error('Choose either --refresh-osm or --use-osm-cache')
    build(args.official, args.refresh_osm, args.use_osm_cache)

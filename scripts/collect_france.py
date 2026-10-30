#!/usr/bin/env python3
"""Collect official INPN/PatriNat polygons distributed by IGN WFS (no hand-drawn bounds)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import requests
from shapely.geometry import box, mapping, shape
from shapely import make_valid, union_all, set_precision

if __package__:
    from .build_data import BBOX, ROOT, validate
else:
    from build_data import BBOX, ROOT, validate

ENDPOINT = 'https://data.geopf.fr/wfs/ows'
LAYERS = [
    ('patrinat_pn:parc_national', 'Parc national', 'Parc national — cœur / aire d’adhésion'),
    ('patrinat_pnm:pnm', 'Parc naturel marin', 'Parc naturel marin'),
    ('patrinat_ripn:ripn', 'Réserve naturelle', 'Réserve intégrale de parc national'),
    ('patrinat_sc:sc', 'Site classé', 'Site classé au titre du paysage'),
    ('patrinat_pnr:pnr', 'PNR', 'Parc naturel régional'),
    ('patrinat_rnn:rnn', 'Réserve naturelle', 'Réserve naturelle nationale'),
    ('patrinat_rnr:rnr', 'Réserve naturelle', 'Réserve naturelle régionale'),
    ('patrinat_rnc:pnm', 'Réserve naturelle', 'Réserve naturelle de Corse'),
    ('patrinat_rb:rb', 'Réserve biologique', 'Réserve biologique'),
    ('patrinat_apb:apb', 'Arrêté de protection', 'Arrêté de protection de biotope'),
    ('patrinat_aphn:aphn', 'Arrêté de protection', 'Arrêté de protection d’habitat naturel'),
    ('patrinat_apg:apg', 'Arrêté de protection', 'Arrêté de protection de géotope'),
    ('patrinat_sic:sic', 'Natura 2000', 'Natura 2000 — directive Habitats (SIC / ZSC)'),
    ('patrinat_zps:zps', 'Natura 2000', 'Natura 2000 — directive Oiseaux (ZPS)'),
    ('patrinat_cen:cen', 'Site de conservatoire', 'Terrain acquis des Conservatoires d’espaces naturels'),
    ('patrinat_cdl:conservatoire_littoral', 'Conservatoire du littoral', 'Terrain du Conservatoire du littoral'),
    ('patrinat_pprnn:pprnn', 'Périmètre de protection', 'Périmètre de protection de réserve naturelle nationale'),
    ('patrinat_pprnr:pprnr', 'Périmètre de protection', 'Périmètre de protection de réserve naturelle régionale'),
    ('patrinat_rncfs:rncfs', 'Autre protection', 'Réserve nationale de chasse et de faune sauvage'),
    ('patrinat_ramsar:ramsar', 'Reconnaissance internationale', 'Site Ramsar'),
    ('patrinat_bios:bios', 'Reconnaissance internationale', 'Réserve de biosphère UNESCO'),
]
TOLERANCE = 0.00005  # ~4–6 m: display simplification, never a legal boundary


def round_coordinates(coordinates):
    return [round(v, 6) if isinstance(v, (int, float)) else round_coordinates(v) for v in coordinates]


def params(layer, start=0):
    return {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature',
            'typeNames': layer, 'outputFormat': 'application/json', 'srsName': 'CRS:84',
            'bbox': ','.join(map(str, BBOX)) + ',urn:ogc:def:crs:OGC:1.3:CRS84',
            'count': 100, 'startIndex': start}


def collect_layer(spec, offline=False):
    layer, category, designation = spec
    cache = ROOT / '.cache/inpn' / (layer.replace(':', '_') + '.json')
    if offline:
        raw = json.loads(cache.read_text())
    else:
        features, start, total = [], 0, None
        while total is None or start < total:
            response = requests.get(ENDPOINT, params=params(layer, start), timeout=180)
            response.raise_for_status()
            page = response.json()
            matched = page.get('numberMatched', page.get('totalFeatures'))
            if not isinstance(matched, int):
                raise ValueError(f'{layer}: missing reliable total: {matched}')
            if total is not None and total != matched:
                raise ValueError(f'{layer}: total changed during paging')
            total = matched
            chunk = page.get('features', [])
            if not chunk and start < total:
                raise ValueError(f'{layer}: truncated response at {start}/{total}')
            features.extend(chunk)
            start += len(chunk)
        if len(features) != total:
            raise ValueError(f'{layer}: expected {total}, got {len(features)}')
        raw = {'collected_at': datetime.now(timezone.utc).isoformat(), 'features': features, 'numberMatched': total}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(raw, ensure_ascii=False))
    grouped = {}
    window = box(*BBOX)
    for f in raw['features']:
        p = f['properties']
        reference = p.get('id_mnhn')
        if not reference or not p.get('nom_site'):
            raise ValueError(f'{layer}: missing official reference or name')
        geom = shape(f['geometry'])
        if not geom.is_valid:
            geom = make_valid(geom)
        if not geom.intersects(window):
            continue
        grouped.setdefault(reference, {'properties': p, 'geometries': []})['geometries'].append(geom)
    result = []
    for reference, item in grouped.items():
        p = item['properties']
        geom = union_all(item['geometries'])
        if geom.geom_type == 'GeometryCollection':
            geom = union_all([g for g in geom.geoms if g.geom_type in ('Polygon', 'MultiPolygon')])
        if geom.is_empty or geom.geom_type not in ('Polygon', 'MultiPolygon'):
            raise ValueError(f'{layer}: nonpolygonal geometry for {reference}')
        # Keep full extent; simplify only for an interactive web map, preserving topology.
        display = geom.simplify(TOLERANCE, preserve_topology=True)
        snapped = set_precision(display, 0.000001)
        if not snapped.is_empty:
            display = snapped
        geometry = mapping(display)
        geometry['coordinates'] = round_coordinates(geometry['coordinates'])
        if not shape(geometry).is_valid:
            raise ValueError(f'{reference}: invalid display geometry')
        zone = p.get('zone')
        subtype = designation + (f' — {zone}' if zone else '')
        name = p['nom_site']
        if category == 'Parc national' and zone and zone.lower() not in name.lower():
            name += f' — {zone}'
        result.append({'type': 'Feature', 'geometry': geometry, 'properties': {
            'id': f'inpn:{reference}', 'reference': reference, 'name': name,
            'category': category, 'designation': subtype, 'country': 'France',
            'status': 'Référencé dans l’inventaire officiel', 'evidence': 'official',
            'source': 'INPN / PatriNat — diffusion IGN Géoplateforme',
            'source_layer': layer, 'url': p.get('url_fiche') or f'https://inpn.mnhn.fr/espace/protege/{reference}',
            'source_download': ENDPOINT + '?' + urlencode({**{k: v for k, v in params(layer).items() if k not in ('bbox', 'count', 'startIndex')}, 'CQL_FILTER': f"id_mnhn='{reference}'"}),
            'collected_at': raw['collected_at'], 'source_modified': p.get('modif_geo') or p.get('modif_adm'),
            'created_at': p.get('date_crea'), 'source_term_end': p.get('acte_fin'),
            'operator': p.get('gest_site') or p.get('operateur') or '',
            'source_area_ha': p.get('area_sig'),
            'license': 'Licence Ouverte / Open Licence — données INPN',
            'geometry_quality': 'official_simplified', 'simplification_degrees': TOLERANCE,
            'note': 'Contour issu du service officiel, simplifié pour l’affichage (~4–6 m), sans découpage '
                    'à la fenêtre d’étude. Pour un usage réglementaire, consulter la fiche, les actes et le '
                    'fichier source. La date de collecte ne signifie pas que le fournisseur a actualisé le statut.'}})
    digest = hashlib.sha256(cache.read_bytes()).hexdigest()
    manifest = {'layer': layer, 'category': category, 'designation': designation,
                'matched': raw['numberMatched'], 'records': len(result), 'collected_at': raw['collected_at'],
                'raw_sha256': digest, 'url': ENDPOINT + '?' + urlencode(params(layer)), 'state': 'collected'}
    print(f'{layer}: {len(result)} official records ({raw["numberMatched"]} source features)', flush=True)
    return result, manifest


def main(offline=False):
    # Every declared source must succeed. A failed refresh never overwrites the published inventory.
    with ThreadPoolExecutor(max_workers=3) as executor:
        outputs = list(executor.map(lambda spec: collect_layer(spec, offline), LAYERS))
    features = [f for result, _ in outputs for f in result]
    data = {'type': 'FeatureCollection', 'features': features}
    validate(data)
    output = ROOT / 'data/france-official.geojson'
    temp = output.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    temp.replace(output)
    report = {'provider': 'INPN / PatriNat, IGN WFS', 'bbox': BBOX,
              'simplification_degrees': TOLERANCE, 'layers': [m for _, m in outputs],
              'limitations': ['Fenêtre géographique, pas une délimitation administrative du massif.',
                             'CEN : terrains acquis renseignés dans cette couche, pas tous les sites gérés.',
                             'France uniquement. Les données sources peuvent être anciennes.',
                             'Les désignations et secteurs superposés sont des enregistrements distincts.']}
    (ROOT / 'data/france-sources.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {len(features)} official records to {output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Rebuild deterministically from cached raw responses')
    main(parser.parse_args().offline)

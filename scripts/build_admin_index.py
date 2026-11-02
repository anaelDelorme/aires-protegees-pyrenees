#!/usr/bin/env python3
"""Rebuild indicative French administrative memberships offline from retained boundaries."""
import json
from pathlib import Path
from shapely.geometry import shape
ROOT = Path(__file__).resolve().parents[1]

def build_index(areas=None):
    boundaries = json.loads((ROOT / 'data/france-administrative.geojson').read_text())
    if areas is None:
        areas = json.loads((ROOT / 'site/data/areas.geojson').read_text())
    departments = {f['properties']['code']: f['properties'] for f in boundaries['features']}
    geometries = [(f['properties']['code'], shape(f['geometry'])) for f in boundaries['features']]
    memberships = {}
    for feature in areas['features']:
        p = feature['properties']
        if p.get('country') != 'France':
            continue
        geometry = shape(feature['geometry'])
        memberships[p['id']] = [code for code, boundary in geometries
                               if boundary.intersects(geometry)
                               and (geometry.geom_type == 'Point' or boundary.intersection(geometry).area > 0)]
    result = {'metadata': boundaries['metadata'], 'departments': departments, 'memberships': memberships}
    (ROOT / 'site/data/admin-index.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Rattachements administratifs indicatifs : {len(memberships)} enregistrements français.')
    return result

if __name__ == '__main__':
    build_index()

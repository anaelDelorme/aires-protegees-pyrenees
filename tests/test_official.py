import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from shapely.geometry import shape
from scripts import collect_france
from scripts.build_data import ROOT


def feature(ref='FRTEST001', x=0):
    return {'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [
        [[x, 42.5], [x+.01, 42.5], [x+.01, 42.51], [x, 42.51], [x, 42.5]]]},
        'properties': {'id_mnhn': ref, 'nom_site': 'Site test', 'url_fiche': 'https://inpn.mnhn.fr/site/test'}}


def response(total, features):
    result = Mock()
    result.json.return_value = {'numberMatched': total, 'features': features}
    return result


class OfficialCollectorTests(unittest.TestCase):
    spec = ('test:layer', 'Réserve naturelle', 'Réserve naturelle nationale')

    def test_paging_and_offline_rebuild_keep_ids_and_collection_date(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(collect_france, 'ROOT', Path(tmp)):
            with patch.object(collect_france.requests, 'get', side_effect=[
                response(3, [feature('FRTEST001'), feature('FRTEST002', .1)]),
                response(3, [feature('FRTEST003', .2)])]) as get:
                result, manifest = collect_france.collect_layer(self.spec)
            self.assertEqual(len(result), 3)
            self.assertEqual(get.call_args_list[1].kwargs['params']['startIndex'], 2)
            self.assertEqual(manifest['matched'], 3)
            self.assertEqual(result[0]['properties']['evidence'], 'official')
            self.assertIn('CQL_FILTER', result[0]['properties']['source_download'])
            with patch.object(collect_france.requests, 'get', side_effect=AssertionError('Offline must not use network')):
                cached, cached_manifest = collect_france.collect_layer(self.spec, offline=True)
            self.assertEqual(result, cached)
            self.assertEqual(manifest, cached_manifest)

    def test_truncated_page_is_not_treated_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(collect_france, 'ROOT', Path(tmp)):
            with patch.object(collect_france.requests, 'get', side_effect=[
                response(2, [feature()]), response(2, [])]):
                with self.assertRaisesRegex(ValueError, 'truncated'):
                    collect_france.collect_layer(self.spec)
            self.assertFalse((Path(tmp) / '.cache/inpn/test_layer.json').exists())

    def test_changing_total_fails_instead_of_mixing_versions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(collect_france, 'ROOT', Path(tmp)):
            with patch.object(collect_france.requests, 'get', side_effect=[
                response(3, [feature()]), response(4, [feature('FRTEST002')])]):
                with self.assertRaisesRegex(ValueError, 'total changed'):
                    collect_france.collect_layer(self.spec)

    def test_parts_with_the_same_official_id_are_united(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(collect_france, 'ROOT', Path(tmp)):
            with patch.object(collect_france.requests, 'get', return_value=response(2, [feature(), feature(x=.03)])):
                result, manifest = collect_france.collect_layer(self.spec)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['geometry']['type'], 'MultiPolygon')
            self.assertEqual(manifest['matched'], 2)
            self.assertEqual(manifest['records'], 1)

    def test_published_official_inventory_has_valid_polygons_and_consistent_coverage(self):
        data = json.loads((ROOT / 'site/data/areas.geojson').read_text())
        official = [f for f in data['features'] if f['properties'].get('evidence') == 'official']
        self.assertGreater(len(official), 400)
        self.assertEqual(len(official), data['metadata']['official_records'])
        self.assertEqual(sum(s['records'] for s in data['metadata']['france_layers']), len(official))
        for f in official:
            geom = shape(f['geometry'])
            self.assertTrue(geom.is_valid, f['properties']['id'])
            self.assertFalse(geom.is_empty, f['properties']['id'])
            self.assertIn(geom.geom_type, ('Polygon', 'MultiPolygon'))
            self.assertEqual(f['properties']['country'], 'France')
            self.assertTrue(f['properties']['source_layer'].startswith('patrinat_'))
            self.assertTrue(f['properties']['collected_at'])
        # The initial French park points must disappear once their official polygons are available.
        ids = {f['properties']['id'] for f in data['features']}
        for old_id in ('manual:1', 'manual:2', 'manual:3', 'manual:4'):
            self.assertNotIn(old_id, ids)
        self.assertEqual(sum(f['properties']['status'] == 'Projet' for f in data['features']), 1)


if __name__ == '__main__':
    unittest.main()

import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_data import classify, validate, ROOT


class DataTests(unittest.TestCase):
    def test_classification_does_not_confuse_pnr_with_national_park(self):
        self.assertEqual(classify({'name': 'Parc naturel régional des Pyrénées catalanes'}), 'PNR')
        self.assertEqual(classify({'name': 'Parque Nacional de Ordesa y Monte Perdido'}), 'Parc national')
        self.assertEqual(classify({'name': 'Paratge Natural d’Interès Nacional de l’Albera'}), 'Autre protection')

    def test_natura_and_conservatoire(self):
        self.assertEqual(classify({'ref:natura2000': 'FR1234567'}), 'Natura 2000')
        self.assertEqual(classify({'operator': 'Conservatoire d’espaces naturels'}), 'Site de conservatoire')

    def test_project_is_separate_and_never_has_fabricated_boundary(self):
        data = json.loads((ROOT / 'data/curated.geojson').read_text())
        projects = [f for f in data['features'] if f['properties']['category'] == 'Projet de PNR']
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]['properties']['status'], 'Projet')
        self.assertEqual(projects[0]['geometry']['type'], 'Point')

    def test_published_data_and_duplicate_rejection(self):
        data = json.loads((ROOT / 'site/data/areas.geojson').read_text())
        validate(data)
        self.assertFalse(data['metadata']['exhaustive'])
        self.assertGreater(len(data['features']), 0)
        bad = copy.deepcopy(data)
        bad['features'].append(bad['features'][0])
        with self.assertRaises(ValueError):
            validate(bad)

    def test_administrative_memberships_and_cross_department_park(self):
        admin = json.loads((ROOT / 'site/data/admin-index.json').read_text())
        self.assertEqual(admin['memberships']['inpn:FR3600004'], ['65'])
        self.assertEqual(admin['memberships']['inpn:FR3300003'], ['64', '65'])
        self.assertEqual(admin['departments']['64']['region_name'], 'Nouvelle-Aquitaine')
        self.assertEqual(admin['departments']['65']['region_name'], 'Occitanie')
        data = json.loads((ROOT / 'site/data/areas.geojson').read_text())
        french_ids = {f['properties']['id'] for f in data['features'] if f['properties']['country'] == 'France'}
        self.assertEqual(set(admin['memberships']), french_ids)
        self.assertEqual(admin['metadata']['license'], 'Licence Ouverte')

    def test_reject_unsafe_source_link(self):
        data = json.loads((ROOT / 'data/curated.geojson').read_text())
        data['features'][0]['properties']['url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError):
            validate(data)


if __name__ == '__main__':
    unittest.main()

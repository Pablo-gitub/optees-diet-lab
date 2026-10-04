import importlib.util
from pathlib import Path
import unittest
import csv, gzip, json, tempfile
from contextlib import redirect_stdout
import io

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('off', ROOT / 'scripts/import_open_food_facts.py')
off = importlib.util.module_from_spec(spec)
spec.loader.exec_module(off)


class OffTests(unittest.TestCase):
    def base(self):
        return {
            'code': '0123456789012',
            'product_name': 'Pasta',
            'quantity': '500 g',
            'energy-kcal_100g': '350',
            'proteins_100g': '12',
            'fat_100g': '2',
            'carbohydrates_100g': '70',
        }

    def test_missing_is_not_zero(self):
        row = self.base()
        row['fat_100g'] = ''
        result = off.normalize(row)
        self.assertIsNone(result['fat_g_100g'])
        self.assertFalse(result['numeric_candidate'])

    def test_zero_is_preserved_and_brand_product_not_auto_admitted(self):
        row = self.base()
        row['fat_100g'] = '0'
        result = off.normalize(row)
        self.assertEqual(result['fat_g_100g'], 0)
        self.assertTrue(result['numeric_candidate'])
        self.assertFalse(result['solver_eligible'])
        self.assertEqual(result['barcode'], '0123456789012')

    def test_units_are_not_silently_converted(self):
        row = self.base()
        row['quantity'] = '200 ml'
        self.assertEqual(off.normalize(row)['nutrient_basis'], 'per_100_ml')
        row['quantity'] = 'una confezione'
        self.assertFalse(off.normalize(row)['numeric_candidate'])

    def test_energy_conversion_and_bad_macros(self):
        row = self.base()
        row['energy-kcal_100g'] = ''
        row['energy-kj_100g'] = '1464.4'
        self.assertAlmostEqual(off.normalize(row)['kcal_100g'], 350)
        row['fat_100g'] = '80'
        self.assertIn('implausible_macro_sum', off.normalize(row)['quality_flags'])

    def test_source_errors_exclude_candidate(self):
        row = self.base()
        row['data_quality_errors_tags'] = 'en:nutrition-value-over-100'
        self.assertFalse(off.normalize(row)['numeric_candidate'])

    def test_offline_import_filters_country_deduplicates_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.tsv.gz'
            base = self.base()
            base['countries_tags'] = 'en:italy'
            other = {**base, 'code': '999', 'countries_tags': 'en:france'}
            near = {**base, 'code': '998', 'countries_tags': 'en:italy-test'}
            with gzip.open(source, 'wt', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(base), delimiter='\t')
                writer.writeheader()
                writer.writerows([base, base, other, near])
            with redirect_stdout(io.StringIO()):
                off.run(root / 'out', source)
            rows = [json.loads(x) for x in (root / 'out/products.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['barcode'], '0123456789012')
            manifest = json.loads((root / 'out/manifest.json').read_text())
            self.assertEqual(manifest['scanned_rows'], 4)
            self.assertEqual(manifest['solver_eligible'], 0)
            with gzip.open(root / 'out/raw_italy.jsonl.gz', 'rt') as stream:
                self.assertEqual(json.loads(next(stream))['countries_tags'], 'en:italy')


if __name__ == '__main__':
    unittest.main()

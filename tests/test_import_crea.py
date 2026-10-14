"""T-008: tracce dichiarate distinte dai nutrienti davvero mancanti."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import import_crea
from import_crea import parse_food,number


def sheet(values):
    rows=''.join('<tr>'+''.join('<td>'+v+'</td>' for v in [name,'g',value,'','','','','',''])+'</tr>' for name,value in values)
    return '<table class="toptable"><tr><td><h1>Alimento sintetico</h1></td></tr><tr><td>Codice Alimento</td><td>123456</td></tr></table><table class="tblmain">'+rows+'</table>'


class ImportCreaTests(unittest.TestCase):
    def test_trace_numeric_and_missing_keep_distinct_provenance(self):
        food=parse_food(sheet([('Lipidi (g)','tr'),('Energia (kcal)','42,5'),('Proteine (g)',''),('Carboidrati disponibili (g)','n.d.')]),'123456')
        self.assertEqual(food['fat_g_100g'],0)
        self.assertEqual(food['kcal_100g'],42.5)
        self.assertIsNone(food['protein_g_100g'])
        self.assertIsNone(food['carbs_available_g_100g'])
        self.assertEqual(food['trace_nutrients'],['fat_g_100g'])
        trace=next(n for n in food['nutrients'] if n['name']=='Lipidi (g)')
        self.assertEqual(trace['value_100g_raw'],'tr')
        self.assertEqual(trace['value_100g_provenance'],'tracce (tr) nel CREA')

    def test_protein_trace_is_recognized_without_changing_label(self):
        food=parse_food(sheet([('Proteine (g)','tr'),('Lipidi (g)','0')]),'123456')
        self.assertEqual(food['protein_g_100g'],0)
        self.assertEqual(food['trace_nutrients'],['protein_g_100g'])

    def test_missing_and_other_symbols_are_never_invented_zeros(self):
        for value in ('','n.d.','ND','-','<0.1','tracce'):
            with self.subTest(value=value):self.assertIsNone(number(value))
        self.assertEqual(number('  TR  '),0)
        self.assertEqual(number('0'),0)

    def test_offline_missing_page_leaves_existing_dataset_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw.mkdir()
            (raw/'index.html').write_text('<a href="/tabelle-nutrizionali/123456">Sintetico</a>')
            for filename in ('prefazione.html','legenda.html'):(raw/filename).write_text('Cache sintetica')
            target=root/'foods.csv';target.write_text('dataset precedente')
            with patch.object(import_crea,'ROOT',root),patch.object(import_crea,'RAW',raw),patch('sys.argv',['import_crea','--offline']),patch.object(import_crea,'urlopen',side_effect=AssertionError('Download vietato')):
                with self.assertRaisesRegex(FileNotFoundError,'123456.html'):import_crea.main()
            self.assertEqual(target.read_text(),'dataset precedente')

    def test_public_apple_and_egg_are_complete_solver_candidates(self):
        import json
        from plan_diet_day import load_foods,formulate,NUTRIENTS
        root=Path(__file__).resolve().parents[1]
        foods=load_foods();config=json.loads((root/'config/demo-diet-day.json').read_text());config['mode']='free'
        _,choices,_=formulate(config,foods)
        for code,trace in [('007120','fat_g_100g'),('181100','carbs_available_g_100g')]:
            with self.subTest(code=code):
                self.assertTrue(all(foods[code][key] for key in NUTRIENTS))
                self.assertEqual(float(foods[code][trace]),0)
                self.assertIn(trace,json.loads(foods[code]['trace_nutrients']))
                self.assertIn(code,{c['food_id'] for c in choices})

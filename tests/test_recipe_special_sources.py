import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import match_recipe_ingredients as matching
import calculate_recipe_nutrients as calc
from recipe_special_sources import POLICY,special_food
from plan_recipe import formulate_recipe,decode_recipe
from test_recipe_solver import solve
from ingredient_overlap import canonical

class RecipeSpecialSourcesTests(unittest.TestCase):
    def setUp(self):
        self.dictionary=matching.load_dictionary(matching.DEFAULT_DICT);self.crea=matching.load_crea(matching.DEFAULT_CREA);self.approved=matching.load_approved_mappings(matching.DEFAULT_APPROVED)
    def process(self,name,grams=None,unit='toTaste',quantity=None,servings=2,**extra):
        ingredient=dict(key='1',name=name,grams_whole_recipe=grams,unit=unit,quantity=quantity,**extra)
        return matching.process_ingredient(ingredient,dict(id='test:special',servings=servings),self.dictionary,self.approved,self.crea,None)
    def test_exclusion_from_batches_across_variants_and_specific_review(self):
        # USDA precedence still resolves the onion canonical, but no approval leaks.
        r=self.process('  SPRING ONION  ',grams=50,source_nutrition_reference=dict(id='170000'))
        self.assertNotEqual(r['match_status'],'approved')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);proposals=root/'ingredient-proposals';proposals.mkdir()
            (root/'approved.json').write_text(json.dumps(dict(canonical_approvals={'cipolla_cruda':dict(source='CREA',id='005300',reviewed=True,state_checked=True)},recipe_overrides={})))
            (proposals/'batch-01.json').write_text(json.dumps(dict(proposals=[dict(canonical_id='cipolla_cruda',raw_names_excluded=[dict(name='Onion',reason='excluded')])])))
            data=matching.load_approved_mappings(root/'approved.json')
            ing=dict(key='1',name='ONION',grams_whole_recipe=50,unit='g',quantity=50)
            r=matching.process_ingredient(ing,dict(id='test:special'),self.dictionary,data,self.crea,None)
            self.assertTrue(r['approval_excluded']);self.assertFalse(r['reviewed'])
            data['recipe_overrides']={'test:special':{'1':dict(source='CREA',id='005300',reviewed=True,state_checked=True)}}
            self.assertEqual(matching.process_ingredient(ing,dict(id='test:special'),self.dictionary,data,self.crea,None)['match_status'],'approved')
            matching.save_approved_mappings(data,root/'saved.json');self.assertNotIn('_raw_names_excluded',json.loads((root/'saved.json').read_text()))
    def test_trace_is_declared_zero_without_inventing_missing_weight_or_massive_zero(self):
        for name in ['Salt','Black pepper','Dried oregano','Bay leaf','Vanilla extract','Ground nutmeg']:
            r=self.process(name);self.assertEqual(r['selected_candidate']['source'],'condiment',name);self.assertEqual(r['declared_kcal'],0);self.assertIsNone(r['grams']);self.assertEqual(r['quantity_status'],'trace')
        r=self.process('Salt',grams=4,unit='g');self.assertEqual(r['match_status'],'approved')
        for name in ['Salt','Vanilla extract']:
            self.assertNotEqual((self.process(name,grams=50,unit='g').get('selected_candidate') or {}).get('source'),'condiment')
        self.assertEqual(self.process('Fresh mint',grams=4,unit='g')['selected_candidate']['trace_class'],'aromatic')
        self.assertEqual(self.process('Salt and pepper')['selected_candidate']['source'],'condiment')
        self.approved['recipe_overrides']={'test:special':{'1':dict(source='condiment',id='trace',reviewed=True,state_checked=True)}}
        override=self.process('Salt')
        self.assertEqual(override['quantity_status'],'trace');self.assertEqual(override['selected_candidate']['declared_kcal'],0)
        self.assertIsNone(canonical('special',dict(special=dict(source='condiment',source_id='trace',name='Unknown English spice'))))
    def test_stock_never_concentrate_even_bad_shared_approval_ml_l_and_calculation(self):
        self.approved['canonical_approvals']['brodo_vegetale']=dict(source='CREA',id='503010',reviewed=True,state_checked=True)
        r=self.process('Vegetable stock',unit='ml',quantity=500);self.assertEqual(r['grams'],500);self.assertEqual(r['selected_candidate']['source'],'stock')
        self.assertEqual(self.process('Vegetable stock',unit='l',quantity=.5)['grams'],500)
        for name in ('Vegetable stock cubes','Vegetable stock or milk'):
            self.assertNotEqual((self.process(name,grams=500).get('selected_candidate') or {}).get('source'),'stock')
        c=matching.find_canonical_ingredient(dict(name='Vegetable stock'),self.dictionary)
        self.assertFalse(any(i['id']=='503010' for i in matching.match_crea_candidates(c,{},self.crea)))
        food=special_food('stock','cube_1_50',calc.food_lookup)
        for n in matching.NUTRIENTS:self.assertAlmostEqual(food[n],float(self.crea['503010'][n])*.02)
        self.assertIsNone(canonical('stock',dict(stock=dict(source='stock',source_id='cube_1_50',name=food['name']))))
    def test_trace_export_and_calculator_and_real_solver_format(self):
        salt=self.process('Salt');stock=self.process('Vegetable stock',grams=500,unit='ml',quantity=500)
        stock['ingredient_key']='2'
        recipe=dict(id='test:special',title='Test',source='test',cuisine='Italian',servings=2,solver_ready=True,ingredients=[salt,stock])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);matching.export_solver_recipes([recipe],root/'solver.json');matching.export_recipe_mappings([recipe],root)
            model=json.loads((root/'solver.json').read_text())['recipes'][0]
            self.assertEqual(model['trace_condiments'][0]['grams'],None);self.assertEqual(len(model['ingredients']),1)
            mappings=json.loads((root/'test_special.json').read_text())
            source=dict(id='test:special',servings=2,ingredients=[dict(key='1',name='Salt',grams_whole_recipe=None),dict(key='2',name='Vegetable stock',grams_whole_recipe=500)])
            calculated=calc.calculate(source,mappings);self.assertTrue(calculated['complete']);self.assertEqual(calculated['ingredient_sources'][0]['declared_kcal'],0)
            self.assertAlmostEqual(calculated['whole_recipe']['kcal'],float(self.crea['503010']['kcal_100g'])*.1,places=3)
            config=json.loads((matching.ROOT/'config/demo-recipe.json').read_text());config.update(scale_min=1,scale_max=1,flexibility=0)
            config['targets']={n:dict(min=max(0,v-1),target=max(.1,v),max=v+1) for n,v in calculated['per_serving'].items()}
            p,choices,ratios=formulate_recipe(model,config);result=solve(p);self.assertEqual(result['mathematical_status'],'optimal')
            decoded=decode_recipe(model,config,p,choices,result);self.assertEqual(len(decoded['trace_condiments']),1)
            mappings['1']['grams_override']=50;self.assertFalse(calc.calculate(source,mappings)['complete'])

    def test_only_three_salt_pepper_compounds_are_traces(self):
        for name in ('Salt and pepper','salt & pepper','salt and black pepper','  SALT   AND PEPPER  '):
            row=self.process(name);self.assertEqual(row['selected_candidate']['source'],'condiment');self.assertIsNone(row['grams'])
        for name in ('salt and sugar','salt & garlic','salt and pepper and sugar','pepper and salt'):
            self.assertNotEqual((self.process(name).get('selected_candidate') or {}).get('source'),'condiment')
        self.assertNotEqual((self.process('salt and pepper',note='and sugar').get('selected_candidate') or {}).get('source'),'condiment')
    def test_trace_whitelist_can_be_extended_without_allowing_compounds(self):
        from unittest.mock import patch
        with patch.dict(POLICY['trace_condiment'],exact_names=POLICY['trace_condiment']['exact_names']+['test dried spice','salt and sugar']):
            self.assertEqual(self.process('test dried spice')['selected_candidate']['source'],'condiment')
            self.assertNotEqual((self.process('salt and sugar').get('selected_candidate') or {}).get('source'),'condiment')
    def test_approved_conversions_require_author_source_and_compatible_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'conversions.json';approved=Path(tmp)/'approved.json'
            matching.save_approved_mappings(self.approved,approved)
            matching.approve_conversion('cipolla_cruda','piece',100,'Fonte sintetica verificata','Autore test',path,approved)
            self.dictionary['_approved_conversions']=matching.load_conversions(path)
            self.dictionary['_approved_conversion_canonicals']={'cipolla_cruda'}
            row=self.process('Onion',unit='piece',quantity=2)
            self.assertEqual(row['grams'],200);self.assertEqual(row['quantity_status'],'resolved');self.assertIn('Autore test',row['quantity_note'])
            del self.approved['canonical_approvals']['cipolla_cruda']
            self.assertNotEqual(self.process('Onion',unit='piece',quantity=2)['quantity_status'],'resolved')
            for args in [('missing','piece',100,'source','author'),('cipolla_cruda','piece',float('nan'),'source','author'),('cipolla_cruda','piece',100,None,'author'),('cipolla_cruda','piece',100,'source',None)]:
                with self.assertRaises(ValueError):matching.approve_conversion(*args,path,approved)

    def test_aromatic_requested_examples_and_thresholds(self):
        for name,unit,quantity,servings in [('3 cloves garlic','clove',3,4),('1 bunch parsley','bunch',1,1),('juice of 1 lemon',None,None,4)]:
            row=self.process(name,unit=unit,quantity=quantity,servings=servings)
            self.assertEqual(row['selected_candidate']['trace_class'],'aromatic',name)
            self.assertEqual(row['declared_kcal'],0);self.assertEqual(row['quantity_status'],'trace')
        for name,unit,quantity,servings in [('1 head garlic','head',1,2),('2 tbsp pesto','tbsp',2,1),('juice of 1 lemon',None,None,1)]:
            row=self.process(name,unit=unit,quantity=quantity,servings=servings)
            self.assertNotEqual((row.get('selected_candidate') or {}).get('source'),'condiment',name)
        for name,limit in [('fresh basil',20),('garlic',10),('fresh ginger',15),('fresh chilli',25),('lemon juice',30),('lemongrass',10),('kaffir lime leaves',10)]:
            self.assertEqual(self.process(name,grams=limit*2)['selected_candidate']['trace_class'],'aromatic',name)
            self.assertNotEqual((self.process(name,grams=limit*2+.1).get('selected_candidate') or {}).get('source'),'condiment',name)
        for name in ('olive oil','butter','cream','sugar','honey','curry paste','nuts','cumin seeds','cheese','sweet pepper','onion'):
            self.assertNotEqual((self.process(name,grams=1).get('selected_candidate') or {}).get('source'),'condiment',name)
        self.assertEqual(self.process('soy sauce',unit='tbsp',quantity=1,servings=1)['selected_candidate']['trace_class'],'aromatic')
        self.assertNotEqual((self.process('soy sauce',unit='tbsp',quantity=2,servings=1).get('selected_candidate') or {}).get('source'),'condiment')

    def test_aromatic_units_and_approved_conversion(self):
        for unit in ('sprig','leaf','bunch','handful'):
            self.assertEqual(self.process('parsley',unit=unit,quantity=2,servings=1)['quantity_status'],'trace')
        self.assertEqual(self.process('parsley',grams=100,unit='bunch',quantity=1,servings=1)['quantity_status'],'trace')
        for unit in ('pinch','q.b.','to taste'):
            self.assertEqual(self.process('fresh basil',unit=unit)['quantity_status'],'trace')
        from recipe_special_sources import aromatic_trace
        ingredient=dict(name='garlic',quantity=3,unit='clove')
        conversions={'aglio':{'clove':dict(grams=3,source='Fonte sintetica',approved_by='Test')}}
        trace=aromatic_trace(ingredient,{'id':'aglio'},{'servings':4},None,conversions)
        self.assertEqual(trace['conversion']['grams'],3)
        self.assertIsNone(aromatic_trace(dict(ingredient,quantity=20),{'id':'aglio'},{'servings':4},None,conversions))
        self.assertIsNone(aromatic_trace(ingredient,{'id':'aglio'},{'servings':4},None,{}))
        self.dictionary['_approved_conversions']={}
        self.assertNotEqual((self.process('garlic',unit='clove',quantity=3,servings=4).get('selected_candidate') or {}).get('source'),'condiment')
        self.assertIsNone(aromatic_trace(dict(name='ginger',unit='piece',quantity=1),{'id':'zenzero_fresco'},{'servings':2},None,{}))

    def test_aromatic_export_ignores_mass_but_keeps_shopping_trace_and_calculator_guard(self):
        herb=self.process('fresh basil',grams=30,servings=2)
        stock=self.process('Vegetable stock',grams=500);stock['ingredient_key']='2'
        recipe=dict(id='test:aromatic',title='Sintetica',servings=2,source='test',cuisine='Italian',solver_ready=True,ingredients=[herb,stock])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);matching.export_solver_recipes([recipe],root/'solver.json');matching.export_recipe_mappings([recipe],root)
            model=json.loads((root/'solver.json').read_text())['recipes'][0]
            self.assertEqual(len(model['ingredients']),1)
            self.assertEqual(model['trace_condiments'][0]['trace_class'],'aromatic')
            self.assertIsNone(model['trace_condiments'][0]['grams'])
            source=dict(id='test:aromatic',servings=2,ingredients=[dict(key='1',name='fresh basil',grams_whole_recipe=30),dict(key='2',name='Vegetable stock',grams_whole_recipe=500)])
            mappings=json.loads((root/'test_aromatic.json').read_text());values=calc.calculate(source,mappings)
            self.assertTrue(values['complete']);self.assertEqual(values['ingredient_sources'][0]['declared_kcal'],0)
            mappings['1']['grams_override']=41
            self.assertFalse(calc.calculate(source,mappings)['complete'])

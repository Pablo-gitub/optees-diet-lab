import copy
import json
import sys
import unittest
from pathlib import Path
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from plan_recipe import formulate_recipe,decode_recipe,templates,values_verified


def solve(problem):
    rows=problem['constraints'];lo=[];hi=[]
    for r in rows:
        lo.append(r['rhs'] if r['relation'] in ['=','>='] else -np.inf)
        hi.append(r['rhs'] if r['relation'] in ['=','<='] else np.inf)
    result=milp(np.array(problem['objective']['coefficients']),integrality=np.array([int(v['integrality']=='B') for v in problem['variables']]),bounds=Bounds([v['lb'] for v in problem['variables']],[v['ub'] for v in problem['variables']]),constraints=LinearConstraint(np.array([r['coefficients'] for r in rows]),lo,hi))
    return {'mathematical_status':'optimal' if result.success else 'infeasible','validation':{'status':'verified'},'result':{'variables':[] if result.x is None else [{'name':v['name'],'value':float(x)} for v,x in zip(problem['variables'],result.x)]}}


class RecipeSolverTests(unittest.TestCase):
    def config(self):return json.loads((ROOT/'config/demo-recipe.json').read_text())
    def test_real_catalog_recipe_quantities_and_lexicographic_ratios(self):
        recipe=templates()[0];config=self.config();problem,choices,ratios=formulate_recipe(recipe,config)
        first=solve(problem);self.assertEqual(first['mathematical_status'],'optimal')
        values=values_verified(problem,first);score=sum(c*x for c,x in zip(problem['objective']['coefficients'],values))
        problem['constraints'].append(dict(coefficients=problem['objective']['coefficients'][:],relation='<=',rhs=score+1e-7));problem['objective']['coefficients']=ratios
        second=solve(problem);record=decode_recipe(recipe,config,problem,choices,second)
        self.assertEqual(len(record['selections']),4)
        self.assertEqual(len({s['key'] for s in record['selections']}),4)
        self.assertLessEqual(record['nutrient_score'],score+1e-5)
        for s in record['selections']:self.assertLessEqual(abs(s['proportion_change_percent']),10.001)
        for n,spec in config['targets'].items():self.assertGreaterEqual(record['nutrients'][n],spec['min']-1e-3);self.assertLessEqual(record['nutrients'][n],spec['max']+1e-3)
    def test_all_reviewed_templates_admit_reference_portions(self):
        for recipe in templates():
            values=recipe.get('reference_nutrition')
            if not values:continue
            config=dict(prefer_branded=False,flexibility=0,scale_min=1,scale_max=1,targets={n:dict(min=max(.000001,v*.99),target=max(.000001,v),max=max(.000001,v*1.01)) for n,v in values.items()})
            problem,choices,_=formulate_recipe(recipe,config)
            result=decode_recipe(recipe,config,problem,choices,solve(problem))
            self.assertEqual(result['status'],'optimal',recipe['id'])
            for n,v in values.items():self.assertAlmostEqual(result['nutrients'][n],v,places=3)

    def test_reviewed_water_has_zero_nutrients_without_dropping_weight(self):
        recipe=dict(id='water-test',title='Water',ingredients=[dict(key='water',name='Acqua',state='pura',grams_per_reference_portion=100,candidates=[dict(source='water',id='water',reviewed=True,state_checked=True)]),templates()[0]['ingredients'][0]])
        config=dict(flexibility=0,scale_min=1,scale_max=1,targets={'kcal':dict(min=200,target=280,max=400)})
        p,c,_=formulate_recipe(recipe,config);r=decode_recipe(recipe,config,p,c,solve(p))
        water=next(s for s in r['selections'] if s['source']=='water');self.assertEqual(water['grams'],100)
        self.assertEqual(next(x for x in c if x['source']=='water')['nutrients']['kcal'],0)

    def test_zero_flex_preserves_every_ratio(self):
        config=self.config();config['flexibility']=0
        problem,choices,_=formulate_recipe(templates()[0],config);record=decode_recipe(templates()[0],config,problem,choices,solve(problem))
        self.assertEqual(record['status'],'optimal')
        self.assertTrue(all(s['proportion_change_percent']==0 for s in record['selections']))
    def test_brand_selection_changes_with_nutrient_target(self):
        recipe=dict(id='test',title='Test',ingredients=[dict(key='a',name='a',state='dry',grams_per_reference_portion=100,candidates=[dict(source='test',id=id,reviewed=True,state_checked=True) for id in ['low','high']])])
        def lookup(source,id):return dict(name=id,nutrient_basis='per_100_g',kcal_100g=200 if id=='low' else 400,protein_g_100g=10,fat_g_100g=2,carbs_available_g_100g=30)
        for target,expected in [(200,'low'),(400,'high')]:
            config=dict(flexibility=0,scale_min=1,scale_max=1,targets={'kcal':dict(min=target,target=target,max=target)})
            p,c,_=formulate_recipe(recipe,config,lookup);r=decode_recipe(recipe,config,p,c,solve(p));self.assertEqual(r['selections'][0]['id'],expected)
    def test_infeasible_target_is_not_returned_as_a_plan(self):
        config=self.config();config['targets']['kcal']=dict(min=5000,target=5000,max=5000)
        p,c,_=formulate_recipe(templates()[0],config);r=decode_recipe(templates()[0],config,p,c,solve(p))
        self.assertEqual(r['status'],'infeasible');self.assertEqual(r['selections'],[])
    def test_missing_data_unreviewed_mapping_and_exclusions(self):
        recipe=copy.deepcopy(templates()[0]);config=self.config()
        config['disabled_products']=[c['source']+':'+c['id'] for c in recipe['ingredients'][0]['candidates'] if c['source']=='Open Food Facts'];config['excluded_crea_ids']=['000800']
        with self.assertRaises(ValueError):formulate_recipe(recipe,config)
        recipe['ingredients'][0]['candidates'][0]['state_checked']=False
        config=self.config();config['prefer_branded']=False
        with self.assertRaises(ValueError):formulate_recipe(recipe,config)
        def missing(source,id):return {'name':'unknown','kcal_100g':None}
        with self.assertRaises(ValueError):formulate_recipe(templates()[0],self.config(),missing)
    def test_branded_priority_and_fallback_after_disabling_all_brands(self):
        recipe=templates()[0];config=self.config()
        _,choices,_=formulate_recipe(recipe,config)
        pasta=[c for c in choices if c['key']=='pasta']
        self.assertTrue(pasta)
        self.assertTrue(all(c['source']=='Open Food Facts' for c in pasta))
        config['disabled_products']=[c['source']+':'+c['id'] for c in recipe['ingredients'][0]['candidates'] if c['source']=='Open Food Facts']
        _,choices,_=formulate_recipe(recipe,config)
        self.assertEqual([c['source'] for c in choices if c['key']=='pasta'],['CREA'])

    def test_invalid_branded_nutrition_does_not_hide_generic_fallback(self):
        def lookup(source,identifier):
            return dict(name=identifier,nutrient_basis='per_100_g',kcal_100g=None if source=='Open Food Facts' else 350,protein_g_100g=10,fat_g_100g=2,carbs_available_g_100g=50)
        _,choices,_=formulate_recipe(templates()[0],self.config(),lookup)
        self.assertTrue(all(c['source']=='CREA' for c in choices))

    def test_bad_limits_and_unknown_nutrients_rejected(self):
        for changes in [dict(flexibility=.3),dict(flexibility=float('nan')),dict(scale_min=True),dict(scale_max=.2),dict(targets={}),dict(targets={'unknown':{}})]:
            with self.assertRaises(ValueError):formulate_recipe(templates()[0],dict(self.config(),**changes))
    def test_unverified_or_invalid_solution_rejected(self):
        p,c,_=formulate_recipe(templates()[0],self.config());r=solve(p);r['validation']['status']='unverified'
        with self.assertRaises(ValueError):decode_recipe(templates()[0],self.config(),p,c,r)
        r=solve(p);r['result']['variables'][0]['value']=100
        with self.assertRaises(ValueError):decode_recipe(templates()[0],self.config(),p,c,r)

if __name__=='__main__':unittest.main()

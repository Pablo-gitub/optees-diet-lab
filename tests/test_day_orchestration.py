import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from day_orchestration import orchestrate_day,distance,plan_diff,exploration_score,context_key
from plan_diet_day import load_foods
from test_recipe_solver import solve

class OrchestrationTests(unittest.TestCase):
    def config(self):
        c=json.loads((ROOT/'config/demo-diet-day.json').read_text());c['mode']='free';c['portion_bounds_g']={i:[40,40] for i in ['000800','000100','000530']};c['portion_bounds_g'].update({i:[120,120] for i in ['106500','121410','181100','123610','004005','004125','004505']});c['portion_bounds_g'].update({i:[100,100] for i in ['005730','006600','005410','007120','007260']});c['portion_bounds_g']['009210']=[10,10];return c
    def run_chain(self,request=None,config=None,**kwargs):
        async def fake(session,p):return solve(p)
        with patch('multiobjective_day.solve_problem',side_effect=fake):return asyncio.run(orchestrate_day(None,config or self.config(),load_foods(),request or dict(pool_size=5,k=4,time_limit=120),**kwargs))
    def test_verified_diverse_near_optimal_unique_roles_and_diff(self):
        r=self.run_chain();self.assertTrue(r['plans']);self.assertEqual(len({p['role'] for p in r['plans']}),len(r['plans']))
        best=r['plans'][0];self.assertIsNone(best['diff'])
        for i,p in enumerate(r['plans']):
            self.assertTrue(p['constraint_report']['all_respected']);self.assertTrue(p['constraint_report']['verified'])
            # 8.9 minimizes overlap inside hard nutritional bounds; epsilon
            # is a reported reference, not a reason to discard feasible diversity.
            targets=self.config()['main_meals_targets']
            for nutrient,spec in targets.items():
                self.assertGreaterEqual(p['nutrients'][nutrient.replace('_100g','')],spec['min']-1e-3)
                self.assertLessEqual(p['nutrients'][nutrient.replace('_100g','')],spec['max']+1e-3)
            self.assertEqual(p['robustness']['status'],'unavailable');self.assertNotEqual(p['role'],'robust')
            for q in r['plans'][:i]:self.assertGreaterEqual(distance(q,p),r['pool']['min_distance'])
            if i:
                before={(s['meal'],s['food_id']) for s in best['selections']};after={(s['meal'],s['food_id']) for s in p['selections']}
                diff=p['diff'];self.assertEqual((before-{(s['meal'],s['food_id']) for s in diff['removed']})|{(s['meal'],s['food_id']) for s in diff['added']},after)
    def test_reproducibility_and_legacy_warning(self):
        request=dict(pool_size=4,k=4,time_limit=120,seed=17,strategy='unknown')
        self.assertEqual(self.run_chain(request),self.run_chain(request))
        self.assertIn('legacy_strategy_ignored',[x['code'] for x in self.run_chain(request)['warnings']])
    def test_target_warning_and_infeasible_never_relaxes_bounds(self):
        c=self.config();c['main_meals_targets']['kcal_100g']['target']=1400
        self.assertIn('targets_inconsistent',[x['code'] for x in self.run_chain(config=c)['warnings']])
        c['excluded_crea_ids']=['000800','000100','000530'];r=self.run_chain(config=c)
        self.assertEqual(r['status'],'infeasible');self.assertFalse(r['plans'])
    def test_bandit_feature_context_and_no_observation_mutation(self):
        observations=[('protein:fish',1.)];before=copy.deepcopy(observations)
        r=self.run_chain(observations=observations);self.assertEqual(observations,before)
        for p in r['plans']:self.assertTrue(all(not arm in ('balanced','minmax','maxmin') for arm in p['arms']))
        c=self.config();old=context_key(c);c['main_meals_targets']['protein_g_100g']['target']=66;self.assertNotEqual(context_key(c),old)
    def test_robustness_is_separate_ranking(self):
        health=dict(version='test',usable_consumption_baseline=True,consumption_scenarios=dict(low_kcal=1500,central_kcal=1800,high_kcal=2100))
        r=self.run_chain(health=health,balance=-300)
        for p in r['plans']:
            self.assertEqual(p['robustness']['status'],'available')
            self.assertAlmostEqual(p['robustness']['scenarios']['low'],abs(p['nutrients']['kcal']-1500+300))
    def test_invalid_request(self):
        with self.assertRaises(ValueError):self.run_chain(dict(k=True))

    def test_best_has_no_distance_reason_and_singleton_has_one_warning(self):
        r=self.run_chain(dict(k=1,pool_size=1))
        self.assertFalse(any('diversi dal riferimento' in reason for reason in r['plans'][0]['explanation']['reasons']))
        c=self.config();c['locked_meals']={meal:[dict(food_id=s['food_id'],grams=s['grams'],source='CREA',reference_id=s['food_id']) for s in r['plans'][0]['selections'] if s['meal']==meal] for meal in ('lunch','dinner')}
        r=self.run_chain(config=c)
        self.assertEqual(len(r['plans']),1)
        self.assertEqual([w['code'] for w in r['warnings'] if w['code'] in ('diversity_relaxed','limited_alternatives')],['limited_alternatives'])

class WeighablePortionsTests(unittest.TestCase):
    def test_integer_portions_and_recomputed_totals(self):
        c=OrchestrationTests().config()
        async def fake(session,p):return solve(p)
        with patch('multiobjective_day.solve_problem',side_effect=fake):r=asyncio.run(orchestrate_day(None,c,load_foods(),dict(pool_size=4,k=4,time_limit=120)))
        foods=load_foods()
        for p in r['plans']:
            for s in p['selections']:self.assertIsInstance(s['grams'],int);self.assertEqual(s['grams']%5,0)
            for n in ['kcal','protein_g','fat_g','carbs_available_g']:
                total=sum(float(foods[s['food_id']][n+'_100g'])*s['grams']/100 for s in p['selections'])
                self.assertAlmostEqual(total,p['nutrients'][n],places=2)
    def test_fractional_integer_variable_rejected(self):
        from plan_recipe import values_verified
        problem=dict(variables=[dict(name='steps',lb=0,ub=10,integrality='I')],constraints=[])
        result=dict(validation=dict(status='verified'),result=dict(variables=[dict(name='steps',value=2.5)]))
        with self.assertRaises(ValueError):values_verified(problem,result)

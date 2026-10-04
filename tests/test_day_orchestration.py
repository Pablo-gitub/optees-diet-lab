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
        c=json.loads((ROOT/'config/demo-diet-day.json').read_text());c['mode']='free';return c
    def run_chain(self,request=None,config=None,**kwargs):
        async def fake(session,p):return solve(p)
        with patch('multiobjective_day.solve_problem',side_effect=fake):return asyncio.run(orchestrate_day(None,config or self.config(),load_foods(),request or dict(pool_size=5,k=4,time_limit=120),**kwargs))
    def test_verified_diverse_near_optimal_unique_roles_and_diff(self):
        r=self.run_chain();self.assertTrue(r['plans']);self.assertEqual(len({p['role'] for p in r['plans']}),len(r['plans']))
        best=r['plans'][0];self.assertIsNone(best['diff'])
        for i,p in enumerate(r['plans']):
            self.assertTrue(p['constraint_report']['all_respected']);self.assertTrue(p['constraint_report']['verified'])
            self.assertLessEqual(p['objectives']['nutrition_error'],r['pool']['near_optimal_limit']+1e-6)
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

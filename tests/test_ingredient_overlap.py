import asyncio
import copy
import time
import unittest
from unittest.mock import patch
from ingredient_overlap import canonical,amounts,overlap,cuts,minimax_candidate,report
from plan_recipe import values_verified
from test_recipe_solver import solve
import test_day_orchestration as day_tests
import test_week_orchestration as week_tests
from plan_diet_day import load_foods
from week_orchestration import generate_week

class IngredientOverlapTests(unittest.TestCase):
    def plan(self,*items):return dict(selections=[dict(meal='lunch',food_id=i,grams=g) for i,g in items])
    def test_canonical_brand_categories_and_recipe_fractions(self):
        foods=load_foods();foods['brand']=dict(source='OFF',source_id='8076800195057',name='Spaghetti Barilla')
        self.assertEqual(canonical('brand',foods),canonical('000800',foods))
        self.assertIsNone(canonical('009210',foods))
        foods['salt']=dict(source='user_label',source_id='salt',name='Sale marino')
        foods['unknown_brand']=dict(source='OFF',source_id='unmapped',name='Prodotto da classificare')
        foods['other_brand']=dict(source='user_label',source_id='other',name='Altro da classificare')
        self.assertEqual(canonical('unknown_brand',foods),canonical('other_brand',foods))
        self.assertIsNone(canonical('salt',foods));self.assertIsNotNone(canonical('005300',foods))
        a=amounts(self.plan(('brand',100),('009210',30)),foods);b=amounts(self.plan(('000800',10)),foods)
        self.assertEqual(overlap(a,b),1)
        recipe=amounts(self.plan(('recipe:vegetable_puree',200)),foods)
        self.assertEqual(sum(recipe.values()),100)
        foods['personal_oil']=dict(source='user_label',source_id='oil',name='Una marca')
        profile=dict(food_preferences=dict(preferred_products={'009210':dict(source='user_label',id='oil')}))
        self.assertIsNone(canonical('personal_oil',foods,profile))
        foods['locked_recipe']=dict(source='recipe',source_id='run:test',name='Ricetta')
        profile['_recipe_runs']={'run:test':dict(status='optimal',selections=[dict(source='CREA',id='000800',food='Pasta',grams=100),dict(source='CREA',id='009210',food='Olio',grams=20)])}
        value=amounts(self.plan(('locked_recipe',240)),foods,profile)
        self.assertAlmostEqual(value['pasta'],200)
    def fixture(self,shared=False):
        foods={'shared':dict(name='Alimento comune'),'a':dict(name='Alimento A'),'b':dict(name='Alimento B'),'c':dict(name='Alimento C')}
        choices=[dict(food_id=i,meal='lunch',q=n*2,y=n*2+1) for n,i in enumerate(foods)]
        variables=[];rows=[]
        for c in choices:
            variables.extend([dict(name=c['food_id']+'_g',lb=0,ub=100,integrality='C'),dict(name=c['food_id']+'_y',lb=0,ub=1,integrality='B')])
            r=[0.]*8;r[c['q']]=1;r[c['y']]=-100;rows.append(dict(coefficients=r,relation='=',rhs=0))
        r=[0.]*8
        for c in choices:r[c['q']]=1
        rows.append(dict(coefficients=r,relation='=',rhs=200 if shared else 100))
        r=[0.]*8;r[0]=1;rows.append(dict(coefficients=r,relation='=',rhs=100 if shared else 0))
        return dict(variables=variables,constraints=rows,objective=dict(coefficients=[0.]*8,sense='min'),solver=dict(time_limit=5)),choices,foods
    def test_linear_cuts_against_every_previous_both_directions(self):
        p,choices,foods=self.fixture();previous=[self.plan(('a',100)),self.plan(('b',100))]
        model=cuts(p,choices,previous,foods,.1);r=solve(model);values_verified(model,r)
        by={v['name']:v['value'] for v in r['result']['variables']};self.assertAlmostEqual(by['c_g'],100)
        self.assertEqual(p['variables'][0]['name'],'shared_g');self.assertEqual(len(p['variables']),8)
    def test_minimax_certifies_unavoidable_half_without_nutrition_relaxation(self):
        p,choices,foods=self.fixture(True);before=copy.deepcopy(p)
        async def fake(problem):return solve(problem)
        r,model,certificate=asyncio.run(minimax_candidate(p,choices,[self.plan(('shared',100),('a',100))],foods,fake,time.monotonic()+20))
        self.assertTrue(certificate['certified']);self.assertFalse(certificate['target_feasible'])
        self.assertGreaterEqual(certificate['threshold'],.5);self.assertLess(certificate['threshold'],.51)
        values_verified(model,r);self.assertEqual(p,before)
    def test_three_meal_alternatives_and_checked_report(self):
        r=day_tests.OrchestrationTests().run_chain(dict(k=3,pool_size=3,time_limit=120));self.assertEqual(len(r['plans']),3)
        self.assertEqual(r['pool']['overlap_target'],10)
        vectors=[amounts(p,load_foods()) for p in r['plans']]
        actual=max(overlap(a,b)*100 for i,a in enumerate(vectors) for b in vectors[:i])
        self.assertAlmostEqual(actual,r['pool']['overlap_achieved'],places=2)
        self.assertTrue(all(p['constraint_report']['all_respected'] for p in r['plans']))
    def test_three_week_alternatives_and_extension_checks_all_existing(self):
        async def fake(s,p):return solve(p)
        profile=week_tests.WeekOrchestrationTests().profile();request=dict(week_start='2026-10-05',k=3,pool_size=3,time_limit=120)
        with patch('plan_diet_day.solve_problem',side_effect=fake):
            result=asyncio.run(generate_week(None,profile,request,week_tests.make_config,load_foods()))
            more=asyncio.run(generate_week(None,profile,dict(request,_existing_plans=result['plans']),week_tests.make_config,load_foods()))
        self.assertEqual(len(result['plans']),3)
        self.assertTrue(all(p['constraint_report']['all_respected'] for p in result['plans']))
        for p in more['plans']:
            for prior in result['plans']:self.assertLessEqual(overlap(amounts(p,load_foods()),amounts(prior,load_foods())),.5+1e-6)
        if not more['plans']:self.assertEqual(more['status'],'no_more_alternatives')
    def test_feasible_reference_still_attempts_three_without_claiming_optimum(self):
        async def fake(session,p):
            result=solve(p)
            if result['mathematical_status']=='optimal':result['mathematical_status']='feasible'
            return result
        profile=week_tests.WeekOrchestrationTests().profile()
        with patch('plan_diet_day.solve_problem',side_effect=fake):
            result=asyncio.run(generate_week(None,profile,dict(week_start='2026-10-05',k=3,pool_size=3,time_limit=120),week_tests.make_config,load_foods()))
        self.assertEqual(len(result['plans']),3);self.assertEqual(result['status'],'partial')
        self.assertTrue(all(p['constraint_report']['all_respected'] for p in result['plans']))

    def test_no_timeout_claim_of_certified_infeasibility(self):
        p,choices,foods=self.fixture()
        async def fake(problem):return dict(mathematical_status='unknown')
        r,_,certificate=asyncio.run(minimax_candidate(p,choices,[self.plan(('a',100))],foods,fake,time.monotonic()+1))
        self.assertIsNone(r);self.assertFalse(certificate['certified'])

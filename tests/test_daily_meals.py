import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from daily_meals import defaults,validate,products
from plan_diet_day import formulate,load_foods,decode_result,optimize_day,NUTRIENTS
from test_recipe_solver import solve
from unittest.mock import patch


def preference_fixture():
 return dict(products=[dict(id='bar',name='Personal bar',serving_g=35,label_basis_g=100,kcal_per_serving=173,label_nutrients=dict(protein_g=26,fat_g=27,carbs_g=35)),dict(id='crackers',name='Personal crackers',serving_g=32,label_basis_g=32,kcal_per_serving=131,label_nutrients=dict(protein_g=3.5,fat_g=3.1,carbs_g=20))],preferences=dict(breakfast=dict(preferred_product_id='bar'),morning_snack=dict(preferred_product_id='crackers')))


class DailyMealsTests(unittest.TestCase):
 def setUp(self):
  self.config=json.loads((ROOT/'config/demo-diet-day.json').read_text());self.config.update(mode='free',daily_meals=defaults(True),food_preferences=preference_fixture());self.foods=load_foods()
 def run_plan(self):
  p,c,slots=formulate(self.config,self.foods)
  async def fake(session,problem):return solve(problem)
  with patch('plan_diet_day.solve_problem',side_effect=fake):r=asyncio.run(optimize_day(None,p))
  return decode_result(self.config,p,c,slots,self.foods,r),p,c
 def test_whole_day_totals_and_discrete_personal_products(self):
  r,_,_=self.run_plan();self.assertEqual(r['status'],'optimal');self.assertEqual(r['scope'],'full_day_planned_meals')
  selected={s['meal']:s for s in r['selections'] if s['meal'] not in ['lunch','dinner']}
  self.assertEqual(selected['breakfast']['food_id'],'personal:bar');self.assertEqual(selected['breakfast']['grams'],35)
  self.assertEqual(selected['morning_snack']['food_id'],'personal:crackers');self.assertEqual(selected['morning_snack']['grams'],32)
  self.assertAlmostEqual(r['nutrients_by_meal']['breakfast']['kcal'],173)
  self.assertAlmostEqual(r['nutrients_by_meal']['morning_snack']['kcal'],131)
  for n,total in r['nutrients'].items():self.assertAlmostEqual(sum(m[n] for m in r['nutrients_by_meal'].values()),total,delta=.003)
  self.assertEqual(r['preference_penalty'],0)
  report=r['constraint_report'];self.assertTrue(report['verified']);self.assertTrue(report['all_respected'])
  self.assertEqual(len(report['checks']),4)
  self.assertEqual(next(c for c in report['checks'] if c['nutrient']=='kcal')['min'],1400)
 def test_energy_uses_label_not_macro_reconstruction(self):
  p=products(preference_fixture())['bar'];self.assertAlmostEqual(float(p['kcal_100g'])*.35,173);self.assertAlmostEqual(float(p['protein_g_100g'])*.35,9.1)
 def test_optional_second_bar_is_not_available_without_permission(self):
  _,c,_=formulate(self.config,self.foods);bars=[x for x in c if x['food_id']=='personal:bar'];self.assertEqual([x['units'] for x in bars],[1])
  self.config['daily_meals']['allow_second_bar']=True
  _,c,_=formulate(self.config,self.foods);self.assertEqual([x['units'] for x in c if x['food_id']=='personal:bar'],[1,2])
 def test_hard_bounds_can_override_preference(self):
  # A <1 g breakfast fat bound rules out both packaged bar servings.
  self.config['meal_targets']={'breakfast':{'fat_g_100g':dict(min=0,max=1)}}
  r,_,_=self.run_plan();self.assertEqual(r['status'],'optimal')
  self.assertEqual(next(s for s in r['selections'] if s['meal']=='breakfast')['food_id'],'007510')
  self.assertGreaterEqual(r['preference_penalty'],1)
  local=next(c for c in r['constraint_report']['checks'] if c['meal']=='breakfast')
  self.assertTrue(local['respected']);self.assertLessEqual(local['actual'],1.000001)
  self.assertTrue(any('Colazione' in note for note in r['preference_changes']))
 def test_daily_targets_do_not_reuse_main_meal_targets(self):
  self.config['main_meals_targets']['kcal_100g']=dict(min=9000,target=9000,max=9000)
  r,_,_=self.run_plan();self.assertEqual(r['status'],'optimal');self.assertLess(r['nutrients']['kcal'],2401)
 def test_absent_personal_preferences_do_not_import_someone_elses_labels(self):
  self.config['food_preferences']={};_,choices,_=formulate(self.config,self.foods)
  self.assertFalse(any(c['food_id'].startswith('personal:') for c in choices))
 def test_unplanned_afternoon_is_explicit_and_adds_no_food(self):
  self.config['daily_meals']['afternoon_fruit']=False;r,_,_=self.run_plan()
  self.assertEqual(r['slots']['afternoon_snack'],'not_planned');self.assertFalse(any(s['meal']=='afternoon_snack' for s in r['selections']))
 def test_invalid_daily_settings_and_missing_label_fail(self):
  for key,value in [('banana_min_g',float('nan')),('banana_max_g',True),('allow_second_bar','yes'),('policy','strict_original')]:
   d=defaults();d[key]=value
   with self.assertRaises(ValueError):validate(d)
  self.config['food_preferences']['preferences']['breakfast']['preferred_product_id']='missing'
  with self.assertRaises(ValueError):formulate(self.config,self.foods)
 def test_daily_targets_remain_hard_when_impossible(self):
  self.config['daily_meals']['targets']['kcal_100g']=dict(min=9000,target=9000,max=9000)
  r,_,_=self.run_plan();self.assertEqual(r['status'],'infeasible');self.assertEqual(r['selections'],[])

if __name__=='__main__':unittest.main()

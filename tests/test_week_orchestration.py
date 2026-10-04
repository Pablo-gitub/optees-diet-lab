import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from week_orchestration import weekly_model,generate_week,week_keys,add_lock,generate_meal_alternatives
from plan_diet_day import load_foods,formulate
from test_recipe_solver import solve
from test_day_orchestration import OrchestrationTests
from daily_meals import defaults


def make_config(profile,day):
    c=copy.deepcopy(profile['config']);c['day_index']=day;return c

class WeekOrchestrationTests(unittest.TestCase):
    def profile(self):
        c=OrchestrationTests().config();c['portion_bounds_g'].update({i:[50,50] for i in ['000800','000100','000530']});c['portion_bounds_g']['166000']=[30,30];c['portion_bounds_g'].update({i:[40,40] for i in ['008540','008570']});c['portion_bounds_g'].update({i:[120,120] for i in ['110020','110400']})
        return dict(mode='free',config=c)
    def test_joint_week_model_frequencies_locked_quantities_and_verification(self):
        profile=self.profile();request=dict(week_start='2026-10-05',k=1,pool_size=1,max_protein_repetitions=3)
        async def fake(session,p):return solve(p)
        with patch('plan_diet_day.solve_problem',side_effect=fake):r=asyncio.run(generate_week(None,profile,request,make_config,load_foods()))
        self.assertTrue(r['plans']);p=r['plans'][0];self.assertEqual(len(p['days']),7);self.assertTrue(p['constraint_report']['all_respected'])
        self.assertTrue(all(count<=3 for count in p['constraint_report']['protein_frequencies'].values()))
        for day in p['days']:self.assertTrue(day['constraint_report']['verified'])
        model,blocks,choices,_=weekly_model(profile,request,make_config,load_foods())
        self.assertEqual(len(blocks),7);self.assertTrue(any(v['name'].startswith('frequency_') for v in model['variables']))
    def test_week_infeasible_frequency_is_not_relaxed(self):
        request=dict(week_start='2026-10-05',k=1,pool_size=1,max_protein_repetitions=1)
        async def fake(session,p):return solve(p)
        with patch('plan_diet_day.solve_problem',side_effect=fake):r=asyncio.run(generate_week(None,self.profile(),request,make_config,load_foods()))
        self.assertEqual(r['status'],'infeasible');self.assertFalse(r['plans'])
    def test_locks_are_fixed_even_when_not_multiple_of_five(self):
        profile=self.profile();foods=load_foods();request=dict(week_start='2026-10-05',locked=[dict(date='2026-10-05',slot='lunch',items=[dict(food=dict(source='CREA',id='000800'),grams=83)])])
        model,blocks,choices,_=weekly_model(profile,request,make_config,foods)
        locked=[c for c in choices if c.get('locked')];self.assertEqual(len(locked),1)
        self.assertEqual(model['variables'][locked[0]['y']]['lb'],0);self.assertEqual(model['variables'][locked[0]['y']]['ub'],1)
        for key,value in [('y',1),('q',83)]:
            index=locked[0][key]
            self.assertTrue(any(r['relation']=='=' and r['rhs']==value and r['coefficients'][index]==1 and sum(abs(c) for c in r['coefficients'])==1 for r in model['constraints']))
    def test_invalid_lock_or_unknown_nutrients_refused(self):
        profile=self.profile()
        with self.assertRaises(ValueError):weekly_model(profile,dict(week_start='2026-10-05',locked=[dict(date='2026-10-15',slot='lunch',items=[])]),make_config,load_foods())
        with self.assertRaises(ValueError):weekly_model(profile,dict(week_start='2026-10-05',max_protein_repetitions=True),make_config,load_foods())

class MealAlternativeTests(unittest.TestCase):
    def test_other_meals_fixed_and_constraints_verified(self):
        import sqlite3
        import diary_service as diary
        from day_orchestration import orchestrate_day
        profile=WeekOrchestrationTests().profile();profile.update(targets=profile['config']['main_meals_targets'],personal_diets=False)
        async def fake(session,p):return solve(p)
        with patch('multiobjective_day.solve_problem',side_effect=fake):original=asyncio.run(orchestrate_day(None,profile['config'],load_foods(),dict(k=1,pool_size=1)))['plans'][0]
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;diary.migrate(db)
        week=db.execute("INSERT INTO week_plan(user_id,week_start,mode,status,targets) VALUES(1,'2026-10-05','free','active',?)",(json.dumps(profile['targets']),)).lastrowid
        for slot in ('lunch','dinner'):
            items=[dict(food=dict(source='CREA',id=s['food_id']),grams=s['grams'],units=None) for s in original['selections'] if s['meal']==slot]
            db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status,day_index) VALUES(?,'2026-10-05',?,?,'best','chosen',7)",(week,slot,json.dumps(items)))
        run=generate_meal_alternatives(db,1,profile,dict(date='2026-10-05',slot='lunch'),make_config)
        with patch('multiobjective_day.solve_problem',side_effect=fake):result=asyncio.run(run(None))
        self.assertTrue(result['plans'])
        for p in result['plans']:
            self.assertTrue(p['constraint_report']['all_respected']);self.assertTrue(all(s['meal']=='lunch' for s in p['selections']))
            self.assertEqual(p['nutrients_by_meal']['dinner'],original['nutrients_by_meal']['dinner'])
            self.assertEqual(p['day_index'],7);self.assertEqual(p['diff']['reference_plan'],'current_meal')
        db.close()

class ReferenceCertificationTests(unittest.TestCase):
    def test_preference_fallback_is_feasible_not_nutrition_optimal(self):
        from plan_diet_day import optimize_day
        from test_multiobjective_day import MultiobjectiveTests
        problem,_,_=MultiobjectiveTests().fixture();problem['preference_coefficients']=[1,0,0,0]
        count=0
        async def fake(session,p):
            nonlocal count
            count+=1
            return solve(p) if count==1 else dict(mathematical_status='infeasible')
        with patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(optimize_day(None,problem))
        self.assertEqual(result['mathematical_status'],'feasible');self.assertEqual(result['validation']['status'],'verified')

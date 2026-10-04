import asyncio
import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch
import test_week_orchestration as week_tests
from daily_meals import defaults
from plan_diet_day import load_foods
from test_recipe_solver import solve
import joint_orchestration as joint
import workout_service as workouts


def fixture(start='2026-10-05'):
    config=week_tests.WeekOrchestrationTests().profile()['config']
    settings=defaults(False);settings.update(enabled=True,banana_min_g=100,banana_max_g=100)
    profile=dict(mode='free',targets_demo=True,personal_diets=False,targets=config['main_meals_targets'],daily_meals=settings,meal_targets={},excluded_crea_ids=[],config=config,_workout_settings=dict(level='beginner',equipment=['cyclette'],intensity_confirmed=True,variants={'stationary-bike':dict(variant='standard',executable=True)}))
    targets=copy.deepcopy(settings['targets']);targets['kcal_100g'].update(min=900,target=1400,max=2500);targets['carbs_available_g_100g']['target']=135
    training=copy.deepcopy(targets);training['kcal_100g']['target']=1500;training['carbs_available_g_100g']['target']=160
    request=dict(week_start=start,day_targets=dict(rest=targets,training=training),diet=dict(k=1,pool_size=1),workout=dict(days={d:40 for d in joint.dates(start)},allowed_protocols=['cardio_continuous'],sessions_min=2,sessions_max=2,strength_sessions_min=0,strength_sessions_max=0,cardio_minutes_min=40,weekly_minutes_max=60))
    def make_config(personal,index):return dict(copy.deepcopy(config),day_index=index,mode=personal['mode'],daily_meals=copy.deepcopy(personal['daily_meals']))
    return profile,request,make_config


class JointOrchestration(unittest.TestCase):
    def test_full_week_joint_verification_targets_and_energy_scope(self):
        profile,request,make_config=fixture()
        async def fake(session,p):return solve(p)
        with patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(joint.generate_week(None,profile,request,make_config,load_foods()))
        self.assertTrue(result['plans'],result)
        for plan in result['plans']:
            self.assertEqual(plan['status'],'feasible');self.assertTrue(plan['demo'])
            self.assertTrue(plan['constraint_report']['verified']);self.assertTrue(plan['constraint_report']['workout']['all_respected'])
            self.assertEqual(len(plan['days']),7);self.assertEqual(len(plan['workout_sessions']),2)
            for day in plan['days']:
                self.assertEqual(day['targets'],request['day_targets'][day['day_type']]);self.assertEqual(day['energy_scenarios']['status'],'unavailable')
                self.assertTrue(day['constraint_report']['all_respected'])
                self.assertTrue(all(s['grams']%5==0 for s in day['selections']))
            self.assertIn('training_fit',plan['objectives']);self.assertIn('training_minutes',plan['objectives'])
            self.assertIn('protocol:cardio_continuous',plan['arms'])
    def test_joint_pareto_includes_training_and_diff_tracks_moves(self):
        common=dict(nutrition_error=1,worst_error=.2,preference=1,variety=.5,training_minutes=60)
        a=dict(objectives=dict(common,training_fit=.2));b=dict(objectives=dict(common,training_fit=.5))
        self.assertEqual(joint.front([a,b]),[b])
        before=dict(workout_sessions=[dict(date='2026-10-05',session_id='bike'),dict(date='2026-10-06',session_id='row')])
        after=dict(workout_sessions=[dict(date='2026-10-07',session_id='bike'),dict(date='2026-10-06',session_id='core')])
        diff=joint.session_diff(before,after)
        self.assertEqual(diff['sessions_moved'],[dict(session_id='bike',from_date='2026-10-05',to_date='2026-10-07')])
        self.assertEqual(diff['sessions_added'],[dict(date='2026-10-06',session_id='core')]);self.assertEqual(diff['sessions_removed'],[dict(date='2026-10-06',session_id='row')])
    def test_configuration_and_complete_day_are_required(self):
        profile,request,_=fixture();original=copy.deepcopy(profile)
        joint.validate_request(profile,request);self.assertEqual(profile,original)
        for update in [dict(day_targets={}),dict(k=True),dict(energy_balance_target_kcal=True),dict(day_modes={'rest':'free','training':'training'})]:
            with self.assertRaises(ValueError):joint.validate_request(profile,dict(request,**update))
        profile['daily_meals']['enabled']=False
        with self.assertRaises(ValueError):joint.validate_request(profile,request)

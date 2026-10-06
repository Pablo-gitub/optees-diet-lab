import asyncio
import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch
import activity_service as activity
import workout_service as workouts
from joint_energy import day_scenarios
from test_recipe_solver import solve
from test_joint_orchestration import fixture


class ActivityTests(unittest.TestCase):
    def data(self):
        profile,request,_=fixture()
        profile['_filtered_weight_kg']=80
        profile['goals']=dict(activity=dict(gym='no',liked_activities=['walking_brisk']),training_priorities=dict(health=3))
        data=dict(request['workout'],week_start=request['week_start'],sessions_min=0,sessions_max=7,weekly_minutes_max=150,cardio_minutes_min=0)
        data['days']={d:30 for d in data['days']}
        return profile,data
    def test_net_met_and_personal_source_and_no_double_counting(self):
        row=next(a for a in activity.catalog()['activities'] if a['id']=='walking_brisk')
        estimate=activity.energy(row,30,80)
        self.assertAlmostEqual(estimate['energy_kcal']['central'],152)
        self.assertAlmostEqual(estimate['energy_kcal']['low'],106.4)
        self.assertTrue(estimate['net'])
        self.assertEqual(activity.energy(row,30,None)['status'],'unavailable')
        model=dict(activity='HKWorkoutActivityTypeWalking',status='provisional',observations=3,age_days=2,kcal_per_min_p20=3,kcal_per_min_p50=4,kcal_per_min_p80=5)
        self.assertEqual(activity.energy(row,30,None,dict(workout_energy_models=[model]))['source'],'apple_health_activity_quantiles')
        session=activity.snapshot(row,30,80)
        health=dict(non_workout_consumption_scenarios=dict(status='available',low_kcal=1700,central_kcal=1800,high_kcal=1900,source='apple_health_total_minus_observed_workouts'))
        result=day_scenarios(health,[dict(session_id=session['id'],session=session)])
        self.assertEqual(result['consumption_kcal']['central'],1952)
        self.assertTrue(result['double_counting_prevented'])
        session['additional_activity']=False
        self.assertEqual(day_scenarios(health,[dict(session_id=session['id'],session=session)])['status'],'unavailable')
    def test_activity_duration_is_integer_and_gym_no_has_only_activities(self):
        profile,data=self.data()
        async def fake(session,p):
            model=copy.deepcopy(p)
            if model['objective']['sense']=='max':model['objective']['coefficients']=[-c for c in model['objective']['coefficients']]
            return solve(model)
        with patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(workouts.generate_week(None,profile,data))
        self.assertTrue(result['plans'],result)
        for plan in result['plans']:
            self.assertTrue(plan['constraint_report']['all_respected'])
            self.assertEqual(plan['weekly_duration_seconds'],150*60)
            for item in plan['workout_sessions']:
                self.assertEqual(item['session']['kind'],'activity')
                self.assertEqual(item['minutes']%5,0)
                self.assertLessEqual(item['minutes'],30)
    def test_no_priorities_impose_no_activity_and_disliked_are_refused(self):
        profile,data=self.data();profile['goals']['training_priorities']={}
        self.assertEqual(activity.candidates(profile,data),[])
        async def fake(session,p):
            model=copy.deepcopy(p)
            if model['objective']['sense']=='max':model['objective']['coefficients']=[-c for c in model['objective']['coefficients']]
            return solve(model)
        with patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(workouts.generate_week(None,profile,data))
        self.assertEqual(result['plans'][0]['workout_sessions'],[])
        profile['goals']['activity']['disliked_activities']=['walking_brisk']
        with self.assertRaises(ValueError):activity.candidates(profile,dict(data,activities=['walking_brisk']))
    def test_confirm_is_owned_idempotent_csrf_and_skipping_enters_deviations(self):
        # Real HTTP/diary path on the test account's temporary database.
        from test_web import WebTests
        web=WebTests();web.setUpClass()
        try:
            client,headers=web.account('activityconfirmation')
            today=__import__('diary_service').local_today().isoformat()
            row=next(a for a in activity.catalog()['activities'] if a['id']=='walking_brisk');snapshot=activity.snapshot(row,30,80)
            with web.module.connect() as db:
                owner=db.execute("SELECT id FROM users WHERE username='activityconfirmation'").fetchone()['id']
                week=db.execute("INSERT INTO week_plan(user_id,week_start,mode,status,targets) VALUES(?,?,'free','active','{}')",(owner,today)).lastrowid
                identifier=db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,minutes,status,snapshot) VALUES(?,?,?,?, 'chosen',?)",(week,today,snapshot['id'],30,json.dumps(snapshot))).lastrowid
            data=dict(planned_session_id=identifier)
            self.assertEqual(client.post('/api/activities/confirm',json=data).status_code,403)
            stranger,h2=web.account('activitystranger')
            self.assertEqual(stranger.post('/api/activities/confirm',json=data,headers=h2).status_code,404)
            self.assertEqual(client.post('/api/activities/confirm',json=data,headers=headers).status_code,200)
            self.assertEqual(client.post('/api/activities/confirm',json=data,headers=headers).status_code,200)
            with web.module.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM workout_log WHERE user_id=?',(owner,)).fetchone()[0],1)
        finally:web.tearDownClass()

    def test_skipped_activity_enters_b13_as_energy_not_food(self):
        import meal_rebalance
        today=__import__('diary_service').local_today().isoformat()
        snap=dict(views=[dict(date=today,meals=[],workouts=[dict(kind='activity',status='skipped',planned_session_id=1,energy_estimate=dict(status='available',energy_kcal=dict(low=100,central=150,high=200),source='compendium_met_net'))])],previous_correction=0)
        values,excess,_,missing,_=meal_rebalance.deviations(dict(from_diary=True),snap)
        self.assertIsNone(missing);self.assertEqual(excess,dict(min=100,max=200))
        self.assertEqual(values[0]['kind'],'activity')
        self.assertNotIn('consumed_kcal',values[0])
        snap['views'][0]['workouts'][0]['status']='chosen'
        self.assertEqual(meal_rebalance.deviations(dict(from_diary=True),snap)[1],dict(min=0,max=0))

    def test_activities_are_in_joint_days_and_activity_energy_is_visible(self):
        import joint_orchestration as joint
        from plan_diet_day import load_foods
        profile,data=self.data();_,request,make_config=fixture();request['workout']=data
        async def fake(session,p):
            model=copy.deepcopy(p)
            if model['objective']['sense']=='max':model['objective']['coefficients']=[-c for c in model['objective']['coefficients']]
            return solve(model)
        with patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(joint.generate_week(None,profile,request,make_config,load_foods()))
        self.assertTrue(result['plans'],result)
        for plan in result['plans']:
            self.assertTrue(all(s['session']['kind']=='activity' for s in plan['workout_sessions']))
            self.assertTrue(any(d['workout_sessions'] for d in plan['days']))
            self.assertTrue(all(d['day_type']=='training' for d in plan['days'] if d['workout_sessions']))

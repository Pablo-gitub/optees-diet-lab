import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import time
from fastapi.testclient import TestClient
import activity_service
import activity_targets
from daily_meals import defaults

ROOT=Path(__file__).resolve().parents[1]

class ActivityTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();os.environ['DIET_WEB_DB']=str(Path(cls.temp.name)/'targets.sqlite')
        spec=importlib.util.spec_from_file_location('target_web',ROOT/'web/app.py');cls.app=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.app);del os.environ['DIET_WEB_DB']
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.app.attempts.clear();self.client=TestClient(self.app.app);name='target'+str(time.time_ns())
        self.client.post('/api/register',json=dict(username=name,password='test-password-123'))
        reply=self.client.post('/api/login',json=dict(username=name,password='test-password-123')).json();self.headers={'x-csrf-token':reply['csrf']}
        today=self.app.diary.local_today();self.today=today;self.start=(today-dt.timedelta(days=today.weekday())).isoformat()
        target=dict(kcal_100g=dict(min=1400,target=1800,max=3000),protein_g_100g=dict(min=45,target=120,max=200),fat_g_100g=dict(min=25,target=50,max=100),carbs_available_g_100g=dict(min=90,target=217.5,max=400))
        daily=defaults(False);daily.update(enabled=True,targets=target,targets_demo=False)
        response=self.client.put('/api/profile',json=dict(mode='free',daily_meals=daily,energy_balance_target_kcal=0),headers=self.headers);self.assertEqual(response.status_code,200,response.text)
        with self.app.connect() as db:
            self.user=db.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()[0]
            db.execute("INSERT INTO measurement(user_id,date,kind,value,unit,source) VALUES(?,?,'weight',80,'kg','manual')",(self.user,today.isoformat()))
            week=db.execute("INSERT INTO week_plan(user_id,week_start,mode,status,targets) VALUES(?,?,'free','active',?)",(self.user,self.start,json.dumps(target))).lastrowid
            row=next(a for a in activity_service.catalog()['activities'] if a['id']=='walking_brisk');session=activity_service.snapshot(row,30,80)
            self.session_id=db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,minutes,start_time,status,snapshot) VALUES(?,?,?,?,?,'chosen',?)",(week,today.isoformat(),session['id'],30,'18:00',json.dumps(session))).lastrowid
    def profile(self):return self.client.get('/api/profile').json()['profile']
    def proposal(self,**extra):
        result=self.client.post('/api/goals/day-targets/proposal',json=dict(week_start=self.start,**extra),headers=self.headers)
        self.assertEqual(result.status_code,200,result.text);return result.json()
    def decide(self,proposal,action='approve',**extra):
        return self.client.post(f"/api/goals/day-targets/proposal/{proposal['id']}/{action}",json=dict(state_token=proposal['state_token'],**extra),headers=self.headers)
    def test_proposal_formula_macros_limits_and_no_automatic_changes(self):
        before=self.profile();proposal=self.proposal()['proposal'];self.assertEqual(self.profile(),before)
        self.assertEqual(proposal['baseline']['source'],'current_target_minus_approved_balance_estimate')
        active=next(d for d in proposal['days'] if d['day_type']=='training')
        self.assertAlmostEqual(active['requested_kcal'],1906.4)
        self.assertEqual(active['proposed_kcal'],1890)
        self.assertEqual({d['targets']['protein_g_100g']['target'] for d in proposal['days']},{120})
        self.assertEqual(active['targets']['carbs_available_g_100g']['target'],240)
        for d in proposal['days']:
            self.assertLessEqual(abs(d['delta_kcal']),min(100,.05*d['before']['kcal_100g']['target']))
            for key,floor in activity_targets.calibration.FLOORS.items():self.assertGreaterEqual(d['targets'][key]['min'],floor)
        response=self.decide(proposal);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json(),dict(id=proposal['id'],status='approved',targets_changed=True,diary_changed=False))
        after=self.profile();self.assertEqual(after['day_type_targets']['training']['kcal_100g']['target'],1890)
        self.assertEqual(after['daily_meals'],before['daily_meals'])
        self.assertEqual(self.decide(proposal).status_code,409)
        self.assertEqual(self.proposal()['status'],'insufficient_data')
    def test_rejection_is_saved_and_does_not_modify_targets(self):
        before=self.profile();proposal=self.proposal()['proposal'];response=self.decide(proposal,'reject',reason='Preferisco i valori attuali')
        self.assertEqual(response.status_code,200);self.assertFalse(response.json()['targets_changed']);self.assertEqual(self.profile(),before)
        with self.app.connect() as db:
            row=db.execute('SELECT state,reason FROM activity_target_proposal WHERE id=?',(proposal['id'],)).fetchone()
            self.assertEqual(tuple(row),('rejected','Preferisco i valori attuali'))
    def test_stale_measurement_diary_and_selected_plan_are_conflicts(self):
        proposal=self.proposal()['proposal'];before=self.profile()
        with self.app.connect() as db:db.execute('UPDATE planned_session SET start_time=? WHERE id=?',('19:00',self.session_id))
        self.assertEqual(self.decide(proposal).status_code,409);self.assertEqual(self.profile(),before)
        new=self.proposal()['proposal']
        with self.app.connect() as db:db.execute("INSERT INTO measurement(user_id,date,kind,value,unit,source) VALUES(?,?,'weight',81,'kg','manual')",(self.user,self.today.isoformat()))
        self.assertEqual(self.decide(new,'reject').status_code,409)
    def test_missing_data_no_proposal_and_csrf_and_ownership(self):
        self.assertEqual(self.client.post('/api/goals/day-targets/proposal',json=dict(week_start=self.start)).status_code,403)
        self.assertEqual(TestClient(self.app.app).post('/api/goals/day-targets/proposal',json=dict(week_start=self.start)).status_code,401)
        with self.app.connect() as db:db.execute('DELETE FROM measurement WHERE user_id=?',(self.user,))
        result=self.proposal();self.assertEqual(result['status'],'insufficient_data');self.assertEqual(result['missing'],['weight'])
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM activity_target_proposal WHERE user_id=?',(self.user,)).fetchone()[0],0)
    def test_limits_extreme_budgets_and_protected_macro_infeasibility(self):
        profile=self.profile();measurements=[dict(kind='weight',unit='kg',value=80,source='manual',date=self.today.isoformat())]
        for balance in (-1000,1000):
            profile['energy_balance_target_kcal']=balance
            for base in (1000,6000):
                proposal=activity_targets.build(profile,measurements,None,self.start,[],base,self.today)
                self.assertEqual(proposal['status'],'available',proposal)
                self.assertTrue(all(1710<=d['proposed_kcal']<=1890 for d in proposal['days']))
        profile['daily_meals']['targets']['protein_g_100g']['target']=200
        profile['daily_meals']['targets']['fat_g_100g']['target']=100
        self.assertNotEqual(activity_targets.build(profile,measurements,None,self.start,[],1000,self.today)['status'],'available')
    def test_approve_transaction_rolls_back_on_storage_failure(self):
        proposal=self.proposal()['proposal'];before=self.profile()
        with self.app.connect() as db:db.execute("CREATE TRIGGER reject_target_update BEFORE UPDATE ON activity_target_proposal BEGIN SELECT RAISE(ABORT,'test storage failure'); END")
        try:
            with self.assertRaises(Exception):self.decide(proposal)
            self.assertEqual(self.profile(),before)
            with self.app.connect() as db:self.assertEqual(db.execute('SELECT state FROM activity_target_proposal WHERE id=?',(proposal['id'],)).fetchone()[0],'pending')
        finally:
            with self.app.connect() as db:db.execute('DROP TRIGGER reject_target_update')
    def test_without_health_workout_met_is_net_work_only(self):
        session=self.app.workouts.session_by_id({},'strength_dumbbells')
        estimate=activity_targets.session_energy(dict(session_id=session['id'],session=session),80)
        self.assertEqual(estimate['status'],'available');self.assertTrue(estimate['net'])
        self.assertEqual(estimate['source'],'compendium_workout_net_work_phase')
        self.assertLess(estimate['energy_kcal']['central'],(3.5-1)*80*session['duration_seconds']/3600)

    def test_health_central_base_and_personal_low_energy_are_used(self):
        from unittest.mock import patch
        report=dict(non_workout_consumption_scenarios=dict(status='available',source='apple_health_total_minus_observed_workouts',low_kcal=1900,central_kcal=2000,high_kcal=2100),workout_energy_models=[dict(activity='HKWorkoutActivityTypeWalking',status='provisional',observations=3,age_days=1,kcal_per_min_p20=3,kcal_per_min_p50=4,kcal_per_min_p80=5)])
        with patch.object(self.app,'load_health_report',return_value=report):proposal=self.proposal()['proposal']
        active=next(d for d in proposal['days'] if d['day_type']=='training')
        self.assertEqual(active['requested_kcal'],2090)
        self.assertEqual(active['net_activity_low_kcal'],90)
        self.assertEqual(active['session_energy'][0]['source'],'apple_health_activity_quantiles')
    def test_selected_plan_is_private_and_changing_it_invalidates_approval(self):
        row=next(a for a in activity_service.catalog()['activities'] if a['id']=='walking_brisk');session=activity_service.snapshot(row,30,80)
        payload=dict(kind='workout',week_start=self.start,plans=[dict(id=501,workout_sessions=[dict(date=self.today.isoformat(),session_id=session['id'],start_time='18:00',session=session)])])
        with self.app.connect() as db:identifier=db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,0,?,?)',(self.user,json.dumps(payload),'{}')).lastrowid
        proposal=self.proposal(plan_set_id=identifier,plan_id=501)['proposal']
        payload['plans'][0]['workout_sessions'][0]['session']=activity_service.snapshot(row,35,80)
        with self.app.connect() as db:db.execute('UPDATE plan_set SET payload=? WHERE id=?',(json.dumps(payload),identifier))
        self.assertEqual(self.decide(proposal).status_code,409)
        self.client.post('/api/register',json=dict(username='foreign'+str(time.time_ns()),password='test-password-123'))
        # A separate account cannot access either the selected plan or proposal.
        client=TestClient(self.app.app);name='stranger'+str(time.time_ns());client.post('/api/register',json=dict(username=name,password='test-password-123'));reply=client.post('/api/login',json=dict(username=name,password='test-password-123')).json();headers={'x-csrf-token':reply['csrf']}
        self.assertEqual(client.post('/api/goals/day-targets/proposal',json=dict(week_start=self.start,plan_set_id=identifier,plan_id=501),headers=headers).status_code,404)
        self.assertEqual(client.post(f"/api/goals/day-targets/proposal/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=headers).status_code,404)
    def test_balance_approval_can_be_followed_by_target_approval_but_recalibration_is_blocked(self):
        with self.app.connect() as db:db.execute("INSERT INTO goal_energy_proposal(user_id,created,state,decided,payload) VALUES(?,?,'approved',?,'{}')",(self.user,time.time(),time.time()))
        proposal=self.proposal()['proposal']
        self.assertEqual(self.decide(proposal).status_code,200)
        with self.app.connect() as db:self.assertTrue(activity_targets.calibration.cooldown(db,self.user))

    def test_joint_generation_consumes_approved_date_targets_and_manual_override(self):
        import asyncio
        import joint_orchestration as joint
        from unittest.mock import patch
        from plan_diet_day import load_foods
        proposal=self.proposal()['proposal'];self.assertEqual(self.decide(proposal).status_code,200)
        with self.app.connect() as db:
            owner=db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone();profile=self.app.owner_profile(owner)
            _,sessions,_=activity_targets.selection(db,self.user,dict(week_start=self.start))
        captured={}
        async def workout(*args):return dict(status='ok',warnings=[],plans=[dict(workout_sessions=sessions,weekly_duration_seconds=1800)])
        async def diet(session,original,request,callback,*args):
            for i,date in enumerate(joint.dates(self.start)):captured[date]=callback(original,i)
            return dict(status='infeasible',warnings=[],plans=[])
        data=dict(week_start=self.start,workout=dict(days={d:30 for d in joint.dates(self.start)},sessions_min=1,sessions_max=1,strength_sessions_min=0,strength_sessions_max=0,cardio_minutes_min=30))
        with patch.object(joint.workout_engine,'generate_week',side_effect=workout),patch.object(joint.diet_engine,'generate_week',side_effect=diet):
            asyncio.run(joint.generate_week(None,profile,data,self.app.make_config,load_foods()))
            self.assertEqual(captured[self.today.isoformat()]['daily_meals']['targets']['kcal_100g']['target'],1890)
            old=profile['daily_meals']['targets'];data['day_targets']=dict(rest=copy.deepcopy(old),training=copy.deepcopy(old))
            asyncio.run(joint.generate_week(None,profile,data,self.app.make_config,load_foods()))
            self.assertEqual(captured[self.today.isoformat()]['daily_meals']['targets']['kcal_100g']['target'],1800)

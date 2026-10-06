import datetime as dt
import json
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_diary_service as diary_tests
from test_joint_orchestration import fixture
from test_recipe_solver import solve


class JointAPI(diary_tests.DiaryTests):
    def setUp(self):
        super().setUp();personal,self.data,self.make_config=fixture(self.date)
        self.profile['daily_meals']=personal['daily_meals']
        self.assertEqual(self.client.put('/api/profile',json=self.profile,headers=self.headers).status_code,200)
        self.assertEqual(self.client.patch('/api/workouts/config',json=personal['_workout_settings'],headers=self.headers).status_code,200)
    def generate(self,client,timeout=30):
        response=client.post('/api/plans/joint-week',json=self.data,headers=self.headers);self.assertEqual(response.status_code,202,response.text)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            job=client.get('/api/jobs/'+response.json()['job_id']).json()
            if job['state'] in ('done','failed'):break
            time.sleep(.03)
        self.assertEqual(job['state'],'done',job)
        result=client.get('/api/plan-sets/'+str(job['result']['plan_set_id'])).json();self.assertTrue(result['plans'],result)
        return result
    def test_generate_apply_context_targets_and_stale_diary_rejection(self):
        async def fake(session,p):return solve(p)
        with TestClient(self.app.app) as client,patch.object(self.app,'make_config',side_effect=self.make_config),patch('plan_diet_day.solve_problem',side_effect=fake):
            client.cookies.update(self.client.cookies);result=self.generate(client);plan=result['plans'][0]
            applied=client.post('/api/plan-sets/'+result['run_id']+'/apply',json=dict(plan_id=plan['id'],scope='week'),headers=self.headers)
            self.assertEqual(applied.status_code,200,applied.text)
            with self.app.connect() as db:
                context=json.loads(db.execute("SELECT day_context FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(self.user,self.date)).fetchone()['day_context'])
            for day in plan['days']:
                self.assertEqual(context[day['date']]['progress_forecast']['scope'],'full_day_planned_meals')
                self.assertEqual(context[day['date']]['progress_forecast']['planned_kcal'],day['nutrients']['kcal'])
                view=client.get('/api/day',params=dict(date=day['date'])).json()
                self.assertEqual(view['targets']['kcal'],self.data['day_targets'][day['day_type']]['kcal_100g'])
                self.assertEqual(view['day_type'],day['day_type']);self.assertIsNone(view['totals']['eaten'])
            week=client.get('/api/week',params=dict(start=self.date)).json()
            self.assertEqual(week['workouts']['planned'],2)
            self.assertEqual(week['budget']['kcal_target'],sum(d['targets']['kcal_100g']['target'] for d in plan['days']))
            # Applying a candidate after a new actual record must not overwrite it.
            again=self.generate(client)
            client.post('/api/diary/confirm',json=dict(date=self.date,slot='lunch'),headers=self.headers)
            stale=client.post('/api/plan-sets/'+again['run_id']+'/apply',json=dict(plan_id=again['plans'][0]['id'],scope='week'),headers=self.headers)
            self.assertEqual(stale.status_code,409,stale.text);self.assertEqual(stale.json()['code'],'planning_state_changed')
            self.assertEqual(client.get('/api/day',params=dict(date=self.date)).json()['meals'][2]['state'],'as_planned')
    def test_multiple_recorded_workouts_are_locked_with_exact_time(self):
        self.client.patch('/api/workouts/config',json=dict(equipment=['cyclette','vogatore_acqua']),headers=self.headers)
        self.data['workout']['days'][self.date]=60
        for identifier in ('continuous_stationary-bike','continuous_rowing-machine'):
            response=self.client.post('/api/workouts/start',json=dict(session_id=identifier,date=self.date),headers=self.headers);self.assertEqual(response.status_code,200,response.text)
        async def fake(session,p):return solve(p)
        with TestClient(self.app.app) as client,patch.object(self.app,'make_config',side_effect=self.make_config),patch('plan_diet_day.solve_problem',side_effect=fake):
            client.cookies.update(self.client.cookies);result=self.generate(client)
            for p in result['plans']:
                self.assertEqual(len(p['workout_sessions']),2);self.assertTrue(all(s['date']==self.date and s['locked'] for s in p['workout_sessions']))
                self.assertEqual(p['training_metrics']['duration_seconds'],3420)
            response=client.post('/api/plan-sets/'+result['run_id']+'/apply',json=dict(plan_id=result['plans'][0]['id'],scope='week'),headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            view=client.get('/api/day',params=dict(date=self.date)).json();self.assertEqual(len(view['workouts']),2)
            self.assertTrue(all(w['planned_session_id'] is None for w in view['workouts']))
    def test_preferred_recipe_snapshots_survive_joint_week_apply(self):
        for recipe in ('foodose:R048','foodose:R054'):
            response=self.client.put('/api/recipes/'+recipe+'/preferred',json={'preferred':True},headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
        from scipy.optimize import milp as scipy_milp
        def bounded(*args,**kwargs):return scipy_milp(*args,**dict(kwargs,options={'time_limit':8,'mip_rel_gap':.001}))
        base_config=self.make_config
        def config(personal,index):
            value=base_config(personal,index)
            # Require real recipe portions in this fixture: an application test
            # must not pass merely because the soft favorites were unselected.
            offset=(index-self.data.get('day_index',dt.date.fromisoformat(self.date).weekday()))%14
            if offset in (0,1):value['_locked_recipe_by_slot']={'lunch':dict(id=('foodose:R048','foodose:R054')[offset],portions=1)}
            return value
        async def fake(session,p):
            with patch('test_recipe_solver.milp',side_effect=bounded):return solve(p)

        with TestClient(self.app.app) as client,patch.object(self.app,'make_config',side_effect=config),patch('plan_diet_day.solve_problem',side_effect=fake):
            client.cookies.update(self.client.cookies);result=self.generate(client,timeout=120);plan=result['plans'][0]
            selected=[(d,s) for d in plan['days'] for s in d['selections'] if s.get('source')=='recipe']
            self.assertEqual({s['recipe_id'] for _,s in selected},{'foodose:R048','foodose:R054'})
            for day,selection in selected:self.assertIn(selection['reference_id'],day['_recipe_snapshots'])
            applied=client.post('/api/plan-sets/'+result['run_id']+'/apply',json=dict(plan_id=plan['id'],scope='week'),headers=self.headers)
            self.assertEqual(applied.status_code,200,applied.text)
            with self.app.connect() as db:
                self.assertGreater(db.execute('SELECT count(*) FROM bandit_exposure WHERE user_id=? AND plan_id=?',(self.user,plan['id'])).fetchone()[0],0)
                stored={r['id'] for r in db.execute('SELECT id FROM planned_food_snapshot WHERE user_id=? AND source=?',(self.user,'recipe'))}
            for day,selection in selected:
                self.assertIn(selection['reference_id'],stored)
                view=client.get('/api/day',params={'date':day['date']})
                self.assertEqual(view.status_code,200,view.text)
                items=[i for m in view.json()['meals'] if m['planned'] for i in m['planned']['items']]
                self.assertTrue(any(i['food']['id']==selection['reference_id'] for i in items))

    def test_csrf_invalid_request_and_owner_scope(self):
        self.assertEqual(self.client.post('/api/plans/joint-week',json=self.data).status_code,403)
        self.assertEqual(self.client.post('/api/plans/joint-week',json=dict(self.data,day_targets={}),headers=self.headers).status_code,400)


for name in tuple(vars(diary_tests.DiaryTests)):
    if name.startswith('test_'):setattr(JointAPI,name,None)

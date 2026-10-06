import asyncio
import copy
import datetime as dt
import json
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_diary_service as diary_tests
from test_recipe_solver import solve


class WorkoutAPI(diary_tests.DiaryTests):
    def setUp(self):
        super().setUp()
        settings=dict(level='beginner',equipment=['cyclette','vogatore_acqua','tapis_roulant_inclinabile','ellittica'],intensity_confirmed=True)
        response=self.client.patch('/api/workouts/config',json=settings,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
    def seed(self,session_id='hypertrophy_basic',offset=0):
        session=self.app.workouts.session_by_id({},session_id)
        date=(dt.date.fromisoformat(self.date)+dt.timedelta(days=offset)).isoformat()
        with self.app.connect() as db:
            week=db.execute('SELECT week_plan_id FROM planned_meal WHERE id=?',(self.meal,)).fetchone()[0]
            return db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,minutes,status,snapshot) VALUES(?,?,?,?,'chosen',?)",(week,date,session_id,session['duration_minutes_assumed'],json.dumps(session))).lastrowid

    def begin(self,identifier):
        return self.client.post('/api/workouts/start',json=dict(planned_session_id=identifier,session_id='hypertrophy_basic',date=self.date),headers=self.headers)

    def test_start_sets_finish_are_owned_separate_idempotent_and_snapshotted(self):
        identifier=self.seed();before=self.client.get('/api/day',params=dict(date=self.date)).json()
        self.assertEqual(before['workout']['status'],'chosen');self.assertIsNone(before['totals']['eaten'])
        response=self.begin(identifier);self.assertEqual(response.status_code,200,response.text)
        log=response.json()['workout_log_id'];self.assertEqual(response.json()['workout']['status'],'in_progress')
        self.assertEqual(self.begin(identifier).json()['workout_log_id'],log)
        path=f'/api/workouts/{log}/sets'
        self.assertEqual(self.client.post(path,json=dict(exercise_id='bodyweight-squat',set_no=1,reps=10,rir=2),headers=self.headers).status_code,200)
        self.client.post(path,json=dict(exercise_id='bodyweight-squat',set_no=1,reps=12,kg=0),headers=self.headers)
        detail=self.client.get(f'/api/workouts/logs/{log}').json();self.assertEqual(len(detail['sets']),1);self.assertEqual(detail['sets'][0]['reps'],12)
        self.assertEqual(detail['sets'][0]['kg'],0);self.assertIsNone(detail['sets'][0]['rir'])
        finish=self.client.post(f'/api/workouts/{log}/finish',json=dict(rpe=7,notes='Prova sintetica'),headers=self.headers)
        self.assertEqual(finish.json()['workout']['status'],'done')
        detail=self.client.get(f'/api/workouts/logs/{log}').json();self.assertIsNotNone(dt.datetime.fromisoformat(detail['started']).utcoffset());self.assertIsNotNone(detail['ended'])
        self.assertEqual(self.client.post(f'/api/workouts/{log}/finish',json={},headers=self.headers).status_code,200)
        self.assertEqual(self.client.post(path,json=dict(exercise_id='bodyweight-squat',set_no=2,reps=10),headers=self.headers).status_code,409)
        self.assertEqual(self.begin(identifier).status_code,409)
        self.assertEqual(self.client.get('/api/week',params=dict(start=self.date)).json()['workouts'],dict(planned=1,done=1))
        after=self.client.get('/api/day',params=dict(date=self.date)).json();self.assertEqual(before['meals'],after['meals']);self.assertIsNone(after['totals']['eaten'])
        with self.app.connect() as db:db.execute('UPDATE planned_session SET snapshot=? WHERE id=?',(json.dumps(dict(name='changed')),identifier))
        self.assertEqual(self.client.get(f'/api/workouts/logs/{log}').json()['session']['name'],detail['session']['name'])
        name='foreign'+str(time.time_ns())
        self.assertEqual(self.client.post('/api/register',json=dict(username=name,password='test-password-123')).status_code,200)
        self.assertEqual(self.client.post('/api/login',json=dict(username=name,password='test-password-123')).status_code,200)
        csrf=self.client.get('/api/profile').json()['csrf'];headers={'X-CSRF-Token':csrf}
        self.assertEqual(self.client.get(f'/api/workouts/logs/{log}').status_code,404)
        self.assertEqual(self.client.post('/api/workouts/skip',json=dict(planned_session_id=identifier),headers=headers).status_code,404)
        self.assertEqual(self.client.get('/api/workouts/logs',params=dict(start=self.date,end=self.date)).json(),[])

    def test_double_planned_sessions_apply_and_keep_separate_logs(self):
        self.seed()
        snapshot=self.app.workouts.session_by_id({},'hypertrophy_basic')
        plan=dict(workout_sessions=[dict(date=self.date,session_id=snapshot['id'],start_time=t,session=copy.deepcopy(snapshot)) for t in ('08:00','14:00')])
        with self.app.connect() as db:
            owner=db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone();profile=self.app.owner_profile(owner)
            response=self.app.workouts.apply_week(db,self.user,profile,dict(week_start=self.date,run_id=1,kind='workout'),plan,dict(plan_id=1,scope='week'))
        self.assertEqual(len(response['applied_slots']),2)
        identifiers=[s['planned_session_id'] for s in response['applied_slots']]
        first=self.begin(identifiers[0]).json()['workout_log_id']
        second=self.begin(identifiers[1]).json()['workout_log_id']
        self.assertNotEqual(first,second)
        self.client.post(f'/api/workouts/{first}/finish',json={},headers=self.headers)
        view=self.client.get('/api/day',params=dict(date=self.date)).json()
        self.assertEqual(len(view['workouts']),2)
        self.assertEqual({w['status'] for w in view['workouts']},{'done','in_progress'})

    def test_per_set_rpe_is_saved_and_translated_to_bounded_rir(self):
        identifier=self.seed();log=self.begin(identifier).json()['workout_log_id']
        path=f'/api/workouts/{log}/sets'
        data=dict(exercise_id='bodyweight-squat',set_no=1,reps=10,kg=10,rpe=6)
        self.assertEqual(self.client.post(path,json=data,headers=self.headers).status_code,200)
        detail=self.client.get(f'/api/workouts/logs/{log}').json()
        self.assertEqual(detail['sets'][0]['rpe'],6)
        self.assertEqual(detail['sets'][0]['rir'],4)
        self.assertEqual(self.client.post(path,json=dict(data,rpe=11),headers=self.headers).status_code,400)

    def test_missing_values_validation_csrf_skip_and_standalone(self):
        identifier=self.seed()
        self.assertEqual(self.client.post('/api/workouts/start',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/workouts/skip',json=dict(planned_session_id=identifier),headers=self.headers).json()['workout']['status'],'skipped')
        self.assertEqual(self.begin(identifier).status_code,409)
        response=self.client.post('/api/workouts/start',json=dict(session_id='isometric_core',date=self.date),headers=self.headers)
        log=response.json()['workout_log_id']
        path=f'/api/workouts/{log}/sets'
        for data in [dict(exercise_id='push-up',set_no=1,reps=5),dict(exercise_id='plank',set_no=True,reps=5),dict(exercise_id='plank',set_no=1),dict(exercise_id='plank',set_no=1,seconds=20,kg=-1)]:
            self.assertEqual(self.client.post(path,json=data,headers=self.headers).status_code,400)
        self.assertEqual(self.client.post(path,json=dict(exercise_id='plank',set_no=1,seconds=20),headers=self.headers).status_code,200)
        detail=self.client.get(f'/api/workouts/logs/{log}').json();self.assertIsNone(detail['sets'][0]['kg']);self.assertIsNone(detail['sets'][0]['reps'])
        self.assertEqual(self.client.post(f'/api/workouts/{log}/finish',json=dict(rpe=11),headers=self.headers).status_code,400)

    def test_multiple_sessions_snapshot_explanation_and_rounded_minutes(self):
        identifier=self.seed('continuous_stationary-bike')
        response=self.client.post('/api/workouts/start',json=dict(session_id='isometric_core',date=self.date),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        log=response.json()['workout_log_id']
        before=self.client.get('/api/day',params=dict(date=self.date)).json()
        self.assertEqual(len(before['workouts']),2)
        self.assertTrue(any(w['planned_session_id']==identifier for w in before['workouts']))
        self.assertTrue(any(w['workout_log_id']==log for w in before['workouts']))
        for w in before['workouts']:
            self.assertIsInstance(w['minutes'],int)
            self.assertEqual(w['minutes'],int(w['duration_seconds']/60+.5))
        snapshot=next(w for w in before['workouts'] if w['workout_log_id']==log)['configuration_at_start']
        self.assertEqual(snapshot['source'],'workout_log_snapshot')
        self.client.patch('/api/workouts/config',json=dict(level='advanced'),headers=self.headers)
        detail=self.client.get(f'/api/workouts/logs/{log}').json()
        self.assertEqual(detail['configuration_at_start'],snapshot)
        self.assertTrue(snapshot['pending_configuration'])
        self.assertEqual(self.client.get('/api/week',params=dict(start=self.date)).json()['workouts'],dict(planned=1,done=0))

    def request(self):
        dates=[(dt.date.fromisoformat(self.date)+dt.timedelta(days=i-6)).isoformat() for i in range(7)]
        return dict(week_start=dates[0],days={d:40 for d in dates},excluded_days=[dates[1]],sessions_min=2,sessions_max=2,strength_sessions_min=0,strength_sessions_max=0,cardio_minutes_min=40,weekly_minutes_max=80,start_times={dates[0]:'18:30'})

    def test_week_job_generation_application_and_locked_session(self):
        async def fake(session,problem):return solve(problem)
        data=self.request()
        with TestClient(self.app.app) as client,patch('plan_diet_day.solve_problem',side_effect=fake):
            client.cookies.update(self.client.cookies)
            r=client.post('/api/workouts/week',json=data,headers=self.headers);self.assertEqual(r.status_code,202,r.text)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                job=client.get('/api/jobs/'+r.json()['job_id']).json()
                if job['state'] in ('done','failed'):break
                time.sleep(.03)
            self.assertEqual(job['state'],'done',job)
            result=client.get('/api/plan-sets/'+str(job['result']['plan_set_id'])).json();self.assertTrue(result['plans'])
            for plan in result['plans']:
                self.assertTrue(plan['constraint_report']['all_respected']);self.assertEqual(len(plan['workout_sessions']),2)
                self.assertFalse(any(s['date'] in data['excluded_days'] for s in plan['workout_sessions']))
                self.assertTrue(all(s['minutes']<=data['days'][s['date']] for s in plan['workout_sessions']))
            before=client.get('/api/day',params=dict(date=data['week_start'])).json()['meals']
            reply=client.post('/api/plan-sets/'+result['run_id']+'/apply',json=dict(plan_id=result['plans'][0]['id'],scope='week'),headers=self.headers)
            self.assertEqual(reply.status_code,200,reply.text)
            self.assertEqual(reply.json()['meals'],before)
            self.assertEqual(client.get('/api/week',params=dict(start=data['week_start'])).json()['workouts'],dict(planned=2,done=0))
            date=result['plans'][0]['workout_sessions'][0]['date'];p=client.get('/api/day',params=dict(date=date)).json()['workout']
            self.assertEqual(client.post('/api/workouts/start',json=dict(planned_session_id=p['planned_session_id'],session_id=p['session_id'],date=date),headers=self.headers).status_code,200)
            reply=client.post('/api/plan-sets/'+result['run_id']+'/apply',json=dict(plan_id=result['plans'][0]['id'],scope='week'),headers=self.headers)
            self.assertTrue(any(s['date']==date for s in reply.json()['skipped_slots']))
            self.assertEqual(client.get('/api/day',params=dict(date=date)).json()['workout']['planned_session_id'],p['planned_session_id'])

    def test_catalog_is_demo_and_week_input_errors_and_infeasibility(self):
        c=self.client.get('/api/workouts/catalog').json();self.assertEqual(len(c['templates']),13)
        for session in c['templates']:
            self.assertTrue(session['demo']);self.assertTrue(session['pending_configuration'])
            self.assertTrue(all(e['load_kg'] is None for e in session['exercises']))
        data=self.request()
        for patch_ in [dict(days={}),dict(excluded_days=['1999-01-01']),dict(start_times={self.date:'99:99'}),dict(sessions_min=True),dict(goal='invented'),dict(allowed_protocols=[{}])]:
            self.assertEqual(self.client.post('/api/workouts/week',json=dict(data,**patch_),headers=self.headers).status_code,400)
        data['days']={d:1 for d in data['days']}
        result=asyncio.run(self.app.workouts.generate_week(None,self.profile,data));self.assertEqual(result['status'],'infeasible');self.assertFalse(result['plans'])


for name in tuple(vars(diary_tests.DiaryTests)):
    if name.startswith('test_'):setattr(WorkoutAPI,name,None)

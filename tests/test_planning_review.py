"""Review boundaries, retry receipts and non-mutating generation parameters."""
import json
import copy
import time
from fastapi.testclient import TestClient
from unittest.mock import patch
import test_diary_service as base
import planning_review


class PlanningReviewTests(base.DiaryTests):
    def candidate(self,**changes):
        days=[dict(date=(self.app.diary.dt.date.fromisoformat(self.date)+self.app.diary.dt.timedelta(days=i)).isoformat(),day_index=i,mode='free',selections=[dict(meal=m,food_id='000800',source='CREA',food='Pasta',grams=100) for m in ('lunch','dinner')]) for i in range(7)]
        plan=dict(id=10,role='best',days=days)
        payload=dict(run_id='1',mode='free',week_start=self.date,plans=[plan],**changes)
        with self.app.connect() as db:
            set_id=db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,0,?,?)',(self.user,json.dumps(payload),'{}')).lastrowid
            payload['run_id']=str(set_id)
            db.execute('UPDATE plan_set SET payload=? WHERE id=?',(json.dumps(payload),set_id))
        return set_id,payload
    def review(self,identifier,**data):
        return self.client.post(f'/api/plan-sets/{identifier}/review',json={**dict(plan_id=10,scope='week'),**data},headers=self.headers)
    def apply(self,identifier,token,**data):
        return self.client.post(f'/api/plan-sets/{identifier}/apply',json={**dict(plan_id=10,scope='week',review_token=token),**data},headers=self.headers)
    def test_review_is_read_only_and_apply_preserves_consumed_and_locked(self):
        self.post('/api/diary/confirm')
        with self.app.connect() as db:
            week=db.execute('SELECT week_plan_id FROM planned_meal WHERE id=?',(self.meal,)).fetchone()[0]
            db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status,locked) VALUES(?,?,'dinner',?,'best','chosen',1)",(week,self.date,json.dumps(self.items)))
        identifier,_=self.candidate();before=self.client.get('/api/day',params={'date':self.date}).json()
        response=self.review(identifier);self.assertEqual(response.status_code,200,response.text)
        review=response.json();self.assertEqual(len(review['protected_meals']),2);self.assertEqual(len(review['meals']),12)
        self.assertEqual(self.client.get('/api/day',params={'date':self.date}).json(),before)
        original=self.client.get('/api/profile').json()['profile']
        applied=self.apply(identifier,review['review_token']);self.assertEqual(applied.status_code,200,applied.text)
        self.assertEqual(applied.json()['meals'][2]['eaten']['items'][0]['grams'],80)
        self.assertEqual(self.client.get('/api/profile').json()['profile'],original)
        self.assertEqual(self.apply(identifier,review['review_token']).json(),applied.json())
        self.assertIn(10,self.client.get(f'/api/plan-sets/{identifier}').json()['applied_plan_ids'])
        self.assertEqual(self.apply(identifier,review['review_token'],scope='day',date=self.date).status_code,409)
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM plan_application WHERE user_id=?',(self.user,)).fetchone()[0],1)
        self.assertEqual(self.apply(identifier,review['review_token'],plan_id=999).status_code,404)
    def test_change_between_review_and_application_rejected_without_partial_write(self):
        identifier,_=self.candidate();token=self.review(identifier).json()['review_token']
        self.post('/api/diary/confirm')
        response=self.apply(identifier,token);self.assertEqual(response.status_code,409,response.text)
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM planned_meal WHERE week_plan_id=(SELECT week_plan_id FROM planned_meal WHERE id=?)',(self.meal,)).fetchone()[0],1)
    def test_generation_snapshot_rejects_obsolete_candidate(self):
        with self.app.connect() as db:state=planning_review.state(db,self.user,self.date)
        identifier,_=self.candidate(review_state=state)
        self.post('/api/diary/skip')
        self.assertEqual(self.review(identifier).status_code,409)
        self.assertEqual(self.client.post(f'/api/plan-sets/{identifier}/apply',json={'plan_id':10,'scope':'week'},headers=self.headers).status_code,409)
    def test_apply_rolls_back_every_day_on_invalid_late_food(self):
        identifier,payload=self.candidate()
        payload['plans'][0]['days'][-1]['selections'][0]['food_id']='missing-food'
        with self.app.connect() as db:db.execute('UPDATE plan_set SET payload=? WHERE id=?',(json.dumps(payload),identifier))
        token=self.review(identifier).json()['review_token']
        self.assertEqual(self.apply(identifier,token).status_code,400)
        with self.app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM planned_meal m JOIN week_plan w ON w.id=m.week_plan_id WHERE w.user_id=?',(self.user,)).fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM plan_application WHERE user_id=?',(self.user,)).fetchone()[0],0)
    def test_owner_csrf_and_calendar_match_applied_quantities(self):
        identifier,_=self.candidate()
        self.assertEqual(self.client.post(f'/api/plan-sets/{identifier}/review',json={'plan_id':10,'scope':'week'}).status_code,403)
        self.assertEqual(self.review(identifier+9999).status_code,404)
        token=self.review(identifier).json()['review_token'];self.assertEqual(self.apply(identifier,token).status_code,200)
        week=self.client.get('/api/week',params={'start':self.date}).json()
        self.assertEqual(len(week['calendar']),7);self.assertEqual(week['plan_set_run_id'],identifier)
        self.assertEqual(week['calendar'][0]['meals'][2]['foods'],['Pasta di semola'])
        shopping=self.client.get('/api/week/'+self.date+'/shopping-list').json();self.assertEqual(shopping['included_meals'],14)
        recent=self.client.get('/api/planning/recent').json();self.assertTrue(any(x['id']==identifier for x in recent['sets']))
    def test_partial_application_preserves_existing_target_snapshot(self):
        self.post('/api/diary/confirm')
        with self.app.connect() as db:
            db.execute('UPDATE week_plan SET day_context=? WHERE user_id=?',(json.dumps({self.date:dict(targets=self.profile['targets'],mode='free',scope='main_meals',progress_forecast=dict(valid=True,planned_kcal=1135),meal_timing=dict(status='available'))}),self.user))
        identifier,payload=self.candidate()
        targets=copy.deepcopy(self.profile['targets']);targets['kcal_100g']['target']=1900
        plan=payload['plans'][0];plan['targets_by_date']={}
        for day in plan['days']:day.update(targets=targets,scope='full_day_planned_meals')
        with self.app.connect() as db:db.execute('UPDATE plan_set SET payload=? WHERE id=?',(json.dumps(payload),identifier))
        token=self.review(identifier).json()['review_token'];result=self.apply(identifier,token)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['targets']['kcal']['target'],self.profile['targets']['kcal_100g']['target'])
        with self.app.connect() as db:
            context=json.loads(db.execute('SELECT day_context FROM week_plan WHERE user_id=?',(self.user,)).fetchone()[0])[self.date]
        self.assertFalse(context['progress_forecast']['valid']);self.assertEqual(context['meal_timing']['status'],'unavailable')
        next_date=plan['days'][1]['date']
        self.assertEqual(self.client.get('/api/day',params={'date':next_date}).json()['targets']['kcal']['target'],1900)

    def test_workout_generation_passes_started_sessions_as_solver_locks(self):
        started=self.client.post('/api/workouts/start',json={'session_id':'isometric_core','date':self.date},headers=self.headers)
        self.assertEqual(started.status_code,200,started.text)
        dates=[(self.app.diary.dt.date.fromisoformat(self.date)+self.app.diary.dt.timedelta(days=i)).isoformat() for i in range(7)]
        observed=[]
        async def generate(session,profile,data,locked_by_date=None):
            observed.append(locked_by_date)
            return dict(kind='workout',mode='free',week_start=self.date,plans=[],warnings=[])
        with TestClient(self.app.app) as client,patch.object(self.app.workouts,'generate_week',side_effect=generate):
            client.cookies.update(self.client.cookies)
            response=client.post('/api/workouts/week',json={'week_start':self.date,'days':{d:40 for d in dates}},headers=self.headers)
            self.assertEqual(response.status_code,202,response.text)
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                job=client.get('/api/jobs/'+response.json()['job_id']).json()
                if job['state'] in ('done','failed'):break
                time.sleep(.03)
            self.assertEqual(job['state'],'done',job)
        self.assertIn(self.date,observed[0]);self.assertTrue(observed[0][self.date][0]['locked_observation'])

    def test_other_account_cannot_review_apply_or_resume_owner_draft(self):
        identifier,_=self.candidate()
        other=TestClient(self.app.app);name='planning_other'+str(id(self))
        other.post('/api/register',json={'username':name,'password':'test-password-123'})
        other.post('/api/login',json={'username':name,'password':'test-password-123'})
        headers={'X-CSRF-Token':other.get('/api/profile').json()['csrf']}
        for endpoint in ('review','apply'):
            self.assertEqual(other.post(f'/api/plan-sets/{identifier}/{endpoint}',json={'plan_id':10,'scope':'week'},headers=headers).status_code,404)
        self.assertEqual(other.get('/api/planning/recent').json()['sets'],[])

    def test_joint_draft_targets_and_balance_do_not_change_profile_even_on_failure(self):
        from daily_meals import defaults
        with self.app.connect() as db:
            profile=dict(self.profile,daily_meals=dict(defaults(False),enabled=True))
            db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(profile),self.user))
        before=self.client.get('/api/profile').json()['profile']
        targets=copy.deepcopy(profile['daily_meals']['targets']);targets['kcal_100g']['target']=1900
        dates=[(self.app.diary.dt.date.fromisoformat(self.date)+self.app.diary.dt.timedelta(days=i)).isoformat() for i in range(7)]
        request=dict(week_start=self.date,day_targets={'rest':targets,'training':targets},energy_balance_target_kcal=-250,workout=dict(days={d:40 for d in dates},demo=True))
        observed=[]
        async def failed(job,user,personal,data,kind,review_state=None):
            observed.append((personal,data,kind))
            with self.app.connect() as db:db.execute("UPDATE job SET state='failed',error=? WHERE id=?",(json.dumps({'detail':'Synthetic solver failure'}),job))
        with patch.object(self.app,'planning_job',side_effect=failed):result=self.client.post('/api/plans/joint-week',json=request,headers=self.headers)
        self.assertEqual(result.status_code,202,result.text)
        self.assertEqual(observed[0][1]['day_targets']['rest']['kcal_100g']['target'],1900)
        self.assertEqual(observed[0][1]['energy_balance_target_kcal'],-250)
        self.assertEqual(self.client.get('/api/profile').json()['profile'],before)

    def test_failed_generation_never_persists_draft_mode(self):
        observed=[]
        async def failing(job,user,profile,data,kind,review_state=None):
            observed.append((profile['mode'],data,review_state))
            with self.app.connect() as db:db.execute("UPDATE job SET state='failed',error=? WHERE id=?",(json.dumps({'detail':'Synthetic failure'}),job))
        with self.app.connect() as db:
            stored=dict(self.profile,personal_diets=True,mode='free');db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(stored),self.user))
        before=self.client.get('/api/profile').json()['profile']
        with patch.object(self.app,'planning_job',side_effect=failing):
            result=self.client.post('/api/plans/week',json={'week_start':self.date,'mode':'sedentary'},headers=self.headers)
        self.assertEqual(result.status_code,202,result.text);self.assertEqual(observed[0][0],'sedentary');self.assertTrue(observed[0][2])
        self.assertEqual(self.client.get('/api/profile').json()['profile'],before)

for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(PlanningReviewTests,name,None)

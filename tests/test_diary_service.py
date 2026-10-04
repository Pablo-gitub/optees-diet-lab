import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]

class DiaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();os.environ['DIET_WEB_DB']=str(Path(cls.temp.name)/'web.sqlite')
        spec=importlib.util.spec_from_file_location('diary_web',ROOT/'web/app.py');cls.app=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.app);del os.environ['DIET_WEB_DB']
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.app.attempts.clear();self.client=TestClient(self.app.app);name='diary'+str(id(self))+str(int(dt.datetime.now().timestamp()*1000000))
        self.client.post('/api/register',json=dict(username=name,password='test-password-123'))
        self.client.post('/api/login',json=dict(username=name,password='test-password-123'))
        data=self.client.get('/api/profile').json();self.headers={'X-CSRF-Token':data['csrf']};self.profile=data['profile'];self.date=self.app.diary.local_today().isoformat()
        with self.app.connect() as db:
            self.user=db.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()['id']
            targets=json.dumps(self.profile['targets']);week=db.execute("INSERT INTO week_plan(user_id,week_start,mode,status,created,targets) VALUES(?,?,'free','active',0,?)",(self.user,self.date,targets)).lastrowid
            self.items=[dict(food=dict(source='CREA',id='000800'),grams=80,units=None)]
            self.meal=db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status) VALUES(?,?,'lunch',?,'best','chosen')",(week,self.date,json.dumps(self.items))).lastrowid
    def post(self,path,**data):return self.client.post(path,json=dict(date=self.date,slot='lunch',**data),headers=self.headers)
    def test_confirm_idempotent_edit_delete_and_reset(self):
        a=self.post('/api/diary/confirm');self.assertEqual(a.status_code,200);meal=a.json()['meals'][2]
        self.assertEqual(meal['state'],'as_planned');self.assertEqual(meal['eaten']['items'][0]['grams'],80)
        self.assertEqual(len(self.post('/api/diary/confirm').json()['meals'][2]['eaten']['items']),1)
        entry=meal['eaten']['items'][0]['id']
        response=self.client.patch(f'/api/diary/entries/{entry}',json={'grams':90},headers=self.headers)
        self.assertEqual(response.json()['meals'][2]['state'],'modified')
        self.assertEqual(self.client.delete(f'/api/diary/entries/{entry}',headers=self.headers).json()['meals'][2]['state'],'modified')
        reset=self.post('/api/diary/reset').json();self.assertIsNone(reset['meals'][2]['eaten']);self.assertIsNone(reset['totals']['eaten'])
    def test_unknown_is_not_zero_and_added_unplanned_and_skipped(self):
        view=self.client.get('/api/day',params={'date':self.date}).json();self.assertIsNone(view['totals']['eaten']);self.assertEqual(view['totals']['coverage']['logged_slots'],0)
        a=self.post('/api/diary/entries',food=dict(source='CREA',id='007510'),grams=100).json();self.assertEqual(a['meals'][2]['state'],'modified')
        skip=self.post('/api/diary/skip').json();self.assertEqual(skip['totals']['eaten']['kcal'],0);self.assertEqual(skip['totals']['coverage']['logged_slots'],1)
        r=self.client.post('/api/diary/entries',json=dict(date=self.date,slot='morning_snack',food=dict(source='CREA',id='007510'),grams=100),headers=self.headers).json();self.assertEqual(r['meals'][1]['state'],'unplanned')
    def test_invalid_quantities_dates_refs_and_csrf(self):
        self.assertEqual(self.client.post('/api/diary/confirm',json=dict(date=self.date,slot='lunch')).status_code,403)
        for grams in [0,3001,True,1.5]:
            response=self.post('/api/diary/entries',food=dict(source='CREA',id='000800'),grams=grams);self.assertEqual(response.status_code,400);self.assertEqual(response.json()['code'],'invalid_input')
        self.assertEqual(self.post('/api/diary/entries',food=dict(source='CREA',id='missing'),grams=100).status_code,400)
        future=(self.app.diary.local_today()+dt.timedelta(days=2)).isoformat()
        self.assertEqual(self.client.post('/api/diary/skip',json=dict(date=future,slot='lunch'),headers=self.headers).status_code,400)
    def test_measurements_isolation_and_units(self):
        response=self.client.post('/api/measurements',json=dict(date=self.date,kind='weight',value=81,unit='kg'),headers=self.headers);self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/measurements').json()[0]['value'],81)
        self.assertEqual(self.client.post('/api/measurements',json=dict(date=self.date,kind='weight',value=81,unit='cm'),headers=self.headers).status_code,400)
        other=TestClient(self.app.app);other.post('/api/register',json=dict(username='other'+str(id(self)),password='other-password-123'));other.post('/api/login',json=dict(username='other'+str(id(self)),password='other-password-123'));h={'X-CSRF-Token':other.get('/api/profile').json()['csrf']}
        self.assertEqual(other.get('/api/measurements').json(),[])
        self.assertIsNone(other.get('/api/day',params=dict(date=self.date)).json()['meals'][2]['planned'])
        entry=self.post('/api/diary/confirm').json()['meals'][2]['eaten']['items'][0]['id']
        self.assertEqual(other.patch(f'/api/diary/entries/{entry}',json=dict(grams=100),headers=h).status_code,404)
    def test_apply_preserves_locked_and_logged_slots_and_never_writes_diary(self):
        self.post('/api/diary/confirm')
        with self.app.connect() as db:
            week=db.execute('SELECT week_plan_id FROM planned_meal WHERE id=?',(self.meal,)).fetchone()[0]
            db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status,locked) VALUES(?,?,'dinner',?,'best','chosen',1)",(week,self.date,json.dumps(self.items)))
            plan=dict(id=1,role='best',selections=[dict(meal=m,food_id='000800',source='CREA',grams=100) for m in ['lunch','dinner','breakfast']])
            payload=dict(run_id='1',mode='free',plans=[plan]);set_id=db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,0,?,?)',(self.user,json.dumps(payload),'{}')).lastrowid
        response=self.client.post(f'/api/plan-sets/{set_id}/apply',json=dict(plan_id=1,scope='day',date=self.date),headers=self.headers)
        self.assertEqual(response.status_code,200);view=response.json();self.assertEqual(len(view['skipped_slots']),2)
        self.assertEqual(view['meals'][0]['planned']['items'][0]['grams'],100);self.assertIsNone(view['meals'][0]['eaten'])
        self.assertEqual(view['meals'][2]['planned']['items'][0]['grams'],80)
    def test_missing_nutrient_propagates_and_search_accent_insensitive(self):
        with patch.object(self.app.diary,'resolve_food',return_value=dict(name='Test',source_label='test',per_100g=dict(kcal=None,protein_g=1,fat_g=0,carbs_available_g=0))):
            entries=self.app.diary.enriched(self.items,self.profile);self.assertIsNone(self.app.diary.totals(entries)['kcal'])
        response=self.client.get('/api/foods/search',params=dict(q='caffe',limit=5));self.assertEqual(response.status_code,200)
        self.assertTrue(response.json());self.assertTrue(all('food' in f for f in response.json()))
    def test_migration_repeat_and_week_coverage(self):
        with self.app.connect() as db:self.app.diary.migrate(db);self.app.diary.migrate(db)
        view=self.client.get('/api/week',params=dict(start=self.date)).json();self.assertEqual(len(view['days']),7);self.assertIsNone(view['budget']['kcal_eaten']);self.assertIsNone(view['days'][1]['kcal_planned'])
        self.post('/api/diary/confirm');view=self.client.get('/api/week',params=dict(start=self.date)).json();self.assertEqual(view['budget']['complete_days'],1)

    def test_job_lifecycle_and_automatic_diary_locks(self):
        import asyncio
        import time
        from contextlib import asynccontextmanager
        from unittest.mock import patch
        self.post('/api/diary/confirm')
        observed=[]
        @asynccontextmanager
        async def stream(*args):yield (None,None)
        class Session:
            def __init__(self,*args):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def initialize(self):pass
        async def generate(session,profile,data,*args):
            observed.append(data)
            return dict(spec_version='orchestration-v2',week_start=data['week_start'],mode='free',plans=[],status='infeasible',warnings=[])
        with TestClient(self.app.app) as client,patch.object(self.app,'stdio_client',stream),patch.object(self.app,'ClientSession',Session),patch('week_orchestration.generate_week',side_effect=generate):
            client.cookies.update(self.client.cookies)
            self.assertEqual(client.post('/api/plans/week',json=dict(week_start=self.date)).status_code,403)
            response=client.post('/api/plans/week',json=dict(week_start=self.date),headers=self.headers)
            self.assertEqual(response.status_code,202);job=response.json()['job_id']
            for _ in range(100):
                value=client.get('/api/jobs/'+job).json()
                if value['state'] in ('done','failed'):break
                time.sleep(.01)
            self.assertEqual(value['state'],'done');set_id=value['result']['plan_set_id']
            self.assertEqual(client.get('/api/plan-sets/'+str(set_id)).json()['status'],'infeasible')
        self.assertEqual(observed[0]['locked'][0]['items'][0]['grams'],80)
        outsider=TestClient(self.app.app)
        name='jobother'+str(id(self));outsider.post('/api/register',json=dict(username=name,password='other-password-123'));outsider.post('/api/login',json=dict(username=name,password='other-password-123'))
        self.assertEqual(outsider.get('/api/jobs/'+job).status_code,404)
        self.assertEqual(outsider.get('/api/plan-sets/'+str(set_id)).status_code,404)

    def test_personal_label_units_and_recipe_runs_are_owner_scoped(self):
        from test_daily_meals import preference_fixture
        profile=dict(self.profile,food_preferences=preference_fixture())
        with self.app.connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(profile),self.user))
            recipe=dict(title='Ricetta sintetica',status='optimal',selections=[dict(grams=100)],nutrients=dict(kcal=200,protein_g=10,fat_g=5,carbs_g=30))
            recipe_id=db.execute('INSERT INTO recipe_runs(user_id,created,payload) VALUES(?,0,?)',(self.user,json.dumps(recipe))).lastrowid
        result=self.client.post('/api/diary/entries',json=dict(date=self.date,slot='breakfast',food=dict(source='user_label',id='bar'),units=2),headers=self.headers)
        self.assertEqual(result.status_code,200);self.assertEqual(result.json()['meals'][0]['eaten']['items'][0]['grams'],70)
        result=self.client.post('/api/diary/entries',json=dict(date=self.date,slot='morning_snack',food=dict(source='recipe',id='run:'+str(recipe_id)),grams=50),headers=self.headers)
        self.assertEqual(result.status_code,200);self.assertEqual(result.json()['meals'][1]['eaten']['kcal'],100)
        outsider=TestClient(self.app.app);name='recipediary'+str(id(self));outsider.post('/api/register',json=dict(username=name,password='other-password-123'));outsider.post('/api/login',json=dict(username=name,password='other-password-123'));headers={'X-CSRF-Token':outsider.get('/api/profile').json()['csrf']}
        self.assertEqual(outsider.post('/api/diary/entries',json=dict(date=self.date,slot='lunch',food=dict(source='recipe',id='run:'+str(recipe_id)),grams=50),headers=headers).status_code,400)
        self.assertEqual(self.client.patch('/api/diary/entries/1',json=dict(grams=100)).status_code,403)

    def test_measurement_and_apply_and_meal_jobs_require_csrf(self):
        for path in ['/api/measurements','/api/plan-sets/1/apply','/api/plans/meal-alternatives','/api/diary/reset','/api/diary/skip','/api/diary/entries']:
            self.assertEqual(self.client.post(path,json={}).status_code,403)
        self.assertEqual(self.client.delete('/api/diary/entries/1').status_code,403)

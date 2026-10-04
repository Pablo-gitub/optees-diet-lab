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

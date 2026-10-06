import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import shopping_list
import week_report
ROOT=Path(__file__).resolve().parents[1]

class WeekReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();os.environ['DIET_WEB_DB']=str(Path(self.temp.name)/'web.sqlite')
        spec=importlib.util.spec_from_file_location('report_web',ROOT/'web/app.py');self.web=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.web);del os.environ['DIET_WEB_DB']
        self.client=TestClient(self.web.app);self.client.post('/api/register',json=dict(username='synthetic',password='test-password-123'));self.client.post('/api/login',json=dict(username='synthetic',password='test-password-123'))
        data=self.client.get('/api/profile').json();self.headers={'X-CSRF-Token':data['csrf']};self.profile=data['profile'];today=dt.date(2026,10,6);self.today=today;self.start='2026-10-05'
        self.recipe=dict(status='optimal',title='Pasta sintetica',selections=[dict(source='CREA',id='000800',grams=100,food='Pasta di semola'),dict(source='CREA',id='006670',grams=100,food='Passata')],trace_condiments=[dict(name='Salt and pepper')],nutrients=dict(kcal=400,protein_g=12,fat_g=2,carbs_g=82))
        self.profile['_recipe_runs']={'run:1':self.recipe}
        with self.web.connect() as db:
            self.user=db.execute('SELECT id FROM users WHERE username="synthetic"').fetchone()[0]
            self.week=db.execute("INSERT INTO week_plan(user_id,week_start,mode,status,created,targets) VALUES(?,?,'free','active',0,?)",(self.user,self.start,json.dumps(self.profile['targets']))).lastrowid
            for i in range(7):
                date=(dt.date.fromisoformat(self.start)+dt.timedelta(days=i)).isoformat()
                items=[dict(food=dict(source='CREA',id='000800'),grams=100,units=None)]
                if i==2:items=[dict(food=dict(source='recipe',id='run:1'),grams=400,units=None)]
                db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status) VALUES(?,?,'lunch',?,'best','chosen')",(self.week,date,json.dumps(items)))
    def tearDown(self):self.temp.cleanup()
    def test_aggregate_expand_and_exclude_consumed(self):
        with self.web.connect() as db:
            with patch.object(self.web.diary,'local_today',return_value=self.today):self.web.diary.diary_mutation(db,self.user,self.profile,'confirm',dict(date=self.today.isoformat(),slot='lunch'))
            result=shopping_list.shopping_list(db,self.user,self.profile,self.start,today=self.today)
            values={i['canonical_id']:i['grams'] for i in result['items']}
            self.assertEqual(values,{'CREA:000800':600,'CREA:006670':200});self.assertEqual(len(result['trace_condiments']),1);self.assertIsNone(result['trace_condiments'][0]['grams'])
            whole=shopping_list.shopping_list(db,self.user,self.profile,self.start,True,self.today)
            self.assertEqual(next(i['grams'] for i in whole['items'] if i['food']['id']=='000800'),800)
    def test_package_units_and_preferred_merge(self):
        self.assertEqual(shopping_list.package_grams('1,5 kg'),1500);self.assertIsNone(shopping_list.package_grams('500 ml'));self.assertIsNone(shopping_list.package_grams('2 x 250g'))
        profile={'food_preferences':{'preferred_products':{'000800':dict(source='OFF',id='synthetic-product')}}}
        self.assertEqual(shopping_list.canonical_ref(dict(source='OFF',id='synthetic-product'),profile)[0],'CREA:000800')
    def test_pdf_and_owner_endpoints(self):
        workout=dict(id='synthetic-workout',name='Allenamento sintetico',duration_seconds=1800,demo=False,pending_configuration=[],exercises=[dict(source_id='synthetic-squat',name='Squat sintetico',sets=3,repetitions=8,load_kg=20)])
        from activity_service import catalog,snapshot
        activity=snapshot(next(a for a in catalog()['activities'] if a['id']=='walking_moderate'),20,80)
        with self.web.connect() as db:
            for session,date in [(workout,'2026-10-07'),(activity,'2026-10-08')]:db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,minutes,status,snapshot) VALUES(?,?,?,?,'chosen',?)",(self.week,date,session['id'],session['duration_seconds']/60,json.dumps(session)))
        with patch.object(self.web,'owner_profile',return_value=self.profile),patch.object(shopping_list.diary,'local_today',return_value=self.today):
            response=self.client.get('/api/week/'+self.start+'/shopping-list');self.assertEqual(response.status_code,200)
            pdf=self.client.get('/api/week/'+self.start+'/report.pdf');self.assertEqual(pdf.status_code,200);self.assertEqual(pdf.headers['content-type'],'application/pdf');self.assertTrue(pdf.content.startswith(b'%PDF'))
            import subprocess
            path=Path(self.temp.name)/'report.pdf';path.write_bytes(pdf.content)
            text=subprocess.check_output(['pdftotext',str(path),'-'],text=True)
            self.assertIn('Lista',text);self.assertIn('Pasta sintetica',text);self.assertIn('Passata',text);self.assertIn('Squat sintetico',text);self.assertIn('3 serie',text);self.assertIn('20,0 kg',text);self.assertIn('Camminata normale',text)
            info=subprocess.check_output(['pdfinfo',str(path)],text=True)
            self.assertIn('A4',info)
            Path('/tmp/synthetic-week-report.pdf').write_bytes(pdf.content)
        anonymous=TestClient(self.web.app);self.assertEqual(anonymous.get('/api/week/'+self.start+'/shopping-list').status_code,401)
        self.assertEqual(self.client.get('/api/week/2026-10-12/shopping-list').status_code,404)

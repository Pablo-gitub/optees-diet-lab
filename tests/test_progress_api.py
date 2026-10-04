import datetime as dt
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_diary_service as base
import progress_analysis as progress


class ProgressAPI(base.DiaryTests):
    def setUp(self):
        super().setUp();self.today=dt.date(2026,9,21);self.start='2026-09-14'
        with self.app.connect() as db:
            db.execute('DELETE FROM planned_meal WHERE week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?)',(self.user,));db.execute('DELETE FROM week_plan WHERE user_id=?',(self.user,))
    def seed_week(self,start=None,complete=7,full=True):
        start=start or self.start;slots=self.app.diary.SLOTS if full else ('lunch','dinner');context={}
        with self.app.connect() as db:
            week=db.execute("INSERT INTO week_plan(user_id,week_start,mode,status,created,targets) VALUES(?,?,'free','active',0,?)",(self.user,start,json.dumps(self.profile['daily_meals']['targets']))).lastrowid
            for index,date in enumerate(progress.days(start)):
                for slot in slots:
                    db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status) VALUES(?,?,?,?,'best','chosen')",(week,date,slot,json.dumps(self.items)))
                    if index<complete:self.app.diary.diary_mutation(db,self.user,self.profile,'confirm',dict(date=date,slot=slot))
                view=self.app.diary.day_view(db,self.user,self.profile,date)
                context[date]=dict(scope='full_day_planned_meals' if full else 'lunch_and_dinner_only',progress_forecast=dict(valid=True,scope='full_day_planned_meals' if full else 'lunch_and_dinner_only',planned_kcal=view['totals']['planned']['kcal'],energy_scenarios=dict(status='available',consumption_kcal=dict(low=1500,central=1600,high=1700))))
            db.execute('UPDATE week_plan SET day_context=? WHERE id=?',(json.dumps(context),week))
        return week
    def test_summary_complete_contract_check_in_raw_and_expected(self):
        with patch.object(self.app.diary,'local_today',return_value=self.today),patch.object(self.app,'load_health_report',return_value=None):
            self.seed_week()
            self.client.post('/api/measurements',json=dict(date=self.start,kind='weight',unit='kg',value=80),headers=self.headers)
            response=self.client.post('/api/progress/check-in',json=dict(date=self.today.isoformat(),weight_kg=79.8),headers=self.headers)
            self.assertEqual(response.status_code,200,response.text);result=response.json();week=result['previous_week']
            self.assertEqual(week['diet']['value'],1);self.assertEqual(week['kcal_average']['days'],7);self.assertEqual(week['expected_weight']['status'],'available')
            self.assertEqual(len(week['expected_weight']['points']),8);self.assertEqual(week['comparison']['status'],'available')
            self.assertIn('parameters',result['analysis']['weight']);self.assertEqual(len(result['analysis']['weight']['raw_points']),2)
            summary=self.client.get('/api/stats/summary').json()
            self.assertEqual(summary['weight']['status'],'available');self.assertIn('trend_7d',summary['weight'])
            self.assertEqual(summary['adherence_week']['status'],'insufficient_data') # current Monday has no elapsed days
            self.assertIsNone(summary['kcal_average']['eaten_avg'])
            with self.app.connect() as db:self.assertEqual(json.loads(db.execute('SELECT profile FROM users WHERE id=?',(self.user,)).fetchone()['profile'])['targets'],self.profile['targets'])
    def test_partial_diary_missing_nutrients_and_main_meals_are_not_full_days(self):
        with patch.object(self.app.diary,'local_today',return_value=self.today):
            self.seed_week(complete=4)
            with self.app.connect() as db:week=progress.week_analysis(db,self.user,self.profile,self.start,self.today)
            self.assertEqual(week['diet']['status'],'insufficient_data');self.assertIsNone(week['diet']['value']);self.assertIn('reason',week['diet'])
            self.assertIsNone(week['kcal_average']['eaten_avg'])
            later='2026-09-07';self.seed_week(later,full=False)
            with self.app.connect() as db:week=progress.week_analysis(db,self.user,self.profile,later,self.today)
            self.assertEqual(week['diet']['status'],'available');self.assertEqual(week['kcal_average']['status'],'insufficient_data')
    def test_workout_adherence_counts_only_linked_completed_logs_and_missing_is_unknown(self):
        with patch.object(self.app.diary,'local_today',return_value=self.today):
            week=self.seed_week();snapshot=self.app.workouts.session_by_id(self.profile,'continuous_stationary-bike')
            with self.app.connect() as db:
                ids=[]
                for date in (self.start,'2026-09-16'):
                    ids.append(db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,status,snapshot) VALUES(?,?,'continuous_stationary-bike','chosen',?)",(week,date,json.dumps(snapshot))).lastrowid)
                db.execute("INSERT INTO workout_log(user_id,date,session_id,ended,snapshot) VALUES(?,?,'continuous_stationary-bike','done',?)",(self.user,self.start,json.dumps(snapshot)))
                before=progress.week_analysis(db,self.user,self.profile,self.start,self.today)['training']
                self.assertEqual(before['status'],'insufficient_data');self.assertIsNone(before['value']);self.assertEqual(before['free_done'],1)
                db.execute("UPDATE planned_session SET status='done' WHERE id=?",(ids[0],))
                db.execute("INSERT INTO workout_log(user_id,date,planned_session_id,session_id,ended,snapshot) VALUES(?,?,?,'continuous_stationary-bike','done',?)",(self.user,self.start,ids[0],json.dumps(snapshot)))
                db.execute("UPDATE planned_session SET status='skipped' WHERE id=?",(ids[1],))
                after=progress.week_analysis(db,self.user,self.profile,self.start,self.today)['training']
                self.assertEqual(after['status'],'available');self.assertEqual(after['value'],.5);self.assertEqual(after['done'],1)
                analysis=progress.progress(db,self.user,self.profile,[],dt.date.fromisoformat(self.start),1)
                self.assertEqual(progress.summary(analysis)['workouts']['done'],2) # explicit completions today, including one free session
                self.assertEqual(progress.summary(analysis)['adherence_week']['training'],None)
    def test_check_in_csrf_monday_validation_and_owner_isolation(self):
        self.assertEqual(self.client.post('/api/progress/check-in',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/progress/check-in',json=dict(date='2026-09-22',weight_kg=80),headers=self.headers).status_code,400)
        outsider=TestClient(self.app.app)
        self.assertEqual(outsider.get('/api/stats/progress').status_code,401)
        self.client.post('/api/measurements',json=dict(date='2026-09-14',kind='weight',unit='kg',value=88),headers=self.headers)
        outsider.post('/api/register',json=dict(username='progressother'+str(self.user),password='test-password-123'));outsider.post('/api/login',json=dict(username='progressother'+str(self.user),password='test-password-123'))
        with patch.object(self.app,'load_health_report',return_value=None):
            values=outsider.get('/api/stats/progress').json()['weight']['raw_points']
        self.assertEqual(values,[])
        self.assertEqual(self.client.get('/api/stats/progress',params=dict(weeks=0)).status_code,400)
    def test_all_imported_repeated_weight_points_remain_readable(self):
        directory=Path(self.temp.name)/('health'+str(self.user));directory.mkdir()
        zone=dt.timezone.utc;timestamp=dt.datetime(2026,9,14,tzinfo=zone).timestamp()
        with sqlite3.connect(directory/'health.sqlite') as db:
            db.execute('CREATE TABLE measures(kind TEXT,value REAL,end REAL,source TEXT)')
            db.executemany('INSERT INTO measures VALUES(?,?,?,?)',[('weight',80+i*.001,timestamp+i,'Synthetic') for i in range(100)])
        with patch.object(self.app,'health_directory',return_value=directory),self.app.connect() as db:
            values=self.app.measurement_values(db,self.user,dict(timezone='Europe/Rome',measures={}),self.today)
        self.assertEqual(len(values),100);self.assertEqual(len(progress.weight_series(values,self.today)['raw_points']),100)
    def test_forecast_invalidates_when_applied_food_plan_changes(self):
        with patch.object(self.app.diary,'local_today',return_value=self.today):
            self.seed_week()
            with self.app.connect() as db:
                progress.invalidate_forecast(db,self.user,self.start)
                week=progress.week_analysis(db,self.user,self.profile,self.start,self.today)
            weight=progress.weight_series([dict(date=self.start,kind='weight',unit='kg',value=80,source='manual')],self.today)
            self.assertEqual(progress.expected_week(week,weight)['status'],'insufficient_data')

    def test_unknown_nutrients_remain_insufficient_and_day_apply_invalidates_forecast(self):
        with patch.object(self.app.diary,'local_today',return_value=self.today):
            self.seed_week()
            real=self.app.diary.resolve_food
            def missing(ref,profile):
                food=real(ref,profile);food['per_100g']['kcal']=None;return food
            with self.app.connect() as db,patch.object(self.app.diary,'resolve_food',side_effect=missing):
                result=progress.week_analysis(db,self.user,self.profile,self.start,self.today)
                self.assertIsNone(result['diet']['value']);self.assertIsNone(result['kcal_average']['eaten_avg'])
            with self.app.connect() as db:
                self.app.diary.diary_mutation(db,self.user,self.profile,'reset',dict(date=self.start,slot='lunch'))
                plan=dict(id=1,selections=[dict(meal='lunch',food_id='000800',grams=90)])
                self.app.diary.apply_plan(db,self.user,self.profile,dict(mode='free',run_id='1'),plan,dict(plan_id=1,date=self.start,slot='lunch',scope='meal'))
                context=progress.contexts(db,self.user,self.start)
                self.assertFalse(context[self.start]['progress_forecast']['valid'])


for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(ProgressAPI,name,None)

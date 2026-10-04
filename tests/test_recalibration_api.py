import copy
import datetime as dt
import json
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_progress_api as progress_tests
from daily_meals import defaults
import progress_analysis as progress


class RecalibrationAPI(progress_tests.ProgressAPI):
    def setUp(self):
        super().setUp()
        self.report=dict(timezone='Europe/Rome',measures={},weight_history=[],scenarios=dict(status='available'),analysis_version='synthetic-v1',import_={'fingerprint':'synthetic'},daily=[])
        self.report['import']=self.report.pop('import_')
        self.clock=patch.object(self.app.diary,'local_today',return_value=self.today);self.clock.start();self.addCleanup(self.clock.stop)
        self.health=patch.object(self.app,'load_health_report',side_effect=lambda *args:copy.deepcopy(self.report));self.health.start();self.addCleanup(self.health.stop)
        self.profile['daily_meals']=defaults(True);self.profile['daily_meals']['targets_demo']=False;self.profile['energy_balance_target_kcal']=0
        response=self.client.put('/api/profile',json=self.profile,headers=self.headers);self.assertEqual(response.status_code,200,response.text)
    def seed_calibration(self):
        for start in ('2026-09-07','2026-09-14'):self.seed_week(start)
        with self.app.connect() as db:
            for i in range(14):
                date=(self.today-dt.timedelta(days=14-i)).isoformat()
                self.app.diary.add_measurement(db,self.user,dict(date=date,kind='weight',unit='kg',value=80))
                self.report['daily'].append(dict(date=date,usable_for_baseline=True,total_estimated_kcal=2300))
    def checkin(self):
        response=self.client.post('/api/progress/check-in',json=dict(date=self.today.isoformat(),weight_kg=80),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['recalibration']
    def stored_profile(self):
        with self.app.connect() as db:return json.loads(db.execute('SELECT profile FROM users WHERE id=?',(self.user,)).fetchone()['profile'])
    def test_proposal_is_explained_and_does_not_change_targets_then_rejection_recorded(self):
        self.seed_calibration();before=self.stored_profile();result=self.checkin();self.assertEqual(result['status'],'available',result)
        proposal=result['proposal'];self.assertEqual(before,self.stored_profile());self.assertEqual(proposal['data_used']['complete_intake_days'],14)
        self.assertTrue(proposal['uncertainty']['limitations']);self.assertTrue(proposal['limits_applied']);self.assertTrue(proposal['expenditure']['no_workout_calories_added'])
        response=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/reject",json=dict(state_token=proposal['state_token'],reason='Preferisco attendere'),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text);self.assertFalse(response.json()['targets_changed']);self.assertEqual(before,self.stored_profile())
        history=self.client.get('/api/progress/recalibrations').json();self.assertEqual(history[0]['status'],'rejected');self.assertEqual(history[0]['decision_reason'],'Preferisco attendere')
    def test_approval_is_atomic_bounded_future_only_and_rolling_week_cannot_be_bypassed(self):
        self.seed_calibration();before=self.stored_profile();proposal=self.checkin()['proposal']
        with self.app.connect() as db:
            weeks=[dict(r) for r in db.execute('SELECT * FROM week_plan WHERE user_id=?',(self.user,))];entries=[dict(r) for r in db.execute('SELECT * FROM diary_entry WHERE user_id=?',(self.user,))]
        response=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text);after=self.stored_profile()
        old=before['daily_meals']['targets'];new=after['daily_meals']['targets'];self.assertLessEqual(abs(old['kcal_100g']['target']-new['kcal_100g']['target']),min(100,.05*old['kcal_100g']['target']))
        for n in old:
            self.assertEqual(old[n]['min'],new[n]['min']);self.assertEqual(old[n]['max'],new[n]['max'])
            if n!='kcal_100g':self.assertEqual(old[n],new[n])
        self.assertIn('personal_expenditure_estimate',after)
        with self.app.connect() as db:
            self.assertEqual(weeks,[dict(r) for r in db.execute('SELECT * FROM week_plan WHERE user_id=?',(self.user,))]);self.assertEqual(entries,[dict(r) for r in db.execute('SELECT * FROM diary_entry WHERE user_id=?',(self.user,))])
        self.assertEqual(self.client.post(f"/api/progress/recalibrations/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=self.headers).status_code,409)
        self.assertEqual(self.checkin()['status'],'insufficient_data')
        next_monday=self.today+dt.timedelta(days=7)
        with patch.object(self.app.diary,'local_today',return_value=next_monday):
            result=self.client.post('/api/progress/check-in',json=dict(date=next_monday.isoformat(),weight_kg=80),headers=self.headers).json()['recalibration']
        self.assertEqual(result['status'],'insufficient_data');self.assertIn('sette giorni',result['reason'])
    def test_missing_data_never_creates_proposal(self):
        result=self.checkin();self.assertEqual(result['status'],'insufficient_data');self.assertIn('reason',result)
        self.assertEqual(self.client.get('/api/progress/recalibrations').json(),[])
    def test_changed_diary_health_weight_or_profile_is_409_and_no_target_write(self):
        self.seed_calibration()
        for change in ('diary','health','weight','profile','plan'):
            proposal=self.checkin()['proposal'];before=self.stored_profile()
            with self.app.connect() as db:
                if change=='diary':db.execute('UPDATE diary_entry SET updated=updated+1 WHERE user_id=?',(self.user,))
                if change=='weight':self.app.diary.add_measurement(db,self.user,dict(date='2026-09-20',kind='weight',unit='kg',value=80))
                if change=='plan':db.execute("UPDATE planned_meal SET role='varied' WHERE week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?)",(self.user,))
                if change=='profile':
                    changed=copy.deepcopy(before);changed['display_name']='changed';db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(changed),self.user))
            if change=='health':self.report['import']['fingerprint']+='new'
            current=self.stored_profile()
            decision='reject' if change=='health' else 'approve'
            response=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/{decision}",json=dict(state_token=proposal['state_token']),headers=self.headers)
            self.assertEqual(response.status_code,409,response.text);self.assertEqual(response.json()['code'],'progress_state_changed');self.assertEqual(self.stored_profile(),current)
    def test_csrf_isolation_and_old_proposal_superseded(self):
        self.seed_calibration();first=self.checkin()['proposal'];second=self.checkin()['proposal']
        self.assertEqual(self.client.post(f"/api/progress/recalibrations/{second['id']}/approve",json={}).status_code,403)
        self.assertEqual(self.client.post(f"/api/progress/recalibrations/{first['id']}/approve",json=dict(state_token=first['state_token']),headers=self.headers).status_code,409)
        outsider=TestClient(self.app.app);name='calibrationother'+str(self.user)
        outsider.post('/api/register',json=dict(username=name,password='test-password-123'));outsider.post('/api/login',json=dict(username=name,password='test-password-123'))
        token=outsider.get('/api/profile').json()['csrf']
        self.assertEqual(outsider.get('/api/progress/recalibrations').json(),[])
        response=outsider.post(f"/api/progress/recalibrations/{second['id']}/reject",json=dict(state_token=second['state_token']),headers={'X-CSRF-Token':token})
        self.assertEqual(response.status_code,404)
    def test_missing_weights_health_or_demo_targets_prevent_proposals(self):
        self.seed_calibration()
        with self.app.connect() as db:db.execute("DELETE FROM measurement WHERE user_id=? AND date NOT IN ('2026-09-07','2026-09-20')",(self.user,))
        self.assertEqual(self.checkin()['status'],'insufficient_data')
        with self.app.connect() as db:
            for i in range(1,13):self.app.diary.add_measurement(db,self.user,dict(date=(self.today-dt.timedelta(days=14-i)).isoformat(),kind='weight',unit='kg',value=80))
        self.report['daily'].pop();self.assertEqual(self.checkin()['status'],'insufficient_data')
        self.report['daily'].append(dict(date='2026-09-20',usable_for_baseline=True,total_estimated_kcal=2300))
        raw=self.stored_profile();raw['daily_meals']['targets_demo']=True
        with self.app.connect() as db:db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(raw),self.user))
        self.assertEqual(self.checkin()['status'],'insufficient_data')
    def test_approval_rechecks_safety_even_if_persisted_payload_is_corrupted(self):
        self.seed_calibration();proposal=self.checkin()['proposal'];before=self.stored_profile()
        with self.app.connect() as db:
            payload=json.loads(db.execute('SELECT payload FROM recalibration_proposal WHERE id=?',(proposal['id'],)).fetchone()['payload']);payload['changes']['daily']['after']['kcal_100g']['target']=9999
            db.execute('UPDATE recalibration_proposal SET payload=? WHERE id=?',(json.dumps(payload),proposal['id']))
        result=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=self.headers)
        self.assertEqual(result.status_code,409,result.text);self.assertEqual(self.stored_profile(),before)

    def test_expired_proposal_cannot_be_approved(self):
        self.seed_calibration();proposal=self.checkin()['proposal'];before=self.stored_profile()
        with self.app.connect() as db:db.execute('UPDATE recalibration_proposal SET checkin_date=? WHERE id=?',((self.today-dt.timedelta(days=7)).isoformat(),proposal['id']))
        result=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=self.headers)
        self.assertEqual(result.status_code,409,result.text);self.assertEqual(result.json()['code'],'proposal_expired');self.assertEqual(before,self.stored_profile())

    def test_changed_health_availability_invalidates_pending_decision(self):
        self.seed_calibration();proposal=self.checkin()['proposal'];before=self.stored_profile()
        self.report['scenarios']['status']='insufficient_or_stale'
        result=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=self.headers)
        self.assertEqual(result.status_code,409,result.text);self.assertEqual(result.json()['code'],'progress_state_changed');self.assertEqual(before,self.stored_profile())


for name in tuple(vars(progress_tests.ProgressAPI)):
    if name.startswith('test_'):setattr(RecalibrationAPI,name,None)

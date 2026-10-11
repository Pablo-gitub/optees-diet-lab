"""Verifiche T-004 con fixture idonee e transazioni chiuse prima delle richieste."""
import contextlib
from unittest.mock import patch
import json
import test_checkin_presumed as base
import progress_recalibration as recal

class CorrectionExtra(base.CheckinPresumedTests):
    def prepare(self):
        self.seed_days(range(1,15),confirmed=True)
        self.calibration_data()
        self.profile['daily_meals']['targets']['kcal_100g']['target']=2000
        with self.app.connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(self.profile),self.user))
        for day in self.report['daily']:day['total_estimated_kcal']=1600
        first=self.checkin(mode='count').json()['recalibration']['proposal']
        self.assertEqual(first['applied_delta_kcal'],-100)
        self.approve(first)
        return first

    def approve(self,proposal):
        res=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=self.headers)
        self.assertEqual(res.status_code,200,res.text)

    def recalculate(self):
        res=self.client.post('/api/progress/check-in/review/recalculate',json=dict(checkin_date=self.date(0)),headers=self.headers)
        self.assertEqual(res.status_code,200,res.text)
        return res.json()

    def test_full_budget_then_reversal_and_history(self):
        first=self.prepare()
        self.assertEqual(self.recalculate()['status'],'no_adjustment')
        # 1800 kcal intake, peso costante: .75*1973.333 + .25*1800 = 1930.
        for day in self.report['daily']:day['total_estimated_kcal']=1973.3333333333333
        second=self.recalculate()['proposal']
        self.assertEqual(second['applied_delta_kcal'],30)
        self.assertEqual(second['cumulative_delta_kcal'],-70)
        self.assertEqual(second['allowed_delta_kcal']['min'],0)
        self.assertEqual(second['chained_from'],first['id'])
        self.approve(second)
        history=self.client.get('/api/progress/recalibrations').json()
        self.assertEqual({p['id'] for p in history if p['status']=='approved'},{first['id'],second['id']})

    def test_group_budget_uses_each_original_target(self):
        self.prepare()
        with self.app.connect() as db:
            profile=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(self.user,)).fetchone()[0])
            groups=dict(daily=profile['daily_meals']['targets'],**profile['day_type_targets'])
            # Simula target di riposo iniziale più basso, cap 80 e variazione già -80.
            row=db.execute("SELECT id,payload FROM recalibration_proposal WHERE user_id=? AND state='approved'",(self.user,)).fetchone()
            payload=json.loads(row['payload']);payload['changes']['rest']['before']['kcal_100g']['target']=1600
            groups['rest']['kcal_100g']['target']=1520
            db.execute('UPDATE recalibration_proposal SET payload=? WHERE id=?',(json.dumps(payload),row['id']))
            bounds,_,_=recal.chain_budget(db,self.user,self.date(0),groups)
            self.assertEqual(bounds['min'],0)
            self.assertEqual(bounds['max'],160)

    def test_changed_diary_invalidates_correction_token(self):
        self.prepare()
        for day in self.report['daily']:day['total_estimated_kcal']=1973.3333333333333
        proposal=self.recalculate()['proposal']
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db,self.user,self.profile,'skip',dict(date=self.date(2),slot='lunch'))
        res=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=self.headers)
        self.assertEqual(res.status_code,409,res.text)
        self.assertEqual(res.json()['code'],'progress_state_changed')

    def test_regular_proposal_cannot_bypass_cooldown_by_date(self):
        self.prepare()
        for day in self.report['daily']:day['total_estimated_kcal']=1973.3333333333333
        proposal=self.recalculate()['proposal']
        with self.app.connect() as db:
            payload=json.loads(db.execute('SELECT payload FROM recalibration_proposal WHERE id=?',(proposal['id'],)).fetchone()[0])
            payload.pop('chained_from')
            db.execute('UPDATE recalibration_proposal SET payload=? WHERE id=?',(json.dumps(payload),proposal['id']))
        res=self.client.post(f"/api/progress/recalibrations/{proposal['id']}/approve",json=dict(state_token=proposal['state_token']),headers=self.headers)
        self.assertEqual(res.status_code,409,res.text)
        self.assertEqual(res.json()['code'],'recalibration_cooldown')

    def test_no_adjustment_supersedes_pending(self):
        self.prepare()
        for day in self.report['daily']:day['total_estimated_kcal']=1973.3333333333333
        proposal=self.recalculate()['proposal']
        for day in self.report['daily']:day['total_estimated_kcal']=1600
        self.assertEqual(self.recalculate()['status'],'no_adjustment')
        history=self.client.get('/api/progress/recalibrations').json()
        self.assertEqual(next(p['status'] for p in history if p['id']==proposal['id']),'superseded')


    def test_saved_checkin_weight_is_used_after_measurement_edit(self):
        self.prepare()
        for day in self.report['daily']:day['total_estimated_kcal']=1973.3333333333333
        with self.app.connect() as db:
            self.app.diary.add_measurement(db,self.user,dict(date=self.date(0),kind='weight',unit='kg',value=80.1))
        proposal=self.recalculate()['proposal']
        checkin_point=next(p for p in proposal['data_used']['weight_points'] if p['date']==self.date(0))
        self.assertEqual(checkin_point['value'],80)
        self.approve(proposal)

    def test_other_recent_checkin_always_blocks_chain(self):
        self.prepare()
        with self.app.connect() as db:
            self.assertFalse(recal.cooldown(db,self.user,allowed_checkin_date=self.date(0)))
            self.assertTrue(recal.cooldown(db,self.user,allowed_checkin_date=self.date(1)))
            row=db.execute("SELECT * FROM recalibration_proposal WHERE user_id=? AND state='approved'",(self.user,)).fetchone()
            db.execute("INSERT INTO recalibration_proposal(user_id,checkin_date,created,state,fingerprint,payload,decided) VALUES(?,?,?,'approved',?,?,?)",(self.user,self.date(1),row['created'],row['fingerprint'],row['payload'],row['decided']))
            self.assertTrue(recal.cooldown(db,self.user,allowed_checkin_date=self.date(0)))


    def test_review_is_readonly_and_detects_changed_confirmation(self):
        self.seed_days(range(1,15))
        self.calibration_data()
        self.checkin(mode='count')
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db,self.user,self.profile,'confirm',dict(date=self.date(2),slot='lunch'))
        changes=[];real_connect=self.app.connect
        @contextlib.contextmanager
        def tracked():
            db=real_connect();before=db.total_changes
            try:
                with db:yield db
            finally:
                changes.append(db.total_changes-before);db.close()
        with patch.object(self.app,'connect',side_effect=tracked):
            self.assertFalse(self.client.get('/api/progress/check-in/review').json()['corrected'])
        self.assertTrue(changes)
        self.assertEqual(set(changes),{0})
        with self.app.connect() as db:
            row=db.execute('SELECT id FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(self.user,self.date(2),'lunch')).fetchone()
            self.app.diary.diary_mutation(db,self.user,self.profile,'edit',dict(grams=82),entry_id=row['id'])
        self.assertTrue(self.client.get('/api/progress/check-in/review').json()['corrected'])


for name in dir(base.CheckinPresumedTests):
    if name.startswith('test_'):setattr(CorrectionExtra,name,None)

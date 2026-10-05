import copy
import datetime as dt
import json
from unittest.mock import patch
from zoneinfo import ZoneInfo
import test_meal_rebalance as base
import contextual_bandit as bandit


class RebalanceEvaluation(base.RebalanceAPI):
    def setUp(self):
        super().setUp();self.plan.update(status='optimal',mode='free',role='varied',workout_sessions=[])
        with self.app.connect() as db:
            self.original_id=db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,0,?)',(self.user,json.dumps(self.plan))).lastrowid
            self.plan['id']=self.original_id
            db.execute('UPDATE plans SET payload=? WHERE id=?',(json.dumps(self.plan),self.original_id))
            plan_set=dict(kind='joint',run_id='0',mode='free',week_start=self.start,plans=[self.plan],configuration_hash=self.app.workouts.configuration_hash(self.profile),state_hash=self.app.joint.state_hash(db,self.user,self.profile,self.start))
            self.set_id=db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,0,?,?)',(self.user,json.dumps(plan_set),'{}')).lastrowid
        response=self.client.post('/api/plan-sets/'+str(self.set_id)+'/apply',json=dict(plan_id=self.original_id,scope='week'),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        with self.app.connect() as db:
            self.original_exposures={r['date']:dict(r) for r in db.execute('SELECT * FROM bandit_exposure WHERE user_id=?',(self.user,))}
        self.assertEqual(len(self.original_exposures),7)
        self.client.post('/api/plans/'+str(self.original_id)+'/feedback',json=dict(rating=4,tried=True),headers=self.headers)
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db,self.user,self.profile,'confirm',dict(date=self.start,slot='breakfast'))
        self.add_surplus()

    def add_surplus(self):
        with self.app.connect() as db:self.app.diary.diary_mutation(db,self.user,self.profile,'add',dict(date=self.start,slot='breakfast',food=dict(source='CREA',id='000800'),grams=100))

    def rebalance(self,token,action='apply'):
        proposal=self.proposal(dict(date=self.start,from_diary=True))
        self.assertIn(proposal['result']['status'],('full','partial'),proposal['result'])
        self.app.rebalance_previews[token]=proposal
        response=self.client.post('/api/rebalance/'+token+'/'+action,json={},headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return proposal['result'],response.json()

    def test_week_applied_then_rebalanced_days_remain_evaluable_with_same_vote(self):
        with self.app.connect() as db:
            vote=dict(db.execute('SELECT * FROM plan_feedback WHERE user_id=?',(self.user,)).fetchone())
            original_payload=db.execute('SELECT payload FROM plans WHERE id=?',(self.original_id,)).fetchone()[0]
        result,answer=self.rebalance('same-plan')
        self.assertTrue(answer['changed_days']);self.assertTrue(answer['evaluation_revisions'])
        for date in answer['changed_days']:
            view=self.client.get('/api/day?date='+date).json()
            self.assertEqual(view['plan_id'],self.original_id);self.assertEqual(view['rating'],4)
            self.assertEqual(view['plan_evaluation']['status'],'available')
            ref=view['plan_evaluation']['plans'][0];self.assertEqual(ref['rebalance_count'],1)
            self.assertIsNotNone(ref['last_rebalanced_at'])
            self.assertEqual(ref['applied_at'],self.original_exposures[date]['created'])
            with self.app.connect() as db:
                row=dict(db.execute('SELECT * FROM bandit_exposure WHERE user_id=? AND date=?',(self.user,date)).fetchone());snapshot=json.loads(row['snapshot'])
                self.assertEqual(snapshot['original_application']['meals'],json.loads(self.original_exposures[date]['snapshot'])['meals'])
                self.assertEqual(row['context'],self.original_exposures[date]['context'])
                for meal in snapshot['meals']:
                    current=self.app.diary.planned(db,self.user,date,meal['slot'])
                    self.assertEqual(meal['items'],json.loads(current['items']))
                    self.assertEqual(meal['nutrients'],self.app.diary.totals(self.app.diary.enriched(meal['items'],self.profile)))
                    self.assertEqual(current['role'],'varied')
        with self.app.connect() as db:
            self.assertEqual(vote,dict(db.execute('SELECT * FROM plan_feedback WHERE user_id=?',(self.user,)).fetchone()))
            self.assertEqual(original_payload,db.execute('SELECT payload FROM plans WHERE id=?',(self.original_id,)).fetchone()[0])
            self.assertEqual(db.execute('SELECT count(*) FROM bandit_exposure WHERE user_id=?',(self.user,)).fetchone()[0],7)
        self.assertEqual(self.client.get('/api/bandit/summary').json()['eligible_days'],0)

    def test_two_rebalances_preserve_original_reference_without_duplicate_trials(self):
        self.rebalance('first-revision');self.add_surplus();_,answer=self.rebalance('second-revision')
        for date in answer['changed_days']:
            view=self.client.get('/api/day?date='+date).json()
            self.assertEqual(view['plan_id'],self.original_id);self.assertEqual(view['rating'],4)
            self.assertEqual(view['plan_evaluation']['plans'][0]['rebalance_count'],2)
            with self.app.connect() as db:
                snapshot=json.loads(db.execute('SELECT snapshot FROM bandit_exposure WHERE user_id=? AND date=?',(self.user,date)).fetchone()[0])
                self.assertEqual(snapshot['original_application']['meals'],json.loads(self.original_exposures[date]['snapshot'])['meals'])
                self.assertEqual([e['preview_id'] for e in snapshot['rebalance_history']],['first-revision','second-revision'])
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM bandit_exposure WHERE user_id=?',(self.user,)).fetchone()[0],7)

    def test_revised_nutrients_are_used_only_after_actual_trial_and_new_feedback(self):
        _,answer=self.rebalance('trial-revision');date=answer['changed_days'][0]
        future=dt.date.fromisoformat(date);timestamp=dt.datetime.combine(future,dt.time(18),ZoneInfo('Europe/Rome')).timestamp()
        with self.app.connect() as db:username=db.execute('SELECT username FROM users WHERE id=?',(self.user,)).fetchone()[0]
        with patch.object(self.app.diary,'local_today',return_value=future),patch('contextual_bandit.time.time',return_value=timestamp):
            # The session expires overnight: log in on the simulated trial day.
            login=self.client.post('/api/login',json=dict(username=username,password='test-password-123'))
            self.assertEqual(login.status_code,200,login.text)
            self.headers={'X-CSRF-Token':self.client.get('/api/profile').json()['csrf']}
            for slot in self.app.diary.SLOTS:
                response=self.client.post('/api/diary/confirm',json=dict(date=date,slot=slot),headers=self.headers)
                self.assertEqual(response.status_code,200,response.text)
            pending=self.client.get('/api/bandit/summary').json()
            trial=next(t for t in pending['trials'] if t['date']==date)
            self.assertIsNone(trial['reward']);self.assertIn('aggiornamento',trial['reason'])
            response=self.client.post('/api/plans/'+str(self.original_id)+'/feedback',json=dict(rating=5,tried=True),headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            summary=self.client.get('/api/bandit/summary').json();trial=next(t for t in summary['trials'] if t['date']==date)
            self.assertEqual(trial['status'],'eligible');self.assertAlmostEqual(trial['adherence'],1);self.assertAlmostEqual(trial['reward'],1)
            self.assertEqual(summary['eligible_days'],1)
            self.assertEqual(self.client.get('/api/day?date='+date).json()['plan_id'],self.original_id)

    def test_true_replacements_and_foreign_plans_are_not_revived(self):
        date='2026-10-06'
        with self.app.connect() as db:
            row=self.app.diary.planned(db,self.user,date,'lunch');items=json.loads(row['items']);items[0]['grams']+=5
            db.execute('UPDATE planned_meal SET items=? WHERE id=?',(json.dumps(items),row['id']))
        self.rebalance('already-replaced')
        view=self.client.get('/api/day?date='+date).json()
        self.assertIsNone(view['plan_id']);self.assertEqual(view['plan_evaluation']['status'],'unavailable')
        self.add_surplus()
        with self.app.connect() as db:
            db.execute('UPDATE plans SET user_id=? WHERE id=?',(self.user+10000,self.original_id))
            before=[dict(r) for r in db.execute('SELECT * FROM bandit_exposure WHERE user_id=?',(self.user,))]
        _,answer=self.rebalance('foreign-reference')
        self.assertEqual(answer['evaluation_revisions'],[])
        with self.app.connect() as db:self.assertEqual(before,[dict(r) for r in db.execute('SELECT * FROM bandit_exposure WHERE user_id=?',(self.user,))])
        self.assertEqual(self.client.get('/api/day?date='+date).json()['plan_evaluation']['plans'],[])

    def test_keep_preserves_all_application_snapshots(self):
        with self.app.connect() as db:before=[dict(r) for r in db.execute('SELECT * FROM bandit_exposure WHERE user_id=?',(self.user,))]
        _,answer=self.rebalance('keep-reference','keep');self.assertEqual(answer['evaluation_revisions'],[])
        with self.app.connect() as db:self.assertEqual(before,[dict(r) for r in db.execute('SELECT * FROM bandit_exposure WHERE user_id=?',(self.user,))])

    def test_substitutions_revise_food_features_but_keep_plan_and_context(self):
        date='2026-10-06';day=copy.deepcopy(self.plan['days'][1]);day['role']='varied'
        for selection in day['selections']:
            if selection['meal'] in ('lunch','dinner') and selection['food_id']=='000800':selection['food_id']='000100'
        with self.app.connect() as db:
            captured=bandit.capture_rebalance_applications(db,self.user,{date});applied=[]
            for slot in ('lunch','dinner'):
                result=self.app.diary.apply_plan(db,self.user,self.profile,dict(week_start=self.start),dict(day,id=self.original_id),dict(plan_id=self.original_id,scope='meal',date=date,slot=slot));applied.extend(result['applied_slots'])
            bandit.revise_rebalance_applications(db,self.user,self.profile,captured,[day],applied,'substitution')
            row=db.execute('SELECT * FROM bandit_exposure WHERE user_id=? AND date=?',(self.user,date)).fetchone()
            self.assertEqual(row['plan_id'],self.original_id);self.assertEqual(row['context'],self.original_exposures[date]['context'])
            features=json.loads(row['arms']);self.assertIn('starch:rice',features);self.assertNotIn('starch:pasta',features)
        self.assertEqual(self.client.get('/api/day?date='+date).json()['plan_id'],self.original_id)


for name in tuple(vars(base.RebalanceAPI)):
    if name.startswith('test_'):setattr(RebalanceEvaluation,name,None)

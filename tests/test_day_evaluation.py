import copy
import datetime as dt
import json
from unittest.mock import patch
import test_contextual_bandit as base
import contextual_bandit as bandit


class DayEvaluation(base.ContextualBandit):
    def view(self):
        response=self.client.get('/api/day?date='+self.date)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_applied_plan_reference_and_existing_vote_are_visible(self):
        self.apply();view=self.view()
        self.assertEqual(view['plan_id'],self.plan['id']);self.assertIsNone(view['rating'])
        ref=view['plan_evaluation']['plans'][0]
        self.assertEqual(ref['slots'],['lunch']);self.assertTrue(ref['feedback_available']);self.assertEqual(ref['rating_scope'],'plan')
        self.assertEqual(self.client.get('/api/bandit/summary').json()['eligible_days'],0)
        response=self.client.post('/api/diary/confirm',json=dict(date=self.date,slot='lunch'),headers=self.headers)
        self.assertEqual(response.json()['plan_id'],self.plan['id'])
        self.assertEqual(self.feedback(4).status_code,200)
        view=self.view();self.assertEqual(view['rating'],4);self.assertEqual(view['plan_evaluation']['plans'][0]['rating'],4)
        self.assertIsNotNone(view['plan_evaluation']['plans'][0]['rated_at'])
        self.assertEqual(self.client.get('/api/bandit/summary').json()['eligible_days'],1)
        self.assertEqual(self.feedback(2).status_code,200);self.assertEqual(self.view()['rating'],2)
        self.assertEqual(self.client.get('/api/bandit/summary').json()['eligible_days'],1)

    def test_generated_or_selected_plan_is_not_an_applied_reference(self):
        self.client.post('/api/plans/'+str(self.plan['id'])+'/select',json={},headers=self.headers)
        self.feedback(3)
        view=self.view();self.assertIsNone(view['plan_id']);self.assertIsNone(view['rating'])
        self.assertEqual(view['plan_evaluation']['status'],'unavailable');self.assertTrue(view['plan_evaluation']['reason'])

    def test_replaced_plan_is_not_evaluable_and_other_owners_are_invisible(self):
        self.apply();self.feedback(5)
        # Applying on Tuesday can create the Monday-based active week; the
        # original fixture's meal id may belong to a different week.
        active_meal=next(m['planned']['planned_meal_id'] for m in self.view()['meals'] if m['slot']=='lunch')
        with self.app.connect() as db:
            db.execute('UPDATE planned_meal SET items=? WHERE id=?',(json.dumps([dict(food=dict(source='CREA',id='000800'),grams=100,units=None)]),active_meal))
        view=self.view();self.assertIsNone(view['plan_id']);self.assertEqual(view['plan_evaluation']['plans'],[])
        self.assertIn('sostituito',view['plan_evaluation']['reason'])
        with self.app.connect() as db:
            row=db.execute('SELECT * FROM bandit_exposure WHERE user_id=?',(self.user,)).fetchone();snapshot=json.loads(row['snapshot'])
            snapshot['meals'][0]['items']=[dict(food=dict(source='CREA',id='000800'),grams=100,units=None)]
            # Even a matching forged application cannot expose a foreign plan or vote.
            db.execute('UPDATE bandit_exposure SET snapshot=? WHERE user_id=?',(json.dumps(snapshot),self.user))
            db.execute('UPDATE plans SET user_id=? WHERE id=?',(self.user+10000,self.plan['id']))
        self.assertEqual(self.view()['plan_evaluation']['plans'],[])

    def test_mixed_plan_references_do_not_pick_an_arbitrary_day_vote(self):
        self.apply()
        with self.app.connect() as db:
            second=copy.deepcopy(self.plan);second['selections'][0]['meal']='dinner'
            second['id']=db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,0,?)',(self.user,json.dumps(second))).lastrowid
            result=self.app.diary.apply_plan(db,self.user,self.profile,dict(run_id='0',mode='free'),second,dict(plan_id=second['id'],scope='meal',date=self.date,slot='dinner'))
            bandit.record_application(db,self.user,self.profile,second,result)
            db.execute('INSERT INTO plan_feedback VALUES(?,?,?,?)',(self.user,second['id'],2,__import__('time').time()))
        view=self.view();self.assertIsNone(view['plan_id']);self.assertIsNone(view['rating'])
        self.assertEqual(view['plan_evaluation']['status'],'multiple')
        refs={r['plan_id']:r for r in view['plan_evaluation']['plans']}
        self.assertEqual(refs[self.plan['id']]['slots'],['lunch']);self.assertEqual(refs[second['id']]['slots'],['dinner'])
        self.assertEqual(refs[second['id']]['rating'],2)

    def test_future_day_exposes_reference_but_does_not_ask_for_feedback(self):
        self.apply()
        yesterday=dt.date.fromisoformat(self.date)-dt.timedelta(days=1)
        with patch.object(self.app.diary,'local_today',return_value=yesterday):view=self.view()
        self.assertEqual(view['plan_id'],self.plan['id'])
        ref=view['plan_evaluation']['plans'][0];self.assertFalse(ref['feedback_available']);self.assertIn('futura',ref['reason'])

    def test_weekly_vote_is_explicitly_shared_by_plan_not_fabricated_per_day(self):
        self.apply()
        tomorrow=(dt.date.fromisoformat(self.date)+dt.timedelta(days=1)).isoformat()
        with self.app.connect() as db:
            result=self.app.diary.apply_plan(db,self.user,self.profile,dict(run_id='0',mode='free'),self.plan,dict(plan_id=self.plan['id'],scope='meal',date=tomorrow,slot='lunch'))
            bandit.record_application(db,self.user,self.profile,self.plan,result)
        self.feedback(4)
        other=self.client.get('/api/day?date='+tomorrow).json()
        self.assertEqual(other['rating'],4);self.assertEqual(other['plan_id'],self.plan['id'])
        self.assertEqual(other['plan_evaluation']['plans'][0]['rating_scope'],'plan')


for name in tuple(vars(base.ContextualBandit)):
    if name.startswith('test_'):setattr(DayEvaluation,name,None)

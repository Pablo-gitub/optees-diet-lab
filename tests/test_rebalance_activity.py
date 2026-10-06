import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch
from test_meal_rebalance import RebalanceAPI
import meal_rebalance as rebalance
import rebalance_activity

class RebalanceActivityTests(RebalanceAPI):
    def setUp(self):
        super().setUp();self.profile['_filtered_weight_kg']=80
    def test_activity_opt_in_caps_and_atomic_application(self):
        meal=dict(self.meal,activity=dict(mode='walk',max_minutes_per_day=45))
        proposal=self.proposal(meal);result=proposal['result']
        self.assertIn(result['status'],('full','partial'),result)
        self.assertGreater(result['budget']['correction_activity_kcal'],0,result)
        self.assertLessEqual(result['budget']['correction_activity_kcal'],result['budget']['correction_diet_kcal']+.001)
        self.assertAlmostEqual(result['budget']['correction_kcal'],result['budget']['correction_diet_kcal']+result['budget']['correction_activity_kcal'],places=2)
        for day in result['days']:
            self.assertLessEqual(len(day['activities']),1)
            for activity in day['activities']:self.assertLessEqual(activity['minutes'],45)
            self.assertGreaterEqual(day['after_kcal']-sum(a['energy_kcal']['low'] for a in day['activities']),1400-.001)
        with self.app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM planned_session WHERE week_plan_id IN (SELECT id FROM week_plan WHERE user_id='+str(self.user)+')').fetchone()[0],0)
            rebalance.decide(db,self.user,self.profile,'activity-apply',proposal,'apply')
            rows=db.execute('SELECT * FROM planned_session WHERE week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?)',(self.user,)).fetchall();self.assertTrue(rows)
            for row in rows:
                session=json.loads(row['snapshot']);self.assertEqual(session['kind'],'activity');self.assertEqual(row['status'],'chosen');self.assertIn('rebalance_credit_kcal',session['energy_estimate'])
            self.assertRaises(self.app.diary.DomainError,rebalance.decide,db,self.user,self.profile,'activity-apply',proposal,'apply')
    def test_activity_keep_none_missing_weight_and_intense(self):
        self.assertFalse(self.proposal()['result'].get('_activity_sessions'))
        with self.app.connect() as db:snap=rebalance.snapshot(db,self.user,self.profile,self.meal)
        self.assertTrue(rebalance_activity.intense(dict(workouts=[dict(kind='workout',status='chosen')])))
        self.assertFalse(rebalance_activity.intense(dict(workouts=[dict(kind='workout',status='skipped')])))
        profile=copy.deepcopy(self.profile);profile.pop('_filtered_weight_kg')
        problem={'variables':[],'constraints':[],'objective':{'coefficients':[]}}
        rows={v['date']:[] for v in snap['views'][1:]};baseline={date:2000 for date in rows}
        choices,reasons=rebalance_activity.add(problem,snap['views'][1:],profile,dict(mode='walk',max_minutes_per_day=45),rows,baseline,1000,{date:1900 for date in rows})
        self.assertFalse(choices);self.assertTrue(reasons)
        proposal=self.proposal(dict(self.meal,activity=dict(mode='walk',max_minutes_per_day=45)))
        with self.app.connect() as db:
            before='\n'.join(db.iterdump());answer=rebalance.decide(db,self.user,self.profile,'activity-keep',proposal,'keep')
            self.assertFalse(answer['changed_days']);self.assertEqual(db.execute('SELECT count(*) FROM planned_session WHERE week_plan_id IN (SELECT id FROM week_plan WHERE user_id='+str(self.user)+')').fetchone()[0],0)
    def test_activity_validation_and_skipped_credit_once(self):
        parsed=rebalance.diary_request(dict(date=self.start,from_diary=True,activity=dict(mode='liked',max_minutes_per_day=20)),self.today)
        self.assertEqual(parsed['activity']['mode'],'liked')
        for value in ({'mode':'gym'},{'mode':'walk','max_minutes_per_day':50},{'mode':'walk','max_minutes_per_day':True}):self.assertRaises(self.app.diary.DomainError,rebalance_activity.validate,value)
        snap=dict(views=[dict(date=self.start,meals=[],workouts=[dict(kind='activity',status='skipped',planned_session_id=1,energy_estimate=dict(status='available',source='test',energy_kcal=dict(low=40,central=60,high=80),rebalance_credit_kcal=40))])],previous_correction=100)
        recorded,excess,_,reason,_=rebalance.deviations(dict(date=self.start,from_diary=True),snap)
        self.assertIsNone(reason);self.assertEqual(excess,dict(min=-60,max=-60))

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(RebalanceActivityTests(n) for n in RebalanceActivityTests.__dict__ if n.startswith('test_activity_'))

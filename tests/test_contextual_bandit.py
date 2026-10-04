import copy
import datetime as dt
import json
from unittest.mock import patch
import test_diary_service as base
import contextual_bandit as bandit
from day_orchestration import arms,context_key,exploration_score


class ContextualBandit(base.DiaryTests):
    def setUp(self):
        super().setUp()
        selection=dict(meal='lunch',food_id='000800',food='Pasta',grams=80,source='CREA')
        key=bandit.context('free','rest',self.profile['targets'],'lunch_and_dinner_only')
        self.plan=dict(status='optimal',mode='free',day_index=0,day_type='rest',scope='lunch_and_dinner_only',selections=[selection],arms=arms(dict(selections=[selection])),bandit_context=key,targets=self.profile['targets'],optimization=dict(context=key))
        with self.app.connect() as db:
            self.plan['id']=db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,0,?)',(self.user,json.dumps(self.plan))).lastrowid
            self.set_id=db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,0,?,?)',(self.user,json.dumps(dict(run_id='0',mode='free',plans=[self.plan])), '{}')).lastrowid
    def feedback(self,rating=5):return self.client.post('/api/plans/'+str(self.plan['id'])+'/feedback',json=dict(rating=rating,tried=True),headers=self.headers)
    def apply(self):
        response=self.client.post('/api/plan-sets/'+str(self.set_id)+'/apply',json=dict(plan_id=self.plan['id'],scope='meal',date=self.date,slot='lunch'),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
    def test_generate_select_or_vote_without_actual_trial_never_learns(self):
        self.assertEqual(self.client.get('/api/bandit/summary').json()['eligible_days'],0)
        self.assertEqual(self.client.post('/api/plans/'+str(self.plan['id'])+'/select',json={},headers=self.headers).status_code,200)
        response=self.feedback();self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/bandit/summary').json()['contexts'],{})
        self.apply()
        self.assertEqual(self.client.get('/api/bandit/summary').json()['eligible_days'],0)
        self.client.post('/api/diary/confirm',json=dict(date=self.date,slot='lunch'),headers=self.headers)
        # A declaration made before applying must be renewed.
        self.assertEqual(self.client.get('/api/bandit/summary').json()['eligible_days'],0)
        response=self.feedback();self.assertEqual(response.json()['learning']['status'],'eligible')
        summary=self.client.get('/api/bandit/summary').json();self.assertEqual(summary['eligible_days'],1)
        self.assertEqual(summary['trials'][0]['reward'],1)
        self.feedback(3);again=self.client.get('/api/bandit/summary').json()
        self.assertEqual(again['eligible_days'],1);self.assertEqual(again['trials'][0]['reward'],.75)
    def test_reward_combines_vote_with_measured_adherence_and_missing_is_not_zero(self):
        self.apply();self.feedback()
        pending=self.client.get('/api/bandit/summary').json()['trials'][0]
        self.assertEqual(pending['status'],'insufficient_data');self.assertIsNone(pending['reward']);self.assertIsNone(pending['adherence'])
        response=self.client.post('/api/diary/entries',json=dict(date=self.date,slot='lunch',food=dict(source='CREA',id='000800'),grams=40),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        value=self.client.get('/api/bandit/summary').json()['trials'][0]
        self.assertAlmostEqual(value['adherence'],.5,delta=.01);self.assertAlmostEqual(value['reward'],.75,delta=.01)
        with self.app.connect() as db:
            db.execute('INSERT INTO consumed_estimate VALUES(?,?,?,?,0)',(self.user,self.date,'lunch',json.dumps(dict(nutrients=dict(kcal=dict(min=100,max=200))))))
            self.assertEqual(bandit.observations(db,self.user,self.profile),{})
    def test_all_skipped_is_not_an_effectively_tried_plan(self):
        self.apply();self.client.post('/api/diary/skip',json=dict(date=self.date,slot='lunch'),headers=self.headers);self.feedback()
        result=self.client.get('/api/bandit/summary').json();self.assertEqual(result['eligible_days'],0);self.assertIn('non effettivamente',result['trials'][0]['reason'])
    def test_training_rest_and_target_versions_are_separate(self):
        config=self.app.make_config(self.profile,0);rest=context_key(dict(config,day_type='rest'));training=context_key(dict(config,day_type='training'))
        self.assertNotEqual(rest,training)
        changed=copy.deepcopy(config);changed['main_meals_targets']['kcal_100g']['target']+=5
        self.assertNotEqual(context_key(changed),rest)
        candidate=dict(arms=['starch:pasta'],bandit_features=[dict(context=rest,arms=['starch:pasta'])])
        observed={training:[('starch:pasta',1)]}
        self.assertEqual(bandit.rewards(candidate,observed),[])
        self.assertEqual(exploration_score(candidate,observed)[0],1)
        observed[rest]=[('starch:pasta',.5)]
        self.assertEqual(bandit.rewards(candidate,observed),[.5]);self.assertEqual(exploration_score(candidate,observed)[0],0)
        # Repeated days do not multiply the same historical trial.
        candidate['bandit_features']*=7
        self.assertEqual(bandit.rewards(candidate,observed),[.5])
    def test_recorded_training_is_required_for_joint_reward(self):
        self.apply()
        with self.app.connect() as db:
            row=db.execute('SELECT * FROM bandit_exposure WHERE user_id=?',(self.user,)).fetchone();snap=json.loads(row['snapshot'])
            week=db.execute('SELECT id FROM week_plan WHERE user_id=?',(self.user,)).fetchone()[0]
            session=self.app.workouts.session_by_id(self.profile,'continuous_stationary-bike')
            sid=db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,status,snapshot) VALUES(?,?,'continuous_stationary-bike','chosen',?)",(week,self.date,json.dumps(session))).lastrowid
            snap['workout_ids']=[sid];snap['day_type']='training'
            db.execute('UPDATE bandit_exposure SET snapshot=? WHERE user_id=?',(json.dumps(snap),self.user))
        self.client.post('/api/diary/confirm',json=dict(date=self.date,slot='lunch'),headers=self.headers);self.feedback()
        self.assertEqual(self.client.get('/api/bandit/summary').json()['eligible_days'],0)
        with self.app.connect() as db:
            db.execute("UPDATE planned_session SET status='skipped' WHERE id=?",(sid,))
        result=self.client.get('/api/bandit/summary').json()['trials'][0]
        self.assertEqual(result['adherence'],.5);self.assertEqual(result['reward'],.75)
        with self.app.connect() as db:
            db.execute("UPDATE planned_session SET status='done' WHERE id=?",(sid,))
            db.execute('INSERT INTO workout_log(user_id,date,planned_session_id,session_id,ended,snapshot) VALUES(?,?,?,?,?,?)',(self.user,self.date,sid,'continuous_stationary-bike',__import__('time').time(),json.dumps(session)))
        self.assertEqual(self.client.get('/api/bandit/summary').json()['trials'][0]['reward'],1)
    def test_week_solver_ignores_rewards_from_an_unrelated_context(self):
        import asyncio
        from test_week_orchestration import WeekOrchestrationTests,make_config
        from week_orchestration import generate_week
        from plan_diet_day import load_foods
        from test_recipe_solver import solve
        profile=WeekOrchestrationTests().profile();request=dict(week_start=self.date,k=4,pool_size=4)
        other=context_key(dict(make_config(profile,0),day_type='training'))
        async def fake(session,problem):return solve(problem)
        with patch('plan_diet_day.solve_problem',side_effect=fake):
            result=asyncio.run(generate_week(None,profile,request,make_config,load_foods(),observations={other:[('starch:pasta',1)]}))
        self.assertTrue(result['plans']);self.assertNotIn('preferred',[p['role'] for p in result['plans']])
        for plan in result['plans']:
            self.assertTrue(plan['bandit_features']);self.assertTrue(all(f['context']!=other for f in plan['bandit_features']))

    def test_only_observed_features_are_recorded(self):
        with self.app.connect() as db:
            week=db.execute('SELECT id FROM week_plan WHERE user_id=?',(self.user,)).fetchone()[0]
            db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status) VALUES(?,?,'breakfast',?,'best','chosen')",(week,self.date,json.dumps([dict(food=dict(source='CREA',id='007510'),grams=100)])))
            breakfast=dict(self.plan,selections=[dict(meal='breakfast',food_id='007510',grams=100)])
            bandit.record_application(db,self.user,self.profile,breakfast,dict(applied_slots=[dict(date=self.date,slot='breakfast')]))
            self.assertEqual(db.execute('SELECT count(*) FROM bandit_exposure WHERE user_id=?',(self.user,)).fetchone()[0],0)

    def test_owner_scope_and_csrf(self):
        self.assertEqual(self.client.post('/api/plans/'+str(self.plan['id'])+'/feedback',json=dict(rating=5,tried=True)).status_code,403)
        self.apply();self.client.post('/api/diary/confirm',json=dict(date=self.date,slot='lunch'),headers=self.headers);self.feedback()
        with self.app.connect() as db:
            self.assertEqual(bandit.observations(db,self.user+10000,self.profile),{})

for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(ContextualBandit,name,None)

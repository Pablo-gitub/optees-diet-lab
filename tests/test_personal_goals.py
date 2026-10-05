import datetime as dt
import json
from unittest.mock import patch
import test_diary_service as base
import personal_goals as goals

class PersonalGoals(base.DiaryTests):
    def put(self,block,data):return self.client.put('/api/goals/'+block,json=data,headers=self.headers)
    def weights(self):
        with self.app.connect() as db:
            for i,value in enumerate((80,80,83)):
                date=(self.app.diary.local_today()-dt.timedelta(days=2-i)).isoformat()
                self.app.diary.add_measurement(db,self.user,dict(date=date,kind='weight',value=value,unit='kg'))
    def proposal(self):return self.client.post('/api/goals/energy-proposal',json={},headers=self.headers)
    def test_skippable_blocks_profile_preservation_and_validation(self):
        initial=self.client.get('/api/goals').json();self.assertTrue(initial['missing'])
        self.assertEqual(self.put('body',{}).status_code,200)
        self.assertEqual(self.put('activity',dict(gym='no',preferred_stores=['Conad','Coop'],max_session_minutes=90)).status_code,200)
        self.assertEqual(self.put('training',dict(priorities=dict(strength=3,hypertrophy=3,health=3))).status_code,200)
        response=self.client.put('/api/profile',json=dict(display_name='test'),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        saved=self.client.get('/api/profile').json()['profile']['goals'];self.assertEqual(saved['activity']['preferred_stores'],['Conad','Coop'])
        for block,data in [('body',dict(target_weight_kg=True)),('body',dict(target_date=self.date)),('body',dict(pace='moderate',pace_pct_per_week=.2)),('activity',dict(max_session_minutes=19)),('activity',dict(max_sessions_per_day=3)),('training',dict(priorities={k:3 for k in goals.TRAINING[:4]})),('training',dict(priorities={'unknown':1}))]:
            self.assertEqual(self.put(block,data).status_code,400)
        self.assertEqual(self.client.put('/api/goals/body',json={}).status_code,403)
    def test_anchors_and_manual_loads_and_new_circumferences(self):
        anchor=dict(exercise_key='dumbbell-deadlift',heavy=dict(kg=20,reps=3,date=self.date),light=dict(kg=10,reps=12,date=self.date))
        self.assertEqual(self.put('strength-anchors',dict(anchors=[anchor])).status_code,200)
        with self.app.connect() as db:
            db.execute('INSERT INTO workout_configuration(user_id,settings,updated) VALUES(?,?,?)',(self.user,json.dumps(dict(available_loads_kg=[10,20],starting_loads_kg={'dumbbell-deadlift':10})),'now'))
            settings=self.app.workout_settings.read(db,self.user)
        self.assertEqual(settings['strength_anchors'],[anchor]);self.assertEqual(settings['starting_loads_kg']['dumbbell-deadlift'],10)
        for key,reps in [('heavy',1),('heavy',7),('light',9),('light',16)]:
            bad=json.loads(json.dumps(anchor));bad[key]['reps']=reps
            self.assertEqual(self.put('strength-anchors',dict(anchors=[bad])).status_code,400)
        for kind in ('hip','chest','arm','thigh'):
            for value,status in [(10,200),(300,200),(9,400),(301,400)]:
                response=self.client.post('/api/measurements',json=dict(date=self.date,kind=kind,value=value,unit='cm'),headers=self.headers);self.assertEqual(response.status_code,status,response.text)
    def test_proposal_filtered_weight_explicit_approval_and_conflict(self):
        self.weights();self.put('body',dict(target_weight_kg=75,pace='moderate'))
        response=self.proposal();self.assertEqual(response.status_code,200,response.text);p=response.json()['proposal']
        self.assertNotEqual(p['weight']['value_kg'],83);self.assertGreater(p['weight']['value_kg'],80)
        self.assertGreaterEqual(p['proposed_kcal'],-1000);self.assertLessEqual(p['proposed_kcal'],1000)
        self.assertIsNone(self.client.get('/api/profile').json()['profile'].get('energy_balance_target_kcal'))
        path='/api/goals/energy-proposal/'+str(p['id'])
        self.put('activity',dict(gym='no'))
        self.assertEqual(self.client.post(path+'/approve',json=dict(state_token=p['state_token']),headers=self.headers).status_code,409)
        p=self.proposal().json()['proposal'];path='/api/goals/energy-proposal/'+str(p['id'])
        result=self.client.post(path+'/approve',json=dict(state_token=p['state_token']),headers=self.headers)
        self.assertEqual(result.status_code,200,result.text);self.assertEqual(self.client.get('/api/profile').json()['profile']['energy_balance_target_kcal'],p['proposed_kcal'])
        self.assertEqual(self.client.post(path+'/approve',json=dict(state_token=p['state_token']),headers=self.headers).status_code,409)
        self.assertEqual(self.proposal().json()['status'],'insufficient_data')
    def test_missing_weight_rejection_gain_limits_and_existing_balance_cap(self):
        self.put('body',dict(target_weight_kg=90,pace='gentle'))
        self.assertEqual(self.proposal().json()['status'],'insufficient_data')
        self.weights()
        self.assertEqual(self.put('body',dict(target_weight_kg=90,pace='custom',pace_pct_per_week=.75)).status_code,400)
        self.client.put('/api/profile',json=dict(energy_balance_target_kcal=0),headers=self.headers)
        p=self.proposal().json()['proposal'];self.assertLessEqual(abs(p['proposed_kcal']),90)
        path='/api/goals/energy-proposal/'+str(p['id'])+'/reject'
        self.assertEqual(self.client.post(path,json=dict(state_token=p['state_token']),headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/api/profile').json()['profile']['energy_balance_target_kcal'],0)
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT state FROM goal_energy_proposal WHERE id=?',(p['id'],)).fetchone()[0],'rejected')

for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(PersonalGoals,name,None)

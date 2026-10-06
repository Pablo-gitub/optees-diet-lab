import copy
import json
from contextlib import asynccontextmanager
from unittest.mock import patch
import test_diary_service as base

class MoreAlternatives(base.DiaryTests):
    def seed(self):
        config=self.app.make_config(self.profile,0)
        plan=dict(role='best',selections=[dict(meal='lunch',food_id='000800',grams=100)],nutrients={})
        with self.app.connect() as db:
            plan['id']=db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,0,?)',(self.user,json.dumps(plan))).lastrowid
            payload=dict(run_id='test',mode='free',plans=[plan],pool={})
            return db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,0,?,?)',(self.user,json.dumps(payload),json.dumps(dict(config=config,profile={k:v for k,v in self.profile.items() if k!='daily_meals'},request={})))).lastrowid
    def stubs(self):
        @asynccontextmanager
        async def stream(*args,**kwargs):yield None,None
        class Session:
            def __init__(self,*args):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def initialize(self):pass
        return stream,Session
    def test_extension_same_pool_all_seeds_atomic_no_diary_changes_and_csrf(self):
        identifier=self.seed();seen=[]
        async def generate(session,config,foods,data):
            seen.append(copy.deepcopy(data['_existing_plans']))
            return dict(plans=[dict(role='explore',selections=[dict(meal='lunch',food_id='106500',grams=100)],nutrients={},overlap_pct=0)],pool=dict(overlap_target=10,overlap_achieved=0))
        stream,session=self.stubs();url=f'/api/plan-sets/{identifier}/alternatives'
        self.assertEqual(self.client.post(url,json={}).status_code,403)
        with self.app.connect() as db:before=[dict(r) for r in db.execute('SELECT * FROM planned_meal')]
        with patch.object(self.app,'stdio_client',stream),patch.object(self.app,'ClientSession',session),patch.object(self.app,'orchestrate_day',side_effect=generate):
            response=self.client.post(url,json={},headers=self.headers)
        self.assertEqual(response.status_code,200,response.text);r=response.json();self.assertEqual(r['status'],'extended');self.assertEqual(r['plan_set_id'],identifier)
        self.assertEqual(len(seen[0]),1);self.assertEqual(len(r['plan_set']['plans']),2)
        self.assertEqual(self.client.get(f'/api/plan-sets/{identifier}').json(),r['plan_set'])
        with self.app.connect() as db:
            self.assertEqual([dict(r) for r in db.execute('SELECT * FROM planned_meal')],before)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM diary_entry WHERE user_id=?',(self.user,)).fetchone()[0],0)
    def test_changed_state_409_rolls_back_and_no_more_is_read_only(self):
        identifier=self.seed();stream,session=self.stubs();url=f'/api/plan-sets/{identifier}/alternatives'
        async def conflict(*args):
            with self.app.connect() as db:db.execute("UPDATE planned_meal SET locked=1 WHERE id=?",(self.meal,))
            return dict(plans=[dict(selections=[])],pool={})
        with self.app.connect() as db:old=db.execute('SELECT payload FROM plan_set WHERE id=?',(identifier,)).fetchone()[0];count=db.execute('SELECT COUNT(*) FROM plans').fetchone()[0]
        with patch.object(self.app,'stdio_client',stream),patch.object(self.app,'ClientSession',session),patch.object(self.app,'orchestrate_day',side_effect=conflict):
            self.assertEqual(self.client.post(url,json={},headers=self.headers).status_code,409)
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT payload FROM plan_set WHERE id=?',(identifier,)).fetchone()[0],old);self.assertEqual(db.execute('SELECT COUNT(*) FROM plans').fetchone()[0],count)
        async def empty(*args):return dict(plans=[],pool=dict(overlap_target=10))
        with patch.object(self.app,'stdio_client',stream),patch.object(self.app,'ClientSession',session),patch.object(self.app,'orchestrate_day',side_effect=empty):
            response=self.client.post(url,json={},headers=self.headers)
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['status'],'no_more_alternatives');self.assertFalse(response.json()['pool']['overlap_searches'][-1]['certified'])
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT payload FROM plan_set WHERE id=?',(identifier,)).fetchone()[0],old)
        self.assertEqual(self.client.post('/api/plan-sets/999999/alternatives',json={},headers=self.headers).status_code,404)

for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(MoreAlternatives,name,None)

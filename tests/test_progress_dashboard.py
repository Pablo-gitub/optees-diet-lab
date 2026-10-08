import json
import datetime as dt
from unittest.mock import patch
import progress_dashboard as dashboard
import test_diary_service as base

class DashboardTests(base.DiaryTests):
    def item(self,id='one',target=70,**changes):return dict(id=id,metric='weight_kg',target=target,comparison='at_most',state='pending',desired_date=None,window_weeks=1,**changes)
    def store(self,items,revision=0):
        return self.client.put('/api/progress/milestones',json=dict(revision=revision,items=items),headers=self.headers)
    def test_sequence_revision_csrf_and_no_implicit_profile_change(self):
        before=self.client.get('/api/profile').json()
        self.assertEqual(self.client.put('/api/progress/milestones',json=dict(revision=0,items=[])).status_code,403)
        response=self.store([self.item()]);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.store([self.item()]).status_code,409)
        self.assertEqual(self.client.get('/api/profile').json(),before)
        self.assertEqual(self.client.get('/api/progress/milestones').json()['active']['id'],'one')
    def test_early_reached_does_not_skip_and_deferral_persists(self):
        self.store([self.item(target=60),self.item('two',70)])
        today=self.app.diary.local_today()
        with self.app.connect() as db:
            for n in range(3):db.execute("INSERT INTO measurement(user_id,date,kind,value,unit,source) VALUES(?,?,'weight',69,'kg','manual')",(self.user,(today-dt.timedelta(days=n)).isoformat()))
        view=self.client.get('/api/progress/milestones').json();self.assertEqual(view['active']['id'],'one');second=view['rows'][1];self.assertTrue(second['prompt'])
        body=dict(revision=1,id='two',evidence_token=second['evidence']['token'],action='complete')
        self.assertEqual(self.client.post('/api/progress/milestones/decide',json=body,headers=self.headers).status_code,400)
        body['action']='later';self.assertEqual(self.client.post('/api/progress/milestones/decide',json=body,headers=self.headers).status_code,200)
        again=self.client.get('/api/progress/milestones').json();self.assertFalse(again['rows'][1]['prompt']);self.assertEqual(again['active']['id'],'one')
        body['action']='skip_previous';response=self.client.post('/api/progress/milestones/decide',json=body,headers=self.headers);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([i['state'] for i in response.json()['items']],['skipped','achieved']);self.assertIsNone(self.client.get('/api/progress/milestones').json()['active'])
    def test_stale_evidence_and_single_point(self):
        self.store([self.item()]);today=self.app.diary.local_today()
        with self.app.connect() as db:db.execute("INSERT INTO measurement(user_id,date,kind,value,unit,source) VALUES(?,?,'weight',69,'kg','manual')",(self.user,today.isoformat()))
        value=self.client.get('/api/progress/milestones').json();self.assertFalse(value['rows'][0]['evidence']['reached'])
        response=self.client.post('/api/progress/milestones/decide',json=dict(revision=1,id='one',evidence_token='wrong',action='complete'),headers=self.headers);self.assertEqual(response.status_code,409)
    def test_energy_partial_has_no_balance_and_health_is_not_added_twice(self):
        self.post('/api/diary/confirm');today=dt.date.fromisoformat(self.date)+dt.timedelta(days=2)
        report=dict(daily=[dict(date=self.date,total_estimated_kcal=2000,usable_for_baseline=True,resting_coverage_fraction=.95)])
        with self.app.connect() as db:
            value=dashboard.energy_view(db,self.user,self.profile,self.date,report,today)['days'][0]
        self.assertEqual(value['health_expenditure'],2000);self.assertIsNone(value['balance']);self.assertFalse(value['diary_complete']);self.assertIsNotNone(value['registered_intake'])
    def test_energy_snapshot_immutable_and_owner_scoped(self):
        with self.app.connect() as db:
            dashboard.capture(db,self.user,self.profile,self.date,'application')
            original=db.execute('SELECT payload FROM energy_snapshot WHERE user_id=?',(self.user,)).fetchone()[0]
            db.execute('UPDATE planned_meal SET items=? WHERE id=?',(json.dumps([dict(food=dict(source='CREA',id='000800'),grams=180)]),self.meal))
            dashboard.capture(db,self.user,self.profile,self.date,'application')
            rows=dashboard.energy_view(db,self.user,self.profile,dashboard.analysis.monday(dt.date.fromisoformat(self.date)).isoformat(),None,dt.date.fromisoformat(self.date))['versions'];self.assertEqual(len(rows),2)
            self.assertEqual(db.execute('SELECT payload FROM energy_snapshot WHERE user_id=? ORDER BY id LIMIT 1',(self.user,)).fetchone()[0],original)
            self.assertFalse(dashboard.energy_view(db,999,self.profile,self.date,None,dt.date.fromisoformat(self.date))['versions'])
    def test_solver_adapter_only_first_pending(self):
        sessions=self.item('sessions',3);sessions.update(metric='sessions_per_week',comparison='at_least')
        self.store([self.item(),sessions])
        with self.app.connect() as db:
            profile,data=dashboard.solver_adapter(db,self.user,self.profile,dict(sessions_min=1,sessions_max=5),'workout');self.assertEqual(data['sessions_min'],1)
        self.store([sessions,self.item()],revision=1)
        with self.app.connect() as db:
            profile,data=dashboard.solver_adapter(db,self.user,self.profile,dict(sessions_min=1,sessions_max=5),'workout');self.assertEqual(data['sessions_min'],3)
            with self.assertRaises(self.app.diary.DomainError):dashboard.solver_adapter(db,self.user,self.profile,dict(sessions_min=1,sessions_max=2),'workout')
    def test_projection_favorable_flat_opposite_and_insufficient(self):
        today=dt.date(2026,10,8)
        def points(slope):return [dict(date=(today-dt.timedelta(days=35-n*5)).isoformat(),kind='weight',unit='kg',source='manual',value=80+slope*n*5) for n in range(8)]
        item=self.item(target=75)
        self.assertEqual(dashboard.projection(item,points(-.03),today)['status'],'available')
        for slope in (0,.03):self.assertEqual(dashboard.projection(item,points(slope),today)['status'],'unavailable')
        self.assertEqual(dashboard.projection(item,points(-.03)[:2],today)['status'],'unavailable')
    def test_complete_energy_balance_preserves_interval_and_future_missing(self):
        date=self.date;profile=self.profile
        meals=[dict(state='modified',planned=dict(kcal=400),eaten=dict(kcal=400),eaten_range=None) for _ in range(5)]
        meals[0]['eaten_range']=dict(kcal=dict(min=300,max=500))
        view=dict(target_scope='full_day_planned_meals',meals=meals)
        report=dict(daily=[dict(date=date,total_estimated_kcal=2300,usable_for_baseline=True,resting_coverage_fraction=.95)])
        with self.app.connect() as db,patch.object(dashboard.diary,'day_view',return_value=view):
            result=dashboard.energy_days(db,self.user,profile,date,report,dt.date.fromisoformat(date)+dt.timedelta(days=1))[0]
            self.assertEqual(result['registered_intake'],dict(min=1900,max=2100));self.assertEqual(result['balance'],dict(min=-400,max=-200))
            future=dashboard.energy_days(db,self.user,profile,date,report,dt.date.fromisoformat(date)-dt.timedelta(days=1))[0]
            self.assertIsNone(future['registered_intake']);self.assertIsNone(future['health_expenditure']);self.assertIsNone(future['balance'])
    def test_sequence_edit_invalidates_review_state_and_completed_history(self):
        import planning_review
        with self.app.connect() as db:before=planning_review.state(db,self.user,self.date)
        self.store([self.item()])
        with self.app.connect() as db:self.assertNotEqual(before,planning_review.state(db,self.user,self.date))
        items=[self.item()];items[0]['state']='achieved'
        self.assertEqual(self.store(items,revision=1).status_code,400)
        with self.app.connect() as db:
            self.assertIsNone(dashboard.milestones_view(db,999,self.profile,[],self.app.diary.local_today())['active'])
    def test_projection_snapshots_survive_reload_without_duplicates(self):
        self.store([self.item(target=75)])
        today=self.app.diary.local_today()
        with self.app.connect() as db:
            for n in range(8):db.execute("INSERT INTO measurement(user_id,date,kind,value,unit,source) VALUES(?,?,'weight',?,'kg','manual')",(self.user,(today-dt.timedelta(days=35-n*5)).isoformat(),80-.2*n))
        first=self.client.get('/api/progress/milestones').json();second=self.client.get('/api/progress/milestones').json()
        self.assertEqual(first['rows'][0]['projection'],second['rows'][0]['projection'])
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM goal_projection WHERE user_id=?',(self.user,)).fetchone()[0],1)
    def test_active_goal_proposal_uses_only_first_without_profile_mutation(self):
        profile={**self.profile,'goals':dict(body=dict(target_weight_kg=50,pace='gentle')),'_active_milestone':dict(revision=1,definition=self.item(target=75))}
        value=dashboard.goal_profile(profile)
        self.assertEqual(value['goals']['body']['target_weight_kg'],75);self.assertEqual(profile['goals']['body']['target_weight_kg'],50)
    def test_projection_window_approaches_and_moves_away_with_observations(self):
        today=dt.date(2026,10,8)
        def estimate(rate):
            points=[dict(date=(today-dt.timedelta(days=35-n*5)).isoformat(),kind='weight',unit='kg',source='manual',value=80-rate*n*5) for n in range(8)]
            return dashboard.projection(self.item(target=75),points,today)
        fast=estimate(.04);base=estimate(.03);slow=estimate(.02)
        self.assertLess(fast['latest'],base['latest']);self.assertGreater(slow['latest'],base['latest'])
    def test_pending_balance_proposal_reappears_only_for_same_milestone_revision(self):
        import time
        self.store([self.item()])
        proposal=dict(target_weight_kg=70,proposed_kcal=-100,milestone=dict(revision=1,definition=self.item()))
        with self.app.connect() as db:db.execute("INSERT INTO goal_energy_proposal(user_id,created,state,state_token,payload) VALUES(?,?,'pending','token',?)",(self.user,time.time(),json.dumps(proposal)))
        self.assertIsNotNone(self.client.get('/api/progress/milestones').json()['balance_proposal'])
        self.store([self.item(target=69)],revision=1)
        self.assertIsNone(self.client.get('/api/progress/milestones').json()['balance_proposal'])
    def test_legacy_migration_preserves_profile(self):
        with self.app.connect() as db:
            profile={**self.profile,'goals':dict(body=dict(target_weight_kg=70))}
            value=dashboard.sequence(db,self.user,profile);self.assertEqual(value['items'][0]['id'],'legacy-weight_kg');self.assertEqual(profile['goals']['body']['target_weight_kg'],70)

for name in dir(base.DiaryTests):
    if name.startswith('test_') and name not in DashboardTests.__dict__:setattr(DashboardTests,name,None)

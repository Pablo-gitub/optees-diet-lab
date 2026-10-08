import copy
import test_diary_service as base

class MealDrafts(base.DiaryTests):
    def draft(self,slot='lunch'):
        r=self.client.get('/api/diary/draft',params=dict(date=self.date,slot=slot));self.assertEqual(r.status_code,200,r.text);return r.json()
    def body(self,draft):
        return dict(date=draft['date'],slot=draft['slot'],revision=draft['revision'],items=[{k:i[k] for k in ('food','grams','units') if k in i} for i in draft['items']])
    def commit(self,body):return self.client.post('/api/diary/draft/commit',json=body,headers=self.headers)
    def test_open_draft_does_not_confirm_and_discard_does_not_mutate(self):
        d=self.draft();self.assertEqual(d['items'][0]['grams'],80)
        p=self.body(d);p['items'][0]['grams']=90
        saved=self.client.put('/api/diary/draft',json=p,headers=self.headers);self.assertEqual(saved.status_code,200,saved.text)
        meal=self.client.get('/api/day',params=dict(date=self.date)).json()['meals'][2];self.assertEqual(meal['state'],'unknown');self.assertIsNone(meal['eaten'])
        d=self.draft();self.assertEqual(d['items'][0]['grams'],90)
        discarded=self.client.post('/api/diary/draft/discard',json=self.body(d),headers=self.headers)
        self.assertEqual(discarded.status_code,200);self.assertEqual(discarded.json()['meals'][2]['state'],'unknown')
    def test_empty_draft_is_not_a_zero_calorie_registration_and_cancel_can_retry(self):
        d=self.draft();p=self.body(d);p['items']=[]
        saved=self.client.put('/api/diary/draft',json=p,headers=self.headers);self.assertEqual(saved.status_code,200)
        p=self.body(saved.json());self.assertEqual(self.commit(p).status_code,400)
        self.assertEqual(self.client.get('/api/day',params=dict(date=self.date)).json()['meals'][2]['state'],'unknown')
        for _ in range(2):self.assertEqual(self.client.post('/api/diary/draft/discard',json=p,headers=self.headers).status_code,200)
    def test_atomic_replace_and_duplicate_submission(self):
        d=self.draft();p=self.body(d);p['items'][0]['grams']=90
        first=self.commit(p);self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json()['meals'][2]['eaten']['items'][0]['grams'],90)
        self.assertEqual(self.commit(p).status_code,200)
        altered=copy.deepcopy(p);altered['items'][0]['grams']=70;self.assertEqual(self.commit(altered).status_code,409)
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM diary_entry WHERE user_id=?',(self.user,)).fetchone()[0],1)
    def test_invalid_second_item_rolls_back_and_preserves_draft(self):
        self.post('/api/diary/confirm');d=self.draft();p=self.body(d);p['items'][0]['grams']=95;p['items'].append(dict(food=dict(source='CREA',id='missing'),grams=100))
        self.assertEqual(self.commit(p).status_code,400)
        meal=self.client.get('/api/day',params=dict(date=self.date)).json()['meals'][2];self.assertEqual(meal['eaten']['items'][0]['grams'],80)
        self.assertEqual(self.draft()['status'],'draft')
    def test_diary_and_draft_conflicts_do_not_overwrite(self):
        d=self.draft();self.post('/api/diary/confirm');self.assertEqual(self.commit(self.body(d)).status_code,409)
        self.assertTrue(self.draft()['stale'])
        p=self.body(d);saved=self.client.put('/api/diary/draft',json=p,headers=self.headers);self.assertEqual(saved.status_code,200)
        self.assertEqual(self.client.put('/api/diary/draft',json=p,headers=self.headers).status_code,409)
    def test_free_meal_add_replace_remove_in_single_commit(self):
        d=self.draft('breakfast');p=self.body(d);p['items']=[dict(food=dict(source='CREA',id='007510'),grams=100),dict(food=dict(source='CREA',id='000800'),grams=40)]
        self.assertEqual(self.commit(p).status_code,200)
        d=self.draft('breakfast');p=self.body(d);p['items']=p['items'][:1];p['items'][0]['grams']=150
        result=self.commit(p);self.assertEqual(result.status_code,200)
        items=result.json()['meals'][0]['eaten']['items'];self.assertEqual(len(items),1);self.assertEqual(items[0]['grams'],150)
    def test_outside_registration_does_not_require_solver_or_change_future(self):
        body=dict(date=self.date,slot='dinner',preset=dict(id='pizzeria',size='medio'))
        with self.app.connect() as db:before=[dict(r) for r in db.execute('SELECT * FROM planned_meal')]
        response=self.client.post('/api/rebalance/register',json=body,headers=self.headers);self.assertEqual(response.status_code,200,response.text)
        self.assertIsNotNone(response.json()['meals'][4]['consumed_estimate'])
        self.assertEqual(self.client.post('/api/rebalance/register',json=body,headers=self.headers).status_code,200)
        with self.app.connect() as db:self.assertEqual(before,[dict(r) for r in db.execute('SELECT * FROM planned_meal')])
    def test_quick_actions_reject_stale_snapshot_but_can_retry_success(self):
        meal=self.client.get('/api/day',params=dict(date=self.date)).json()['meals'][2]
        with self.app.connect() as db:db.execute('UPDATE planned_meal SET items=? WHERE id=?',(__import__('json').dumps([dict(food=dict(source='CREA',id='000800'),grams=90,units=None)]),self.meal))
        self.assertEqual(self.post('/api/diary/confirm',revision=meal['revision']).status_code,409)
        meal=self.client.get('/api/day',params=dict(date=self.date)).json()['meals'][2]
        for _ in range(2):self.assertEqual(self.post('/api/diary/confirm',revision=meal['revision']).status_code,200)
        current=self.client.get('/api/day',params=dict(date=self.date)).json()['meals'][2]
        self.client.patch('/api/diary/entries/'+str(current['eaten']['items'][0]['id']),json=dict(grams=140),headers=self.headers)
        self.assertEqual(self.post('/api/diary/reset',revision=current['revision']).status_code,409)
        self.assertEqual(self.client.get('/api/day',params=dict(date=self.date)).json()['meals'][2]['eaten']['items'][0]['grams'],140)
    def test_csrf_and_owner_boundary(self):
        d=self.draft();self.assertEqual(self.client.post('/api/diary/draft/commit',json=self.body(d)).status_code,403)
        other=__import__('fastapi.testclient',fromlist=['TestClient']).TestClient(self.app.app)
        other.post('/api/register',json=dict(username='draftother'+str(self.user),password='test-password-123'));other.post('/api/login',json=dict(username='draftother'+str(self.user),password='test-password-123'))
        h={'X-CSRF-Token':other.get('/api/profile').json()['csrf']}
        self.assertEqual(other.post('/api/diary/draft/commit',json=self.body(d),headers=h).status_code,409)

for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(MealDrafts,name,None)

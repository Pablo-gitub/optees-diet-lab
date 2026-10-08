import copy
import json
import test_diary_service as base
import taste_onboarding as tastes
import goal_milestones as milestones


class TasteOnboarding(base.DiaryTests):
    def payload(self, action='draft', **changes):
        p=self.client.get('/api/profile').json()['profile'];state=p['taste_onboarding']
        draft=copy.deepcopy(state['draft']);draft.update(changes)
        return dict(revision=state['revision'],action=action,step=2,draft=draft)
    def put(self,payload):
        return self.client.put('/api/profile/tastes',json=payload,headers=self.headers)
    def test_new_deferred_and_resumed_after_login_without_mutation(self):
        state=self.profile['taste_onboarding'];self.assertTrue(state['welcome'])
        original=copy.deepcopy(self.profile)
        response=self.put(self.payload('defer',preference_note='bozza'));self.assertEqual(response.status_code,200,response.text)
        self.client.post('/api/logout',headers=self.headers)
        with self.app.connect() as db:name=db.execute('SELECT username FROM users WHERE id=?',(self.user,)).fetchone()[0]
        self.client.post('/api/login',json=dict(username=name,password='test-password-123'))
        p=self.client.get('/api/profile').json()['profile']
        self.assertEqual(p['taste_onboarding']['status'],'deferred');self.assertFalse(p['taste_onboarding']['welcome'])
        self.assertEqual(p['taste_onboarding']['draft']['preference_note'],'bozza')
        for field in ('preference_note','targets','daily_meals','excluded_crea_ids'):self.assertEqual(p[field],original[field])
    def test_complete_only_updates_supported_fields_and_solver_config(self):
        before=copy.deepcopy(self.profile);payload=self.payload('complete',excluded_crea_ids=['007510'],preference_note='promemoria',afternoon_fruit=False)
        response=self.put(payload);self.assertEqual(response.status_code,200,response.text);p=response.json()['profile']
        self.assertEqual(p['taste_onboarding']['status'],'completed');self.assertEqual(p['excluded_crea_ids'],['007510'])
        self.assertFalse(p['daily_meals']['enabled']);self.assertFalse(p['daily_meals']['afternoon_fruit'])
        config=self.app.make_config(p,0);self.assertEqual(config['excluded_crea_ids'],['007510'])
        for field in ('targets','meal_targets','mode','targets_demo','personal_diets'):self.assertEqual(p[field],before[field])
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM planned_meal WHERE week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?)',(self.user,)).fetchone()[0],1)
    def test_invalid_and_stale_save_do_not_overwrite(self):
        payload=self.payload();self.assertEqual(self.put(payload).status_code,200)
        self.assertEqual(self.put(payload).status_code,409)
        bad=self.payload('complete',banana_min_g=250,banana_max_g=100);self.assertEqual(self.put(bad).status_code,400)
        bad=self.payload('complete',excluded_crea_ids=['invented']);self.assertEqual(self.put(bad).status_code,400)
        self.assertEqual(self.client.get('/api/profile').json()['profile']['taste_onboarding']['status'],'partial')
    def test_defer_incomplete_range_keeps_draft_but_not_active_settings(self):
        result=self.put(self.payload('defer',banana_min_g=250,banana_max_g=100))
        self.assertEqual(result.status_code,200,result.text)
        p=result.json()['profile'];self.assertEqual(p['taste_onboarding']['draft']['banana_min_g'],250)
        self.assertEqual(p['daily_meals']['banana_min_g'],100)
        self.assertEqual(self.put(self.payload('complete')).status_code,400)
    def test_isolation_and_csrf(self):
        response=self.client.put('/api/profile/tastes',json=self.payload());self.assertEqual(response.status_code,403)
        with self.app.connect() as db:
            before={r['id']:r['profile'] for r in db.execute('SELECT id,profile FROM users WHERE id != ?',(self.user,))}
        self.assertEqual(self.put(self.payload('complete',preference_note='solo mio')).status_code,200)
        with self.app.connect() as db:
            after={r['id']:r['profile'] for r in db.execute('SELECT id,profile FROM users WHERE id != ?',(self.user,))}
        self.assertEqual(before,after)
    def test_legacy_migration_keeps_existing_preferences_without_welcome(self):
        legacy=copy.deepcopy(self.profile);legacy.pop('taste_onboarding');legacy['preference_note']='esistente';legacy['food_preferences']={'products':[]};legacy['excluded_crea_ids']=['007510']
        with self.app.connect() as db:db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(legacy),self.user))
        p=self.client.get('/api/profile').json()['profile'];self.assertFalse(p['taste_onboarding']['welcome'])
        self.assertEqual(p['taste_onboarding']['draft']['preference_note'],'esistente')
        self.assertEqual(p['taste_onboarding']['draft']['excluded_crea_ids'],['007510']);self.assertEqual(p['food_preferences'],{'products':[]})
    def test_enabled_impossible_choices_rejected_atomically(self):
        p=copy.deepcopy(self.profile);p['daily_meals']['enabled']=True
        with self.app.connect() as db:db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(p),self.user))
        result=self.put(self.payload('complete',excluded_crea_ids=['007510']));self.assertEqual(result.status_code,400,result.text)
        self.assertEqual(self.client.get('/api/profile').json()['profile']['excluded_crea_ids'],[])
    def test_supported_habits_reach_formulation_without_changing_targets(self):
        from test_daily_meals import preference_fixture
        p=copy.deepcopy(self.profile);p['food_preferences']=preference_fixture();p['daily_meals']['enabled']=True
        with self.app.connect() as db:db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(p),self.user))
        cuisine=self.client.get('/api/cuisines').json()[0]['id']
        result=self.put(self.payload('complete',afternoon_fruit=False,allow_second_bar=True,preferred_cuisines=[cuisine]))
        self.assertEqual(result.status_code,200,result.text);profile=result.json()['profile']
        _,choices,_=self.app.formulate(self.app.make_config(profile,0),self.app.load_foods())
        self.assertFalse(any(c['meal']=='afternoon_snack' for c in choices))
        bars=[c for c in choices if c['food_id']=='personal:bar'];self.assertEqual({c['units'] for c in bars},{1,2})
        self.assertEqual(profile['preferred_cuisines'],[cuisine]);self.assertEqual(profile['daily_meals']['targets'],p['daily_meals']['targets'])
    def test_old_profile_form_cannot_overwrite_new_preference_draft(self):
        old=copy.deepcopy(self.profile);old['taste_revision']=old['taste_onboarding']['revision']
        self.assertEqual(self.put(self.payload('draft',preference_note='nuova bozza')).status_code,200)
        response=self.client.put('/api/profile',json=old,headers=self.headers);self.assertEqual(response.status_code,409)
        self.assertEqual(self.client.get('/api/profile').json()['profile']['taste_onboarding']['draft']['preference_note'],'nuova bozza')
    def test_full_profile_edit_invalidates_open_draft(self):
        draft=self.payload();p=copy.deepcopy(self.profile);p['preference_note']='altro editor'
        response=self.client.put('/api/profile',json=p,headers=self.headers);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.put(draft).status_code,409)


for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(TasteOnboarding,name,None)


class MilestoneContract(__import__('unittest').TestCase):
    def test_later_achievement_never_skips_first_pending(self):
        item=dict(id='one',metric='weight_kg',target=78,comparison='at_most',state='pending',desired_date=None,window_weeks=1)
        second=dict(item,id='two',target=76,state='achieved')
        value=dict(version=1,items=[item,second]);self.assertEqual(milestones.active_definition(value)['id'],'one')
        value['items'][0]['state']='skipped';self.assertIsNone(milestones.active_definition(value))
    def test_duplicate_ids_and_unsupported_metrics_rejected(self):
        item=dict(id='one',metric='weight_kg',target=78,comparison='at_most',state='pending',desired_date=None,window_weeks=1)
        with self.assertRaises(ValueError):milestones.validate(dict(version=1,items=[item,item]))
        with self.assertRaises(ValueError):milestones.validate(dict(version=1,items=[dict(item,metric='invented')]))

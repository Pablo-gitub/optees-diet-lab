import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['DIET_WEB_DB'] = str(Path(cls.temp.name) / 'test.sqlite')
        spec = importlib.util.spec_from_file_location('test_web_app', ROOT / 'web/app.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        del os.environ['DIET_WEB_DB']

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        # Login rate-limit state belongs to a test, not the whole suite.
        self.module.attempts.clear()

    def account(self, name):
        client = TestClient(self.module.app)
        client.post('/api/register', json={'username': name, 'password': 'long-test-password'})
        reply = client.post('/api/login', json={'username': name, 'password': 'long-test-password'})
        self.assertEqual(reply.status_code, 200)
        return client, {'x-csrf-token': reply.json()['csrf']}

    def test_health_reports_and_import_ownership_are_private(self):
        first,h1=self.account('healthfirst');second,h2=self.account('healthsecond')
        with self.module.connect() as db:owner=db.execute('SELECT id FROM users WHERE username=?',('healthfirst',)).fetchone()['id']
        directory=self.module.health_directory(owner);directory.mkdir(parents=True,exist_ok=True)
        report=dict(version='test',timezone='Europe/Rome',as_of='2026-10-01',measures={'weight':dict(value=80,date='2026-10-01')},scenarios={'valid_days':0},windows=[{'days':28,'end_date':None}],workout_forecasts=[])
        (directory/'summary.json').write_text(json.dumps(report))
        marker=directory.parent/'owner.json';marker.write_text(json.dumps({'user_id':owner}))
        self.assertEqual(TestClient(self.module.app).get('/api/health').status_code,401)
        self.assertTrue(first.get('/api/health').json()['imported'])
        self.assertTrue(first.get('/api/health').json()['can_import'])
        response=second.get('/api/health').json();self.assertFalse(response['imported']);self.assertFalse(response['can_import']);self.assertIsNone(response['report'])
        self.assertEqual(first.post('/api/health/import',json={}).status_code,403)
        self.assertEqual(second.post('/api/health/import',json={},headers=h2).status_code,403)

    def test_trial_feedback_is_private_validated_and_updates_once(self):
        first,h1=self.account('trialfirst');second,h2=self.account('trialsecond')
        with self.module.connect() as db:
            owner=db.execute('SELECT id FROM users WHERE username=?',('trialfirst',)).fetchone()['id']
            plan_id=db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,?,?)',(owner,0,json.dumps({'status':'optimal','mode':'free','day_index':0}))).lastrowid
        url=f'/api/plans/{plan_id}/feedback'
        self.assertEqual(first.post(url,json={'tried':True,'rating':4}).status_code,403)
        self.assertEqual(second.post(url,json={'tried':True,'rating':4},headers=h2).status_code,404)
        for data in [{'tried':False,'rating':4},{'tried':True,'rating':True},{'tried':True,'rating':6}]:
            self.assertEqual(first.post(url,json=data,headers=h1).status_code,400)
        for rating in [4,5]:
            self.assertEqual(first.post(url,json={'tried':True,'rating':rating},headers=h1).status_code,200)
        self.assertEqual(first.get('/api/plans').json()[0]['feedback'],5)
        self.assertEqual(second.get('/api/plans').json(),[])
        with self.module.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM plan_feedback').fetchone()[0],1)

    def test_recipe_solver_auth_validation_and_history_isolation(self):
        first, h1 = self.account('recipefirst')
        second, h2 = self.account('recipesecond')
        self.assertEqual(TestClient(self.module.app).get('/api/recipe-solver').status_code, 401)
        options = first.get('/api/recipe-solver').json()
        self.assertGreaterEqual(len(options['recipes']), 2)
        self.assertIn('foodose:R054', {r['id'] for r in options['recipes']})
        config = options['defaults']
        self.assertEqual(first.post('/api/recipe-optimize', json=config).status_code, 403)
        self.assertEqual(
            first.post('/api/recipe-optimize', json=dict(config, recipe_id='foodose:unmapped'), headers=h1).status_code,
            400,
        )
        self.assertEqual(
            first.post('/api/recipe-optimize', json=dict(config, flexibility=0.3), headers=h1).status_code, 400
        )
        self.assertEqual(
            first.post(
                '/api/recipe-optimize', json=dict(config, disabled_products=['CREA:fake']), headers=h1
            ).status_code,
            400,
        )
        with self.module.connect() as db:
            user = db.execute('SELECT id FROM users WHERE username=?', ('recipefirst',)).fetchone()['id']
            db.execute(
                'INSERT INTO recipe_runs(user_id,created,payload) VALUES(?,?,?)',
                (user, 0, json.dumps({'title': 'first only'})),
            )
        self.assertEqual(second.get('/api/recipe-runs').json(), [])
        self.assertEqual(first.get('/api/recipe-runs').json()[0]['result']['title'], 'first only')

    def test_recipe_diet_options_are_private_and_validate_context(self):
        client, _ = self.account('dietrecipes')
        self.assertEqual(TestClient(self.module.app).get('/api/recipe-diet-options').status_code, 401)
        self.assertEqual(client.get('/api/recipe-diet-options?mode=training').status_code, 403)
        free = client.get('/api/recipe-diet-options').json()
        self.assertNotIn('rules_sha256', free)
        self.assertTrue(all(r['status'] == 'unconstrained' for r in free['recipes']))
        self.assertEqual(client.get('/api/recipe-diet-options?day_index=14').status_code, 400)
        self.assertEqual(client.get('/api/recipe-diet-options?meal=breakfast').status_code, 400)
        with self.module.connect() as db:
            row = db.execute('SELECT id,profile FROM users WHERE username=?', ('dietrecipes',)).fetchone()
            profile = json.loads(row['profile'])
            profile['personal_diets'] = True
            db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(profile), row['id']))
        reply = client.get('/api/recipe-diet-options?mode=training&day_index=0&meal=lunch')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['expression'], 'A')
        self.assertIn('rules_sha256', reply.json())
        self.assertEqual(client.get('/api/recipe-diet-options?mode=unknown').status_code, 400)

    def test_daily_configuration_is_private_validated_and_persisted(self):
        first,h1=self.account('dailyfirst');second,h2=self.account('dailysecond')
        profile=first.get('/api/profile').json()['profile']
        self.assertFalse(profile['daily_meals']['enabled'])
        self.assertNotIn('food_preferences',profile)
        profile['daily_meals']['enabled']=True
        self.assertEqual(first.put('/api/profile',json=profile,headers=h1).status_code,200)
        updated=first.get('/api/profile').json()['profile']
        self.assertTrue(updated['daily_meals']['enabled'])
        self.assertFalse(second.get('/api/profile').json()['profile']['daily_meals']['enabled'])
        config=self.module.make_config(updated,0)
        self.assertEqual(config['food_preferences'],{})
        self.assertEqual(config['daily_meals']['targets'],updated['daily_meals']['targets'])
        profile['daily_meals']['banana_min_g']=600
        self.assertEqual(first.put('/api/profile',json=profile,headers=h1).status_code,400)

    def test_new_profile_has_no_paolo_data_or_diets(self):
        client, headers = self.account('amico')
        profile = client.get('/api/profile').json()['profile']
        self.assertEqual(profile['mode'], 'free')
        self.assertFalse(profile['personal_diets'])
        self.assertNotIn('food_preferences', profile)
        self.assertEqual(profile['preference_note'], '')
        profile['mode'] = 'training'
        profile['personal_diets'] = True
        self.assertEqual(client.put('/api/profile', json=profile, headers=headers).status_code, 400)

    def test_authentication_csrf_and_origin(self):
        client, headers = self.account('security')
        self.assertEqual(TestClient(self.module.app).get('/api/plans').status_code, 401)
        self.assertEqual(client.post('/api/logout').status_code, 403)
        self.assertEqual(
            client.post('/api/logout', headers={**headers, 'origin': 'http://other-host'}).status_code, 403
        )
        self.assertEqual(client.post('/api/logout', headers=headers).status_code, 200)
        self.assertEqual(client.get('/api/profile').status_code, 401)

    def test_plans_and_configuration_are_isolated(self):
        first, h1 = self.account('first')
        second, h2 = self.account('second')
        with self.module.connect() as db:
            user = db.execute('SELECT id FROM users WHERE username=?', ('first',)).fetchone()['id']
            payload = {'status': 'optimal', 'day_index': 0, 'mode': 'free', 'secret': 'first-only'}
            cursor = db.execute(
                'INSERT INTO plans(user_id,created,payload) VALUES(?,?,?)', (user, 0, json.dumps(payload))
            )
            plan_id = cursor.lastrowid
        self.assertEqual(second.get('/api/plans').json(), [])
        self.assertEqual(second.post(f'/api/plans/{plan_id}/select', headers=h2).status_code, 404)
        self.assertEqual(first.post(f'/api/plans/{plan_id}/select', headers=h1).status_code, 200)
        profile = first.get('/api/profile').json()['profile']
        profile['preference_note'] = '<script>personal</script>'
        self.assertEqual(first.put('/api/profile', json=profile, headers=h1).status_code, 200)
        self.assertEqual(second.get('/api/profile').json()['profile']['preference_note'], '')

    def test_cuisine_preferences_are_personal_and_catalog_filters(self):
        first, h1 = self.account('cuisineone')
        second, h2 = self.account('cuisinetwo')
        profile = first.get('/api/profile').json()['profile']
        profile['preferred_cuisines'] = ['italian', 'chinese']
        self.assertEqual(first.put('/api/profile', json=profile, headers=h1).status_code, 200)
        self.assertEqual(second.get('/api/profile').json()['profile']['preferred_cuisines'], [])
        self.assertEqual(first.get('/api/recipes?preferred=true').json()['total'], 87)
        self.assertEqual(second.get('/api/recipes?preferred=true').json()['total'], 0)
        china = first.get('/api/recipes?cuisine=chinese').json()
        self.assertEqual(china['total'], 6)
        self.assertTrue(all(r['cuisine'] == 'Chinese' for r in china['recipes']))
        self.assertEqual(first.get('/api/recipes?q=%25').json()['total'], 0)
        self.assertEqual(first.get('/api/recipes?offset=-1').status_code, 400)
        profile['preferred_cuisines'] = ['unknown']
        self.assertEqual(first.put('/api/profile', json=profile, headers=h1).status_code, 400)

    def test_registration_can_be_disabled(self):
        client = TestClient(self.module.app)
        os.environ['DIET_WEB_ALLOW_REGISTER'] = '0'
        try:
            reply = client.post('/api/register', json={'username': 'blocked', 'password': 'long-test-password'})
        finally:
            del os.environ['DIET_WEB_ALLOW_REGISTER']
        self.assertEqual(reply.status_code, 403)
        with self.module.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM users WHERE username=?', ('blocked',)).fetchone())

    def test_inconsistent_targets_are_saved_with_warning(self):
        client, headers = self.account('targetwarning')
        profile = client.get('/api/profile').json()['profile']
        profile['targets']['kcal_100g']['target'] = 1400
        response = client.put('/api/profile', json=profile, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['warnings'][0]['code'], 'targets_inconsistent')
        saved = client.get('/api/profile').json()
        self.assertEqual(saved['profile']['targets'], profile['targets'])
        self.assertEqual(saved['warnings'][0]['scope'], 'main_meals')

    def test_generate_returns_plan_set_and_preserves_legacy_history(self):
        from contextlib import asynccontextmanager
        from unittest.mock import patch
        from test_recipe_solver import solve
        client,headers=self.account('chainapi')
        @asynccontextmanager
        async def stream(*args):yield (None,None)
        class Session:
            def __init__(self,*args):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def initialize(self):pass
        async def fake(session,problem):return solve(problem)
        with patch.object(self.module,'stdio_client',stream),patch.object(self.module,'ClientSession',Session),patch('multiobjective_day.solve_problem',side_effect=fake):
            self.assertEqual(client.post('/api/generate',json={}).status_code,403)
            response=client.post('/api/generate',json=dict(strategy='legacy',pool_size=4,k=4,time_limit=120),headers=headers)
        self.assertEqual(response.status_code,200)
        result=response.json();self.assertEqual(result['spec_version'],'orchestration-v1')
        self.assertIn('legacy_strategy_ignored',[w['code'] for w in result['warnings']])
        self.assertEqual(len(client.get('/api/plans').json()),result['count'])
        with self.module.connect() as db:
            owner=db.execute('SELECT id FROM users WHERE username=?',('chainapi',)).fetchone()['id']
            self.assertEqual(db.execute('SELECT COUNT(*) FROM plan_feedback WHERE user_id=?',(owner,)).fetchone()[0],0)
            self.assertTrue(json.loads(db.execute('SELECT input FROM plan_set WHERE user_id=?',(owner,)).fetchone()[0])['request'])

    def test_profile_update_without_targets_keeps_existing(self):
        client, headers = self.account('notargets')
        profile = client.get('/api/profile').json()['profile']
        targets = profile.pop('targets')
        self.assertEqual(client.put('/api/profile', json=profile, headers=headers).status_code, 200)
        self.assertEqual(client.get('/api/profile').json()['profile']['targets'], targets)

    def test_recipe_catalog_uses_italian_titles_and_photos_first(self):
        client, _ = self.account('italiantitles')
        found = client.get('/api/recipes?q=polpette%20di%20tacchino').json()
        self.assertGreater(found['total'], 0)
        self.assertTrue(all('tacchino' in r['title_it'].lower() for r in found['recipes']))
        self.assertNotIn('tacchino', found['recipes'][0]['title'].lower())
        first = client.get('/api/recipes').json()['recipes']
        flags = [bool(r.get('illustrative_image')) for r in first]
        self.assertEqual(flags, sorted(flags, reverse=True))
        self.assertTrue(flags[0])

    def test_personal_files_are_not_served(self):
        client = TestClient(self.module.app)
        self.assertEqual(client.get('/data/personal/web_access.txt').status_code, 404)
        self.assertEqual(client.get('/static/../app.py').status_code, 404)


if __name__ == '__main__':
    unittest.main()

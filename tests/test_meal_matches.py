import asyncio
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import meal_matches as matches
from plan_diet_day import load_foods,formulate,decode_result
from test_recipe_solver import solve
from test_joint_orchestration import fixture

ROOT=Path(__file__).resolve().parents[1]

class MatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();os.environ['DIET_WEB_DB']=self.temp.name+'/web.sqlite'
        spec=importlib.util.spec_from_file_location('matches_web',ROOT/'web/app.py');self.web=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.web);del os.environ['DIET_WEB_DB']
        self.client=TestClient(self.web.app);self.client.post('/api/register',json=dict(username='synthetic',password='test-password-123'))
        login=self.client.post('/api/login',json=dict(username='synthetic',password='test-password-123')).json();self.headers={'x-csrf-token':login['csrf']}
        self.profile=self.client.get('/api/profile').json()['profile']
        with self.web.connect() as db:self.user=db.execute("SELECT id FROM users WHERE username='synthetic'").fetchone()[0]
    def tearDown(self):self.temp.cleanup()
    def deck(self):
        async def fake(session,p):return solve(p)
        with self.web.connect() as db,patch('plan_diet_day.solve_problem',side_effect=fake):return asyncio.run(matches.deck(None,db,self.user,self.profile,'lunch','rest',self.web.make_config))
    def test_ten_verified_diverse_optees_cards_and_stable_ids_exclusions(self):
        self.profile['excluded_crea_ids']=['106500']
        deck=self.deck();self.assertEqual(deck['status'],'ok',deck);self.assertEqual(len(deck['cards']),10)
        self.assertGreaterEqual(deck['pool']['exploration_fraction'],.3)
        self.assertEqual(len({tuple(c['combination']) for c in deck['cards']}),10)
        for c in deck['cards']:
            self.assertTrue(2<=len(c['foods'])<=4)
            self.assertNotIn('106500',[i['generic_id'] for i in c['foods']])
            for i in c['foods']:self.assertEqual(i['grams']%5,0);self.assertIsNone(i['image'])
            for n,t in c['targets'].items():
                self.assertGreaterEqual(c['nutrients'][n.replace('_100g','')],t['min']-.001)
                self.assertLessEqual(c['nutrients'][n.replace('_100g','')],t['max']+.001)
        with self.web.connect() as db:db.execute('DELETE FROM meal_match WHERE user_id=?',(self.user,))
        again=self.deck();self.assertEqual([c['id'] for c in deck['cards']],[c['id'] for c in again['cards']])
    def test_api_votes_csrf_undo_owner_skip_and_explicit_questions(self):
        cards=self.deck()['cards'];ids=[c['id'] for c in cards]
        self.assertEqual(self.client.post('/api/matches/'+ids[0]+'/vote',json={'vote':'like'}).status_code,403)
        for identifier in ids[:3]:self.assertEqual(self.client.post('/api/matches/'+identifier+'/vote',json={'vote':'dislike'},headers=self.headers).status_code,200)
        with self.web.connect() as db:self.assertNotIn('009210',json.loads(db.execute('SELECT profile FROM users WHERE id=?',(self.user,)).fetchone()[0])['excluded_crea_ids'])
        questions=self.client.get('/api/matches/questions').json()['questions'];self.assertTrue(questions)
        generic=questions[0]['food']['id']
        response=self.client.post('/api/matches/questions/'+generic+'/answer',json={'answer':'no'},headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['silent_until'],(matches.local_today()+dt.timedelta(days=60)).isoformat())
        self.assertFalse(any(q['food']['id']==generic for q in self.client.get('/api/matches/questions').json()['questions']))
        self.assertEqual(self.client.delete('/api/matches/'+ids[0]+'/vote',headers=self.headers).status_code,409)
        self.assertEqual(self.client.delete('/api/matches/'+ids[2]+'/vote',headers=self.headers).status_code,200)
        self.client.post('/api/matches/'+ids[2]+'/vote',json={'vote':'like'},headers=self.headers)
        self.client.post('/api/matches/'+ids[2]+'/vote',json={'vote':'skip'},headers=self.headers)
        with self.web.connect() as db:self.assertEqual(matches.current_votes(db,self.user)[ids[2]]['vote'],'like')
        other=TestClient(self.web.app);other.post('/api/register',json=dict(username='friend',password='test-password-123'));h=other.post('/api/login',json=dict(username='friend',password='test-password-123')).json()['csrf']
        self.assertEqual(other.post('/api/matches/'+ids[0]+'/vote',json={'vote':'love'},headers={'x-csrf-token':h}).status_code,404)
        self.assertFalse(other.get('/api/matches/questions').json()['questions'])
    def test_yes_is_explicit_exclusion_and_like_suppresses_question(self):
        cards=self.deck()['cards']
        with self.web.connect() as db:
            for c in cards[:4]:matches.vote(db,self.user,c['id'],{'vote':'dislike'})
            questions=matches.questions(db,self.user,self.profile)['questions'];self.assertTrue(questions)
            generic=questions[0]['food']['id']
            matches.answer(db,self.user,self.profile,generic,{'answer':'yes'})
            updated=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(self.user,)).fetchone()[0]);self.assertIn(generic,updated['excluded_crea_ids'])
            matches.vote(db,self.user,cards[0]['id'],{'vote':'love'})
            liked={i['generic_id'] for i in cards[0]['foods']}
            self.assertFalse(liked&{q['food']['id'] for q in matches.questions(db,self.user,updated)['questions']})
    def test_favorite_branches_ratio_soft_love_and_dislike_combination(self):
        card=self.deck()['cards'][0];card['vote']='love';self.profile['_match_cards']=[card]
        cfg=self.web.make_config(self.profile,0);foods=load_foods();p,choices,slots=formulate(cfg,foods)
        branches=[c for c in choices if c.get('match_id')];self.assertTrue(branches)
        y=branches[0]['y'];self.assertAlmostEqual(p['objective']['coefficients'][y],-2*matches.POLICY['preference_bonus'])
        p['constraints'].append(dict(coefficients=[int(i==y) for i in range(len(p['variables']))],relation='=',rhs=1))
        result=solve(p);self.assertEqual(result['mathematical_status'],'optimal')
        values={v['name']:v['value'] for v in result['result']['variables']};active=[c for c in branches if values[p['variables'][c['y']]['name']]>.5];total=sum(values[p['variables'][c['q']]['name']] for c in active)
        fractions={i['generic_id']:i['grams']/sum(f['grams'] for f in card['foods']) for i in card['foods']}
        for c in active:
            ratio=values[p['variables'][c['q']]['name']]/total
            self.assertGreaterEqual(ratio,.7*fractions[c['principal_food_id']]-1e-6);self.assertLessEqual(ratio,1.3*fractions[c['principal_food_id']]+1e-6)
        card['vote']='dislike';cfg=self.web.make_config(self.profile,0);p,choices,_=formulate(cfg,load_foods())
        penalty=[i for i,v in enumerate(p['variables']) if v['name'].startswith('match_dislike')];self.assertTrue(penalty);self.assertGreater(p['objective']['coefficients'][penalty[0]],0)
    def test_images_require_explicit_license_and_attribution(self):
        self.assertIsNone(matches.image_for({'image_url':'https://example.org/a.jpg','license':'ODbL'}))
        self.assertIsNone(matches.image_for({'image_url':'https://example.org/a.jpg','image_license':'CC BY-SA 3.0'}))
        self.assertTrue(matches.image_for({'image_url':'https://example.org/a.jpg','image_license':'CC BY-SA 3.0','image_attribution':'Autore sintetico'}))

    def test_weekly_cap_context_and_skip_not_trial_reward(self):
        from week_orchestration import weekly_model
        import contextual_bandit
        card=self.deck()['cards'][0]
        with self.web.connect() as db:
            matches.vote(db,self.user,card['id'],{'vote':'love'});matches.attach(db,self.user,self.profile)
            observed=contextual_bandit.observations(db,self.user,self.profile)
        self.assertTrue(observed['_match_preference_context'])
        self.assertFalse(contextual_bandit.rewards({'arms':['match:'+card['id']],'bandit_context':card['id']},observed))
        p,blocks,choices,maximum=weekly_model(self.profile,dict(week_start='2026-10-12'),self.web.make_config,load_foods())
        ys={c['y'] for c in choices if c.get('match_id')==card['id']}
        self.assertEqual(len(ys),7)
        self.assertTrue(any(r['relation']=='<=' and r['rhs']==2 and {i for i,v in enumerate(r['coefficients']) if v}==ys for r in p['constraints']))
        for y in sorted(ys)[:3]:p['constraints'].append(dict(coefficients=[int(i==y) for i in range(len(p['variables']))],relation='=',rhs=1))
        self.assertEqual(solve(p)['mathematical_status'],'infeasible')
    def test_deck_http_and_repeated_deck_has_new_exploration(self):
        async def fake(session,p):return solve(p)
        with patch('plan_diet_day.solve_problem',side_effect=fake):
            response=self.client.get('/api/matches/deck',params={'slot':'lunch','day_type':'rest'})
            self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['status'],'ok')
            second=self.client.get('/api/matches/deck',params={'slot':'lunch','day_type':'rest'})
            self.assertEqual(second.status_code,200,second.text)
            self.assertGreaterEqual(second.json()['pool']['exploration_fraction'],.3)
        self.assertEqual(self.client.get('/api/matches/deck',params={'slot':'invalid','day_type':'rest'}).status_code,400)
        self.assertEqual(self.client.get('/api/matches/deck',params={'slot':'lunch','day_type':'invalid'}).status_code,400)
    def test_restricted_habits_report_shortfall_without_invented_foods(self):
        self.profile['daily_meals']['enabled']=True
        async def fake(session,p):return solve(p)
        with self.web.connect() as db,patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(matches.deck(None,db,self.user,self.profile,'breakfast','rest',self.web.make_config))
        self.assertIn(result['status'],('partial','unavailable'));self.assertTrue(result['reason'])
        for card in result['cards']:self.assertEqual([f['generic_id'] for f in card['foods']],['007510'])

"""Contratto T-001: test rossi, solo dati sintetici e database temporanei."""
import contextlib
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

ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.date(2026, 10, 10)


class PresumedMealsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / 'test.sqlite'
        # Prevent the owner-bootstrap branch from loading personal preferences.
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt TEXT, password TEXT, profile TEXT)')
            db.execute("INSERT INTO users VALUES(1,'synthetic-bootstrap','','','{}')")
        with patch.dict(os.environ, DIET_WEB_DB=str(path)):
            spec = importlib.util.spec_from_file_location('presumed_test_app', ROOT / 'web/app.py')
            self.app = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.app)
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(self.app.diary, 'local_today', return_value=TODAY))
        # Avoid nutritional catalog dependencies: a complete, synthetic food.
        self.patches.enter_context(patch.object(self.app.diary, 'resolve_food', side_effect=lambda ref, profile: dict(
            food=ref, name='Alimento sintetico', source_label='Fixture',
            per_100g=dict(kcal=100, protein_g=10, fat_g=2, carbs_available_g=10))))
        self.patches.enter_context(patch.object(self.app, 'load_health_report', return_value=None))
        self.client, self.user, self.profile, self.headers = self.account('synthetic_owner')
        self.items = [dict(food=dict(source='CREA', id='synthetic'), grams=80, units=None)]

    def account(self, name):
        client = TestClient(self.app.app)
        self.assertEqual(client.post('/api/register', json=dict(username=name, password='synthetic-password-123')).status_code, 200)
        self.assertEqual(client.post('/api/login', json=dict(username=name, password='synthetic-password-123')).status_code, 200)
        value = client.get('/api/profile').json()
        with self.app.connect() as db:
            user = db.execute('SELECT id FROM users WHERE username=?', (name,)).fetchone()[0]
        return client, user, value['profile'], {'X-CSRF-Token': value['csrf']}

    def date(self, ago):
        return (TODAY - dt.timedelta(days=ago)).isoformat()

    def plan(self, ago=1, slot='lunch', user=None):
        user = self.user if user is None else user
        date = self.date(ago)
        start = (dt.date.fromisoformat(date) - dt.timedelta(days=dt.date.fromisoformat(date).weekday())).isoformat()
        with self.app.connect() as db:
            week = db.execute("SELECT id FROM week_plan WHERE user_id=? AND week_start=? AND status='active'", (user, start)).fetchone()
            if not week:
                week_id = db.execute("INSERT INTO week_plan(user_id,week_start,mode,status,created,targets,day_context) VALUES(?,?,'free','active',0,?,?)",
                                     (user, start, json.dumps(self.profile['targets']), '{}')).lastrowid
            else:
                week_id = week[0]
            db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status) VALUES(?,?,?,?,'best','chosen')",
                       (week_id, date, slot, json.dumps(self.items)))
        return dict(date=date, slot=slot)

    def view(self, date):
        with self.app.connect() as db:
            return self.app.diary.day_view(db, self.user, self.profile, date)

    def meal(self, date, slot='lunch'):
        return next(m for m in self.view(date)['meals'] if m['slot'] == slot)

    def pending(self, client=None):
        response = (client or self.client).get('/api/diary/pending')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def confirm_all(self, meals, client=None, headers=None):
        return (client or self.client).post('/api/diary/confirm-all', json=dict(meals=meals),
                                            headers=self.headers if headers is None else headers)

    def snapshot(self):
        with self.app.connect() as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            return {t: db.execute('SELECT * FROM "' + t + '" ORDER BY rowid').fetchall() for t in tables}

    def test_yesterday_presumed_totals_state_actions_and_logged_coverage(self):
        self.plan()
        value = self.view(self.date(1)); meal = next(m for m in value['meals'] if m['slot'] == 'lunch')
        self.assertIs(meal.get('presumed'), True)
        self.assertEqual(meal['state'], 'unknown')
        self.assertTrue({'confirm', 'edit', 'skip'} <= set(meal['actions']))
        self.assertEqual(meal['eaten']['items'], meal['planned']['items'])
        self.assertEqual(meal['eaten']['kcal'], 80)
        self.assertEqual(value['totals']['eaten']['kcal'], 80)
        self.assertEqual(value['totals']['coverage']['presumed_slots'], 1)
        self.assertEqual(value['totals']['coverage']['logged_slots'], 0)
        self.assertTrue(all(isinstance(m.get('presumed'), bool) for m in value['meals']))
        # A later explicit confirmation moves coverage without doubling intake.
        response = self.client.post('/api/diary/confirm', json=dict(date=self.date(1), slot='lunch'), headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value['totals']['eaten']['kcal'], 80)
        self.assertEqual(value['totals']['coverage']['presumed_slots'], 0)
        self.assertEqual(value['totals']['coverage']['logged_slots'], 1)

    def test_later_manual_edit_recalculates_totals_without_presumed_double_count(self):
        pair = self.plan()
        self.assertIs(self.meal(pair['date']).get('presumed'), True)
        response = self.client.post('/api/diary/entries', json=dict(pair, food=self.items[0]['food'], grams=90), headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json(); meal = next(m for m in value['meals'] if m['slot'] == 'lunch')
        self.assertIs(meal['presumed'], False)
        self.assertEqual(meal['state'], 'modified')
        self.assertEqual(value['totals']['eaten']['kcal'], 90)
        self.assertEqual(value['totals']['coverage']['presumed_slots'], 0)
        self.assertEqual(value['totals']['coverage']['logged_slots'], 1)

    def test_today_and_future_are_not_presumed_or_pending(self):
        for ago in (0, -1):
            self.plan(ago)
            with self.subTest(ago=ago):
                meal = self.meal(self.date(ago))
                self.assertIs(meal.get('presumed'), False)
                self.assertIsNone(meal['eaten'])
        self.assertEqual(self.pending()['count'], 0)

    def test_eight_days_old_is_presumed_but_not_in_pending(self):
        self.plan(8)
        self.assertIs(self.meal(self.date(8)).get('presumed'), True)
        self.assertEqual(self.pending()['count'], 0)

    def test_pending_window_order_count_and_item_shape(self):
        for ago, slot in [(1, 'lunch'), (1, 'dinner'), (7, 'lunch'), (8, 'lunch'), (0, 'lunch')]:
            self.plan(ago, slot)
        result = self.pending()
        self.assertEqual((result['from'], result['to']), (self.date(7), self.date(1)))
        self.assertEqual(result['count'], 3)
        self.assertEqual([d['date'] for d in result['days']], [self.date(1), self.date(7)])
        self.assertEqual({m['slot'] for m in result['days'][0]['meals']}, {'lunch', 'dinner'})
        for day in result['days']:
            for meal in day['meals']:
                self.assertEqual(meal['kcal'], 80)
                self.assertEqual([(i['name'], i['grams']) for i in meal['items']], [('Alimento sintetico', 80)])

    def test_skipped_modified_or_orphan_entries_are_not_presumed(self):
        for ago, action in [(1, 'skip'), (2, 'entries')]:
            pair = self.plan(ago)
            body = dict(pair)
            if action == 'entries': body.update(food=self.items[0]['food'], grams=90)
            response = self.client.post('/api/diary/' + action, json=body, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
        self.plan(3)
        with self.app.connect() as db:
            db.execute("INSERT INTO diary_entry(user_id,date,slot,food,grams,units,origin,created,updated) VALUES(?,?,'lunch',?,80,NULL,'manual',0,0)",
                       (self.user, self.date(3), json.dumps(self.items[0]['food'])))
        for ago in (1, 2, 3):
            with self.subTest(ago=ago): self.assertIs(self.meal(self.date(ago)).get('presumed'), False)
        self.assertEqual(self.pending()['count'], 0)

    def test_open_draft_excludes_meal_closed_draft_does_not(self):
        import meal_drafts
        self.plan()
        with self.app.connect() as db: meal_drafts.get(db, self.user, self.profile, self.date(1), 'lunch')
        self.assertIs(self.meal(self.date(1)).get('presumed'), False)
        self.assertEqual(self.pending()['count'], 0)
        with self.app.connect() as db:
            db.execute("UPDATE meal_draft SET status='discarded' WHERE user_id=?", (self.user,))
        self.assertIs(self.meal(self.date(1)).get('presumed'), True)
        self.assertEqual(self.pending()['count'], 1)

    def test_inactive_or_absent_plan_is_not_presumed(self):
        self.plan()
        with self.app.connect() as db: db.execute("UPDATE week_plan SET status='superseded' WHERE user_id=?", (self.user,))
        self.assertIs(self.meal(self.date(1)).get('presumed'), False)
        self.assertEqual(self.pending()['count'], 0)

    def test_day_week_pending_and_energy_gets_do_not_write(self):
        self.plan()
        before = self.snapshot(); connections = []
        real_connect = self.app.connect
        @contextlib.contextmanager
        def tracked_connect():
            db = real_connect(); initial = db.total_changes
            try:
                with db: yield db
            finally:
                connections.append((initial, db.total_changes)); db.close()
        with patch.object(self.app, 'connect', side_effect=tracked_connect):
            for path, params in [('/api/day', {'date': self.date(1)}), ('/api/week', {'start': '2026-10-05'}),
                                 ('/api/diary/pending', {}), ('/api/progress/energy', {'start': '2026-10-05'})]:
                with self.subTest(path=path):
                    response = self.client.get(path, params=params)
                    self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(connections)
        self.assertTrue(all(a == b for a, b in connections), connections)
        self.assertEqual(before, self.snapshot())

    def test_week_remaining_excludes_presumed_only(self):
        self.plan(1); self.plan(0)
        with self.app.connect() as db:
            value = self.app.diary.week_view(db, self.user, self.profile, '2026-10-05')
        self.assertEqual(value['budget']['kcal_remaining_planned'], 80)
        self.assertEqual(value['budget']['kcal_eaten'], 80)

    def test_confirm_all_three_and_idempotence(self):
        pairs = [self.plan(ago) for ago in (1, 2, 3)]
        self.assertEqual(self.pending()['count'], 3)
        response = self.confirm_all(pairs)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(result['confirmed']), 3); self.assertEqual(result['skipped'], [])
        self.assertEqual(result['pending'], self.pending()); self.assertEqual(result['pending']['count'], 0)
        for pair in pairs: self.assertEqual(self.meal(pair['date'])['state'], 'as_planned')
        before = self.snapshot()
        again = self.confirm_all(pairs)
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()['confirmed'], []); self.assertEqual(len(again.json()['skipped']), 3)
        self.assertEqual(before, self.snapshot())

    def test_concurrent_registration_is_skipped_without_overwrite(self):
        pairs = [self.plan(ago) for ago in (1, 2, 3)]
        self.assertEqual(self.pending()['count'], 3)
        self.assertEqual(self.client.post('/api/diary/entries', json=dict(pairs[0], food=self.items[0]['food'], grams=90), headers=self.headers).status_code, 200)
        response = self.confirm_all(pairs)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(result['confirmed']), 2)
        self.assertEqual([(r['date'], r['slot']) for r in result['skipped']], [(pairs[0]['date'], 'lunch')])
        self.assertEqual(self.meal(pairs[0]['date'])['state'], 'modified')
        self.assertEqual(self.meal(pairs[0]['date'])['eaten']['kcal'], 90)

    def test_invalid_dates_rollback_whole_request_regardless_of_order(self):
        pair = self.plan()
        for ago in (0, -1, 8):
            invalid = dict(date=self.date(ago), slot='lunch')
            for pairs in ([pair, invalid], [invalid, pair]):
                with self.subTest(ago=ago, pairs=pairs):
                    before = self.snapshot()
                    response = self.confirm_all(pairs)
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(before, self.snapshot())

    def test_authentication_and_csrf(self):
        pair = self.plan(); outsider = TestClient(self.app.app)
        self.assertEqual(outsider.get('/api/diary/pending').status_code, 401)
        self.assertEqual(self.confirm_all([pair], client=outsider, headers={}).status_code, 401)
        before = self.snapshot()
        self.assertEqual(self.confirm_all([pair], headers={}).status_code, 403)
        self.assertEqual(before, self.snapshot())

    def test_pending_and_confirmation_are_owner_scoped(self):
        pair = self.plan()
        other, _, _, headers = self.account('synthetic_other')
        before = self.snapshot()
        self.assertEqual(self.pending(other)['count'], 0)
        # The unspecified status for a never-planned meal is intentionally not fixed.
        response = self.confirm_all([pair], client=other, headers=headers)
        if response.status_code == 200: self.assertEqual(response.json()['confirmed'], [])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.pending()['count'], 1)

    def test_applying_new_week_keeps_past_presumed_plan_and_intake(self):
        pair = self.plan(); before = self.meal(pair['date'])
        days = [dict(date=(dt.date(2026, 10, 5) + dt.timedelta(days=n)).isoformat(),
                     selections=[dict(meal='lunch', source='CREA', food_id='synthetic', grams=160)]) for n in range(7)]
        with self.app.connect() as db:
            self.app.diary.apply_plan(db, self.user, self.profile, dict(week_start='2026-10-05', mode='free', run_id='1'),
                                      dict(id=1, role='best', days=days), dict(plan_id=1, scope='week'))
        after = self.meal(pair['date'])
        self.assertEqual(after['planned']['items'], before['planned']['items'])
        self.assertIs(after.get('presumed'), True)
        self.assertEqual(after['eaten'], before['eaten'])

    def test_rebalance_future_correction_keeps_past_presumed(self):
        import meal_rebalance
        pair = self.plan(); self.plan(-1)
        before = self.meal(pair['date'])
        future = self.date(-1)
        with self.app.connect() as db:
            proposal = dict(state=meal_rebalance.fingerprint(db, self.user, self.profile), start='2026-10-05',
                            result=dict(status='full', estimate=dict(date=self.date(0), slot='dinner', from_diary=True),
                                        budget=dict(correction_kcal=80), days=[dict(date=future, changes=[dict(slot='lunch')], reduction_kcal=80)],
                                        _plan=dict(days=[dict(date=future, selections=[dict(meal='lunch', source='CREA', food_id='synthetic', grams=40)])])))
            result = meal_rebalance.decide(db, self.user, self.profile, 'synthetic-rebalance', proposal, 'apply')
            self.assertEqual(result['changed_days'], [future])
        after = self.meal(pair['date'])
        self.assertIs(after.get('presumed'), True)
        self.assertEqual(after['planned'], before['planned']); self.assertEqual(after['eaten'], before['eaten'])

    def test_energy_balance_counts_presumed_with_sufficient_health_coverage(self):
        import progress_dashboard
        for slot in self.app.diary.SLOTS: self.plan(1, slot)
        with self.app.connect() as db:
            week = db.execute("SELECT id,day_context FROM week_plan WHERE user_id=? AND week_start='2026-10-05'", (self.user,)).fetchone()
            contexts = json.loads(week['day_context']); contexts[self.date(1)] = dict(scope='full_day_planned_meals')
            db.execute('UPDATE week_plan SET day_context=? WHERE id=?', (json.dumps(contexts), week['id']))
            report = dict(daily=[dict(date=self.date(1), total_estimated_kcal=1000, usable_for_baseline=True, resting_coverage_fraction=.95)])
            days = progress_dashboard.energy_view(db, self.user, self.profile, '2026-10-05', report, TODAY)['days']
        day = next(d for d in days if d['date'] == self.date(1))
        self.assertEqual(day.get('presumed_slots'), 5)
        self.assertEqual(day['registered_intake'], dict(min=400, max=400))
        self.assertEqual(day['balance'], dict(min=-600, max=-600))
        self.assertTrue(day['diary_complete'])
        self.assertEqual(day['logged_slots'], 0)
        # The existing health sufficiency rule must still prevent a balance.
        report['daily'][0]['usable_for_baseline'] = False
        with self.app.connect() as db:
            days = progress_dashboard.energy_view(db, self.user, self.profile, '2026-10-05', report, TODAY)['days']
        self.assertIsNone(next(d for d in days if d['date'] == self.date(1))['balance'])

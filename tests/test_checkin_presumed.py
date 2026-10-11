"""T-003: contratto backend del check-in, con soli dati sintetici."""
import contextlib
import copy
import datetime as dt
import json
from unittest.mock import patch

import progress_analysis as analysis
import progress_recalibration as recalibration
from daily_meals import defaults
import test_presumed_meals as base

TODAY = dt.date(2026, 10, 12)
UNSET = object()


class CheckinPresumedTests(base.PresumedMealsTests):
    def setUp(self):
        super().setUp()
        self.patches.enter_context(patch.object(self.app.diary, 'local_today', return_value=TODAY))
        self.patches.enter_context(patch.object(self.app.diary, 'resolve_food', side_effect=lambda ref, profile: dict(
            food=ref, name='Pasto sintetico', source_label='Fixture',
            per_100g=dict(kcal=450, protein_g=20, fat_g=15, carbs_available_g=58.75))))
        self.profile['daily_meals'] = defaults(True)
        self.profile['daily_meals']['targets_demo'] = False
        self.profile['energy_balance_target_kcal'] = 0
        with self.app.connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(self.profile), self.user))
        self.report = dict(version='synthetic-checkin', measures={}, weight_history=[],
                           scenarios=dict(status='available'), daily=[])
        self.patches.enter_context(patch.object(self.app, 'load_health_report', side_effect=lambda *a: copy.deepcopy(self.report)))
        self.patches.enter_context(patch.object(self.app, 'health_updating', return_value=False))

    def date(self, ago):
        return (TODAY - dt.timedelta(days=ago)).isoformat()

    def seed_days(self, ages, confirmed=False, user=None):
        for ago in ages:
            for slot in self.app.diary.SLOTS:
                pair = self.plan(ago, slot, user=user)
                if confirmed:
                    with self.app.connect() as db:
                        self.app.diary.diary_mutation(db, self.user if user is None else user,
                                                     self.profile, 'confirm', pair)

    def calibration_data(self):
        for ago in range(1, 15):
            self.report['daily'].append(dict(date=self.date(ago), usable_for_baseline=True, total_estimated_kcal=2300))
        with self.app.connect() as db:
            for ago in range(15):
                self.app.diary.add_measurement(db, self.user, dict(date=self.date(ago), kind='weight', unit='kg', value=80))

    def checkin(self, mode=UNSET, date=None, weight=80, client=None, headers=None):
        body = dict(date=date or self.date(0), weight_kg=weight)
        if mode is not UNSET: body['presumed'] = mode
        return (client or self.client).post('/api/progress/check-in', json=body,
                                            headers=self.headers if headers is None else headers)

    def test_week_analysis_default_counts_presumed_and_explicit_false_preserves_old_behavior(self):
        self.seed_days(range(1, 8))
        with self.app.connect() as db:
            before = db.total_changes
            value = analysis.week_analysis(db, self.user, self.profile, self.date(7), TODAY)
            self.assertEqual(value['coverage']['complete_days'], 7)
            self.assertEqual(value['diet']['value'], 1)
            self.assertEqual(value['diet']['assessed_meals'], 35)
            self.assertEqual(value['kcal_average']['eaten_avg'], 1800)
            old = analysis.week_analysis(db, self.user, self.profile, self.date(7), TODAY, include_presumed=False)
            self.assertEqual(old['coverage']['complete_days'], 0)
            self.assertIsNone(old['diet']['value'])
            self.assertEqual(db.total_changes, before)

    def test_one_presumed_day_is_complete_without_changing_minimum_five_days_rule(self):
        self.seed_days([1])
        with self.app.connect() as db:
            value = analysis.week_analysis(db, self.user, self.profile, self.date(7), TODAY)
        self.assertEqual(value['coverage']['complete_days'], 1)
        self.assertEqual(value['coverage']['complete_dates'], [self.date(1)])
        self.assertEqual(value['diet']['status'], 'insufficient_data')
        self.assertIsNone(value['diet']['value'])

    def test_default_ask_returns_pending_without_any_write(self):
        self.seed_days([1, 7])
        before = self.snapshot(); changes = []; real_connect = self.app.connect
        @contextlib.contextmanager
        def tracked():
            db = real_connect(); initial = db.total_changes
            try:
                with db: yield db
            finally:
                changes.append((initial, db.total_changes)); db.close()
        with patch.object(self.app, 'connect', side_effect=tracked): response = self.checkin()
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result.get('status'), 'needs_confirmation')
        self.assertEqual(result['date'], self.date(0))
        self.assertEqual(result['pending']['count'], 10)
        self.assertEqual((result['pending']['from'], result['pending']['to']), (self.date(7), self.date(1)))
        self.assertEqual([d['date'] for d in result['pending']['days']], [self.date(1), self.date(7)])
        self.assertEqual({m['slot'] for m in result['pending']['days'][0]['meals']}, set(self.app.diary.SLOTS))
        self.assertEqual(result['pending']['days'][0]['meals'][0]['kcal'], 360)
        self.assertEqual(result['pending']['days'][0]['meals'][0]['items'][0]['name'], 'Pasto sintetico')
        self.assertTrue(changes); self.assertTrue(all(a == b for a, b in changes))
        self.assertEqual(before, self.snapshot())

    def test_historical_checkin_pending_window_uses_checkin_date(self):
        self.seed_days([15, 21, 1])
        before = self.snapshot()
        response = self.checkin(date=self.date(14))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result.get('status'), 'needs_confirmation')
        self.assertEqual((result['pending']['from'], result['pending']['to']), (self.date(21), self.date(15)))
        self.assertEqual(result['pending']['count'], 10)
        self.assertEqual([d['date'] for d in result['pending']['days']], [self.date(15), self.date(21)])
        self.assertEqual(before, self.snapshot())

    def test_old_presumed_meals_only_do_not_prompt_but_count_in_fourteen_days(self):
        self.seed_days([8, 14, 15])
        response = self.checkin()
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value.get('status'), 'done')
        self.assertEqual(value['presumed_meals'], 10)
        with self.app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM measurement WHERE user_id=?', (self.user,)).fetchone()[0], 1)

    def test_count_saves_weight_and_uses_presumed_in_progress_without_confirming_diary(self):
        self.seed_days(range(1, 15)); self.calibration_data()
        response = self.checkin('count', weight=79.9)
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value.get('status'), 'done'); self.assertEqual(value['presumed_meals'], 70)
        self.assertEqual(value['previous_week']['diet']['value'], 1)
        self.assertEqual(value['previous_week']['coverage']['complete_days'], 7)
        self.assertEqual(value['previous_week']['kcal_average']['eaten_avg'], 1800)
        with self.app.connect() as db:
            self.assertEqual(db.execute('SELECT value FROM measurement WHERE user_id=? ORDER BY id DESC LIMIT 1', (self.user,)).fetchone()[0], 79.9)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM meal_log WHERE user_id=?', (self.user,)).fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM diary_entry WHERE user_id=?', (self.user,)).fetchone()[0], 0)

    def test_after_confirm_all_ask_calculates_without_remaining_presumed(self):
        self.seed_days(range(1, 8))
        pending = self.pending()
        pairs = [dict(date=d['date'], slot=m['slot']) for d in pending['days'] for m in d['meals']]
        self.assertEqual(self.confirm_all(pairs).status_code, 200)
        response = self.checkin('ask')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json().get('status'), 'done')
        self.assertEqual(response.json()['presumed_meals'], 0)

    def test_no_presumed_retains_current_checkin_with_zero_count(self):
        self.seed_days(range(1, 8), confirmed=True)
        response = self.checkin()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json().get('status'), 'done')
        self.assertEqual(response.json()['presumed_meals'], 0)
        self.assertEqual(response.json()['previous_week']['diet']['value'], 1)

    def test_recalibration_proposal_identical_for_presumed_and_confirmed(self):
        self.seed_days(range(1, 15)); self.calibration_data()
        with self.app.connect() as db:
            values = self.app.measurement_values(db, self.user)
            # Savepoint isolates proposal persistence when comparing identical inputs.
            db.execute('SAVEPOINT presumed_proposal')
            presumed = recalibration.make_proposal(db, self.user, self.profile, self.report, values, TODAY, TODAY)
            db.execute('ROLLBACK TO presumed_proposal'); db.execute('RELEASE presumed_proposal')
            for ago in range(1, 15):
                for slot in self.app.diary.SLOTS:
                    self.app.diary.diary_mutation(db, self.user, self.profile, 'confirm', dict(date=self.date(ago), slot=slot))
            confirmed = recalibration.make_proposal(db, self.user, self.profile, self.report, values, TODAY, TODAY)
        self.assertEqual(confirmed['status'], 'available', confirmed)
        self.assertEqual(presumed['status'], 'available', presumed)
        left = copy.deepcopy(presumed['proposal']); right = copy.deepcopy(confirmed['proposal'])
        # IDs and fingerprints legitimately change when diary confirmations are written.
        for value in (left, right):
            value.pop('id'); value.pop('state_token')
        self.assertEqual(left, right)

    def test_invalid_mode_is_422_and_does_not_write(self):
        self.seed_days([1])
        for mode in ('invalid', '', None, True, 7, [], {}):
            with self.subTest(mode=mode):
                before = self.snapshot(); response = self.checkin(mode)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(before, self.snapshot())

    def test_invalid_weight_is_validated_before_confirmation_prompt(self):
        self.seed_days([1])
        for weight in (None, True, '80', 0, -1, 501):
            with self.subTest(weight=weight):
                before = self.snapshot(); response = self.checkin(weight=weight)
                # Existing weight validation keeps its 400 (decision of 11 Oct); it must run before the prompt.
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(before, self.snapshot())

    def test_date_validation_authentication_and_csrf_remain_unchanged(self):
        from fastapi.testclient import TestClient
        before = self.snapshot()
        for date in ('invalid', self.date(1), self.date(-7)):
            self.assertEqual(self.checkin(date=date).status_code, 400)
        self.assertEqual(self.checkin(client=TestClient(self.app.app), headers={}).status_code, 401)
        self.assertEqual(self.checkin(headers={}).status_code, 403)
        self.assertEqual(before, self.snapshot())
        # The valid path still requires the new response status.
        self.assertEqual(self.checkin().json().get('status'), 'done')

    def test_user_does_not_see_another_users_pending_or_write_their_weight(self):
        self.seed_days([1])
        other, other_id, _, headers = self.account('synthetic_checkin_other')
        response = self.checkin(client=other, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json().get('status'), 'done')
        self.assertEqual(response.json()['presumed_meals'], 0)
        with self.app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM measurement WHERE user_id=?', (self.user,)).fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM measurement WHERE user_id=?', (other_id,)).fetchone()[0], 1)
        self.assertEqual(self.checkin().json().get('status'), 'needs_confirmation')


# Reuse only the isolated synthetic fixture, not T-001's inherited test cases.
for name in vars(base.PresumedMealsTests):
    if name.startswith('test_') and name not in vars(CheckinPresumedTests):
        setattr(CheckinPresumedTests, name, None)

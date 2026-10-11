"""T-001, regressioni dalla revisione: presunti protetti nelle applicazioni di settimana e giorno, alternativa del singolo pasto ammessa, motivo per sole voci di diario."""
import unittest

import test_presumed_meals as contract


class PresumedMealsReviewTests(unittest.TestCase):
    setUp = contract.PresumedMealsTests.setUp
    account = contract.PresumedMealsTests.account
    date = contract.PresumedMealsTests.date
    plan = contract.PresumedMealsTests.plan
    view = contract.PresumedMealsTests.view
    meal = contract.PresumedMealsTests.meal
    pending = contract.PresumedMealsTests.pending
    confirm_all = contract.PresumedMealsTests.confirm_all

    def apply(self, date, scope, slot=None):
        day = dict(date=date, selections=[dict(meal='lunch', source='CREA', food_id='synthetic', grams=160)])
        data = dict(plan_id=1, scope=scope, date=date, **(dict(slot=slot) if slot else {}))
        with self.app.connect() as db:
            return self.app.diary.apply_plan(db, self.user, self.profile, dict(mode='free', run_id='1'), dict(id=1, role='best', **day), data)

    def test_day_scope_keeps_past_presumed(self):
        pair = self.plan(); before = self.meal(pair['date'])
        self.apply(pair['date'], 'day')
        after = self.meal(pair['date'])
        self.assertIs(after['presumed'], True)
        self.assertEqual(after['planned']['items'], before['planned']['items'])
        self.assertEqual(after['eaten'], before['eaten'])

    def test_meal_scope_alternative_is_an_explicit_choice_and_replaces_presumed(self):
        pair = self.plan()
        self.apply(pair['date'], 'meal', 'lunch')
        after = self.meal(pair['date'])
        self.assertIs(after['presumed'], True)
        self.assertEqual(after['planned']['items'][0]['grams'], 160)

    def test_diary_entries_without_logged_state_are_not_presumed_reason(self):
        pair = self.plan()
        with self.app.connect() as db:
            db.execute('INSERT INTO diary_entry(user_id,date,slot,food,grams,units,origin) VALUES(?,?,?,?,?,?,?)',
                       (self.user, pair['date'], 'lunch', '{"source":"CREA","id":"synthetic"}', 50, None, 'manual'))
        response = self.confirm_all([pair])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['skipped'], [dict(pair, reason='not_presumed')])
        self.assertEqual(response.json()['confirmed'], [])


if __name__ == '__main__':
    unittest.main()

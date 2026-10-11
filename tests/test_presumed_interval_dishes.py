"""T-005: pasti presunti con piatti a intervallo (DIARY-01)."""
import copy
import datetime as dt
import json
from unittest.mock import patch

import progress_analysis as analysis
import progress_recalibration as recalibration
import test_checkin_presumed as checkin_base

TODAY = dt.date(2026, 10, 12)


class PresumedIntervalDishesTests(checkin_base.CheckinPresumedTests):
    def setUp(self):
        super().setUp()
        self.dish_id = 'dish:synthetic_interval'
        self.dish = dict(
            food_id=self.dish_id,
            title='Piatto sintetico a intervallo',
            nutrients=dict(
                kcal=dict(min=500.0, max=800.0),
                protein_g=dict(min=20.0, max=35.0),
                fat_g=dict(min=10.0, max=25.0),
                carbs_available_g=dict(min=50.0, max=90.0),
            ),
            provenance=dict(registration='planned_dish_estimate', source='dish_estimate'),
        )
        self.profile.setdefault('_dish_estimates', {})[self.dish_id] = self.dish
        with self.app.connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(self.profile), self.user))

        def resolve_with_dish(ref, profile):
            if isinstance(ref, dict) and ref.get('source') == 'dish_estimate':
                dish = (profile or {}).get('_dish_estimates', {}).get(ref.get('id'))
                if dish:
                    return dict(
                        food=ref,
                        name=dish.get('title', 'Piatto stimato'),
                        brand=None,
                        source_label='stima a intervallo',
                        unit_g=None,
                        composition_provenance=None,
                        nutrient_ranges=copy.deepcopy(dish['nutrients']),
                        per_100g={n: sum(dish['nutrients'][n].values()) / 2 for n in (
                            'kcal', 'protein_g', 'fat_g', 'carbs_available_g')},
                    )
            return dict(
                food=ref, name='Pasto sintetico', source_label='Fixture',
                per_100g=dict(kcal=450, protein_g=20, fat_g=15, carbs_available_g=58.75),
            )

        self.patches.enter_context(patch.object(self.app.diary, 'resolve_food', side_effect=resolve_with_dish))

    def plan_interval_meal(self, ago=1, slot='lunch'):
        date = self.date(ago)
        start = (dt.date.fromisoformat(date) - dt.timedelta(days=dt.date.fromisoformat(date).weekday())).isoformat()
        items = [dict(food=dict(source='dish_estimate', id=self.dish_id), grams=100, units=None)]
        with self.app.connect() as db:
            week = db.execute(
                "SELECT id FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",
                (self.user, start)
            ).fetchone()
            if not week:
                week_id = db.execute(
                    "INSERT INTO week_plan(user_id,week_start,mode,status,created,targets,day_context) VALUES(?,?,'free','active',0,?,?)",
                    (self.user, start, json.dumps(self.profile['targets']), '{}')
                ).lastrowid
            else:
                week_id = week[0]
            existing = db.execute(
                "SELECT id FROM planned_meal WHERE week_plan_id=? AND date=? AND slot=?",
                (week_id, date, slot)
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE planned_meal SET items=?, role='best', status='chosen' WHERE id=?",
                    (json.dumps(items), existing[0])
                )
            else:
                db.execute(
                    "INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status) VALUES(?,?,?,?,'best','chosen')",
                    (week_id, date, slot, json.dumps(items))
                )
        return dict(date=date, slot=slot)

    def test_day_view_presumed_interval_matches_confirmed_shape(self):
        target_date = self.date(2)
        # Seed the other slots as normal planned meals
        for slot in self.app.diary.SLOTS:
            if slot != 'lunch':
                self.plan(ago=2, slot=slot)
        # Plan the interval dish for lunch
        self.plan_interval_meal(ago=2, slot='lunch')

        with self.app.connect() as db:
            before_changes = db.total_changes
            presumed_view = self.app.diary.day_view(db, self.user, self.profile, target_date)
            # Ensure GET day_view does not write anything
            self.assertEqual(db.total_changes, before_changes)

        presumed_lunch = next(m for m in presumed_view['meals'] if m['slot'] == 'lunch')
        self.assertTrue(presumed_lunch['presumed'])
        self.assertIsNotNone(presumed_lunch['planned']['nutrient_ranges'])

        # Now confirm the lunch interval dish
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db, self.user, self.profile, 'confirm', dict(date=target_date, slot='lunch'))
            confirmed_view = self.app.diary.day_view(db, self.user, self.profile, target_date)

        confirmed_lunch = next(m for m in confirmed_view['meals'] if m['slot'] == 'lunch')
        self.assertFalse(confirmed_lunch['presumed'])

        # Both presumed and confirmed lunch must have identical eaten and eaten_range shapes
        self.assertEqual(presumed_lunch['eaten'], confirmed_lunch['eaten'])
        self.assertEqual(presumed_lunch['eaten_range'], confirmed_lunch['eaten_range'])
        self.assertIsNone(presumed_lunch['eaten']['kcal'])
        self.assertIsNotNone(presumed_lunch['eaten_range'])

        # Totals eaten must have identical shape (all KEYS are None due to interval estimate)
        self.assertEqual(presumed_view['totals']['eaten'], confirmed_view['totals']['eaten'])
        for key in ('kcal', 'protein_g', 'fat_g', 'carbs_available_g'):
            self.assertIsNone(presumed_view['totals']['eaten'][key])

    def test_make_proposal_outcome_identical_for_presumed_and_confirmed_interval(self):
        # 14 days of data, 1 interval dish on day 2 lunch
        self.seed_days(range(1, 15))
        self.plan_interval_meal(ago=2, slot='lunch')
        self.calibration_data()

        with self.app.connect() as db:
            values = self.app.measurement_values(db, self.user)
            db.execute('SAVEPOINT test_interval_presumed')
            presumed = recalibration.make_proposal(db, self.user, self.profile, self.report, values, TODAY, TODAY)
            db.execute('ROLLBACK TO test_interval_presumed')
            db.execute('RELEASE test_interval_presumed')

            # Confirm all meals including the interval lunch
            for ago in range(1, 15):
                for slot in self.app.diary.SLOTS:
                    self.app.diary.diary_mutation(db, self.user, self.profile, 'confirm', dict(date=self.date(ago), slot=slot))

            confirmed = recalibration.make_proposal(db, self.user, self.profile, self.report, values, TODAY, TODAY)

        # Both must produce the exact same outcome (status and reason)
        self.assertEqual(presumed['status'], confirmed['status'])
        self.assertEqual(presumed.get('reason'), confirmed.get('reason'))
        if presumed['status'] == 'available':
            left = copy.deepcopy(presumed['proposal'])
            right = copy.deepcopy(confirmed['proposal'])
            for v in (left, right):
                v.pop('id', None)
                v.pop('state_token', None)
            self.assertEqual(left, right)

    def test_presumed_meal_without_interval_remains_unchanged(self):
        # Normal meal without interval has concrete eaten numbers when presumed
        target_date = self.date(1)
        self.plan(ago=1, slot='lunch')
        with self.app.connect() as db:
            view = self.app.diary.day_view(db, self.user, self.profile, target_date)
        lunch = next(m for m in view['meals'] if m['slot'] == 'lunch')
        self.assertTrue(lunch['presumed'])
        self.assertIsNone(lunch['eaten_range'])
        self.assertIsNotNone(lunch['eaten']['kcal'])
        self.assertEqual(lunch['eaten']['kcal'], 360.0)

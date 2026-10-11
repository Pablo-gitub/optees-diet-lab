"""Verifiche aggiuntive della revisione backend T-003."""
import datetime as dt
from unittest.mock import patch
import test_checkin_presumed as base
import progress_analysis as analysis


class CheckinReferenceTests(base.CheckinPresumedTests):
    def test_week_analysis_uses_reference_date_even_when_wall_clock_is_later(self):
        self.seed_days([0, -1])
        with patch.object(self.app.diary, 'local_today', return_value=base.TODAY + dt.timedelta(days=7)), self.app.connect() as db:
            value = analysis.week_analysis(db, self.user, self.profile, self.date(0), base.TODAY)
        self.assertTrue(all(not m['presumed'] for d in value['days'] for m in d['meals']))
        self.assertTrue(all(d['totals']['eaten'] is None for d in value['days']))

    def test_pending_and_is_presumed_use_explicit_reference_date(self):
        self.seed_days([1, 7, 8, 0])
        before = self.snapshot()
        with patch.object(self.app.diary, 'local_today', return_value=base.TODAY + dt.timedelta(days=30)), self.app.connect() as db:
            date_reference = self.app.diary.pending_presumed(db, self.user, self.profile, as_of=base.TODAY)
            string_reference = self.app.diary.pending_presumed(db, self.user, self.profile, as_of=self.date(0))
            self.assertFalse(self.app.diary.is_presumed(db, self.user, self.date(0), 'lunch', as_of=base.TODAY))
            self.assertTrue(self.app.diary.is_presumed(db, self.user, self.date(1), 'lunch', as_of=base.TODAY))
        self.assertEqual(date_reference, string_reference)
        self.assertEqual(date_reference['count'], 10)
        self.assertEqual([d['date'] for d in date_reference['days']], [self.date(1), self.date(7)])
        self.assertEqual(before, self.snapshot())

    def test_ask_has_no_write_even_with_calibration_data_otherwise_eligible(self):
        self.seed_days(range(1, 15)); self.calibration_data()
        before = self.snapshot()
        response = self.checkin('ask')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'needs_confirmation')
        self.assertEqual(response.json()['pending']['count'], 35)
        self.assertEqual(before, self.snapshot())

    def test_invalid_weight_and_measurement_share_validation_without_writes(self):
        self.seed_days([1]); before = self.snapshot()
        for weight in (None, True, '80', 0, 501):
            with self.subTest(weight=weight), self.app.connect() as db:
                initial = db.total_changes
                with self.assertRaises(self.app.diary.DomainError) as error:
                    self.app.diary.add_measurement(db, self.user, dict(date=self.date(0), kind='weight', value=weight, unit='kg'))
                response = self.checkin(weight=weight)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['detail'], str(error.exception))
                self.assertEqual(db.total_changes, initial)
        self.assertEqual(before, self.snapshot())


for name in vars(base.CheckinPresumedTests):
    if name.startswith('test_') and name not in vars(CheckinReferenceTests):
        setattr(CheckinReferenceTests, name, None)

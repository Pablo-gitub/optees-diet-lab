import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from daily_meals import defaults
from target_validation import target_warnings, profile_target_warnings


class TargetValidationTests(unittest.TestCase):
    def test_demo_targets_are_consistent(self):
        main = json.loads((ROOT / 'config/demo-diet-day.json').read_text())['main_meals_targets']
        self.assertEqual(target_warnings(main), [])
        self.assertEqual(target_warnings(defaults()['targets']), [])

    def test_legacy_targets_warn_without_mutation(self):
        targets = defaults()['targets']
        targets['carbs_available_g_100g']['target'] = 180
        before = copy.deepcopy(targets)
        warning = target_warnings(targets)[0]
        self.assertEqual(warning['code'], 'targets_inconsistent')
        self.assertEqual(warning['macro_kcal'], 1580)
        self.assertEqual(warning['kcal_target'], 1800)
        self.assertEqual(targets, before)

    def test_ten_percent_boundary_and_active_scope(self):
        targets = defaults()['targets']
        targets['kcal_100g']['target'] = 2000
        self.assertEqual(target_warnings(targets), [])
        targets['kcal_100g']['target'] = 2001
        profile = dict(targets=defaults()['targets'], daily_meals=dict(enabled=True, targets=targets))
        self.assertEqual(profile_target_warnings(profile)[0]['scope'], 'daily')
        profile['daily_meals']['enabled'] = False
        self.assertEqual(profile_target_warnings(profile), [])

    def test_invalid_targets_rejected(self):
        for value in [0, True, float('nan'), float('inf')]:
            targets = defaults()['targets']
            targets['kcal_100g']['target'] = value
            with self.assertRaises(ValueError):
                target_warnings(targets)

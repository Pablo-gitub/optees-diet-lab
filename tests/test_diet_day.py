import importlib.util
import json
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('diet', ROOT / 'scripts/plan_diet_day.py')
diet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diet)


class DietTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'config/demo-diet-day.json').read_text())
        self.foods = diet.load_foods()

    def solve(self):
        problem, choices, slots = diet.formulate(self.config, self.foods)
        rows = problem['constraints']
        lower = [r['rhs'] if r['relation'] in ['>=', '='] else -np.inf for r in rows]
        upper = [r['rhs'] if r['relation'] in ['<=', '='] else np.inf for r in rows]
        result = milp(
            np.array(problem['objective']['coefficients']),
            integrality=[v['integrality'] != 'C' for v in problem['variables']],
            bounds=Bounds([v['lb'] for v in problem['variables']], [v['ub'] for v in problem['variables']]),
            constraints=LinearConstraint([r['coefficients'] for r in rows], lower, upper),
        )
        return result, choices, slots

    def test_training_schedule_and_allowed_groups(self):
        result, choices, slots = self.solve()
        self.assertTrue(result.success)
        self.assertEqual(slots, {'lunch': 'A', 'dinner': 'O'})
        chosen = [c for c in choices if result.x[c['y']] > 0.5]
        for meal in slots:
            for group in range(4):
                self.assertEqual(sum(c['meal'] == meal and c['group'] == group for c in chosen), 1)
        self.assertFalse(any(c['food_id'] in diet.PROTEIN for c in choices if c['meal'] == 'lunch'))
        self.assertFalse(any(c['food_id'] == '006515' for c in choices if c['meal'] == 'lunch' and c['group'] == 1))
        self.assertFalse(any(c['food_id'] in ['007120', '181100'] for c in choices))

    def test_exclusions_can_make_problem_infeasible_without_relaxing(self):
        self.config['excluded_crea_ids'] = diet.STARCH
        result, _, _ = self.solve()
        self.assertEqual(result.status, 2)

    def test_unimplemented_alternative_blocks_day(self):
        schedule = {'weeks': [[{'lunch': 'B oppure UNKNOWN', 'dinner': 'C'}]]}
        rules = diet.load_rules(self.config)
        with (
            patch.object(diet, 'load_rules', return_value=rules),
            patch.object(diet.json, 'loads', return_value=schedule),
        ):
            with self.assertRaisesRegex(ValueError, 'not yet verified'):
                diet.formulate(self.config, self.foods)

    def test_alternatives_are_exclusive_and_inactive_portions_zero(self):
        self.config['day_index'] = 11  # G oppure A / F oppure D
        result, choices, slots = self.solve()
        self.assertTrue(result.success)
        for meal in slots:
            active = {
                (c['combination'], c['branch_index']) for c in choices if c['meal'] == meal and result.x[c['y']] > 0.5
            }
            self.assertEqual(len(active), 1)
        for c in choices:
            if result.x[c['y']] < 0.5:
                self.assertAlmostEqual(result.x[c['q']], 0)

    def test_local_feasibility_does_not_imply_global_feasibility(self):
        self.config['day_index'] = 10  # C / C
        self.config['meal_targets'] = {m: {'kcal_100g': {'min': 200, 'max': 900}} for m in ['lunch', 'dinner']}
        global_result, _, _ = self.solve()
        self.assertEqual(global_result.status, 2)
        self.config['main_meals_targets'] = {}
        local_result, _, _ = self.solve()
        self.assertTrue(local_result.success)

    def test_all_calendar_days_have_modelled_branches(self):
        for mode in ['sedentary', 'training']:
            for day in range(14):
                self.config.update(mode=mode, day_index=day)
                diet.formulate(self.config, self.foods)

    def test_modes_do_not_share_a_proteins(self):
        self.config['mode'] = 'sedentary'
        _, choices, _ = diet.formulate(self.config, self.foods)
        self.assertTrue(any(c['food_id'] == '106500' for c in choices if c['meal'] == 'lunch'))

    def test_free_mode_and_invalid_targets(self):
        self.config['mode'] = 'free'
        result, _, _ = self.solve()
        self.assertTrue(result.success)
        self.config['main_meals_targets']['kcal_100g']['target'] = float('nan')
        with self.assertRaises(ValueError):
            diet.formulate(self.config, self.foods)


if __name__ == '__main__':
    unittest.main()

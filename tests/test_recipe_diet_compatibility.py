import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from recipe_diet_compatibility import assess, meal_options, classify, match_branch


def recipe(*groups):
    return dict(
        id='test',
        title='Test',
        ingredients=[
            dict(
                key=str(i),
                name=group,
                grams_per_reference_portion=50,
                candidates=[dict(source='test', id=str(i), reviewed=True, state_checked=True)],
            )
            for i, group in enumerate(groups)
        ],
    )


def branch(*roles):
    return dict(
        id='test',
        required_roles=[dict(name=name, groups=groups, one_food_only=name != 'verdure') for name, groups in roles],
        condiments=['oil', 'water'],
    )


class CompatibilityTests(unittest.TestCase):
    def check(self, groups, branches):
        r = recipe(*groups)
        mapping = {'foods': {'test:' + str(i): g for i, g in enumerate(groups)}}
        return assess(r, 'training', 'A', {'training': {'A': branches}}, mapping)

    def test_complete_mixed_dish_covers_roles_and_counts_all_ingredients(self):
        result = self.check(
            ['pasta', 'vegetable', 'legume', 'oil', 'water'],
            [branch(('primo', ['pasta']), ('verdure', ['vegetable']), ('secondo', ['legume']))],
        )
        self.assertEqual(result['status'], 'compatible')
        self.assertEqual(len(result['ingredients']), 5)
        self.assertFalse(result['nutrition_checked'])

    def test_missing_roles_require_explicit_complements(self):
        result = self.check(
            ['pasta'], [branch(('primo', ['pasta']), ('verdure', ['vegetable']), ('secondo', ['legume']))]
        )
        self.assertEqual(result['status'], 'needs_complements')
        self.assertEqual(result['branches'][0]['missing_roles'], ['verdure', 'secondo'])

    def test_branches_cannot_be_mixed_to_accept_forbidden_ingredient(self):
        result = self.check(
            ['pasta', 'egg'],
            [
                branch(('primo', ['pasta']), ('secondo', ['legume'])),
                branch(('primo', ['potato']), ('secondo', ['egg'])),
            ],
        )
        self.assertEqual(result['status'], 'needs_review')

    def test_two_distinct_cheeses_do_not_count_as_one_choice(self):
        result = self.check(
            ['cheese', 'cheese', 'vegetable'], [branch(('secondo', ['cheese']), ('verdure', ['vegetable']))]
        )
        self.assertEqual(result['status'], 'needs_review')

    def test_multiple_vegetables_are_allowed(self):
        result = self.check(
            ['vegetable', 'vegetable', 'egg'], [branch(('secondo', ['egg']), ('verdure', ['vegetable']))]
        )
        self.assertEqual(result['status'], 'compatible')

    def test_tuna_in_brine_does_not_automatically_replace_tuna_in_oil(self):
        result = self.check(
            ['tuna_brine', 'vegetable'], [branch(('secondo', ['tuna_oil']), ('verdure', ['vegetable']))]
        )
        self.assertEqual(result['status'], 'needs_review')

    def test_unmapped_or_unreviewed_candidates_block_the_whole_ingredient(self):
        r = recipe('egg')
        r['ingredients'][0]['candidates'].append(dict(source='test', id='unknown', reviewed=True, state_checked=True))
        self.assertIsNone(classify(r, {'foods': {'test:0': 'egg'}})[0]['group'])
        r['ingredients'][0]['candidates'] = r['ingredients'][0]['candidates'][:1]
        r['ingredients'][0]['candidates'][0]['reviewed'] = False
        self.assertIsNone(classify(r, {'foods': {'test:0': 'egg'}})[0]['group'])

    def test_free_mode_does_not_read_personal_files(self):
        self.assertEqual(meal_options('free', 0, 'lunch', [recipe('egg')])['recipes'][0]['status'], 'unconstrained')

    def test_unknown_letter_and_invalid_day_fail(self):
        with self.assertRaises(ValueError):
            assess(recipe('egg'), 'training', 'UNKNOWN', {'training': {}}, {'foods': {}})
        for day in [True, -1, 14]:
            with self.assertRaises(ValueError):
                meal_options('free', day, 'lunch', [])

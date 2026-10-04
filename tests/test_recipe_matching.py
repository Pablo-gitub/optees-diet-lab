"""Tests for recipe ingredient matching, grouping, state distinction, and solver safety."""

import copy
import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from match_recipe_ingredients import (
    fold,
    singularize,
    extract_qualifiers,
    find_canonical_ingredient,
    match_crea_candidates,
    search_off_candidates,
    evaluate_quantity,
    process_ingredient,
    process_recipes,
    build_review_queue,
    build_report,
    export_solver_recipes,
    export_recipe_mappings,
    approve_canonical,
    load_dictionary,
    load_approved_mappings,
    load_crea,
    DEFAULT_DICT,
    DEFAULT_APPROVED,
    DEFAULT_CREA,
    DEFAULT_OFF,
    DEFAULT_RECIPES,
)
import calculate_recipe_nutrients as calc


class RecipeMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dictionary = load_dictionary(DEFAULT_DICT)
        cls.crea_foods = load_crea(DEFAULT_CREA)
        cls.db_off = sqlite3.connect(DEFAULT_OFF) if DEFAULT_OFF.exists() else None

    @classmethod
    def tearDownClass(cls):
        if cls.db_off:
            cls.db_off.close()

    def test_shared_approval_cannot_override_occurrence_state(self):
        approvals = load_approved_mappings(DEFAULT_APPROVED)
        for name, description in [
            ('pasta', 'Pasta, cooked'),
            ('olive oil', 'For deep frying; unused oil discarded'),
            ('garlic', 'Garlic, dried powder'),
        ]:
            ing = {
                'key': '1',
                'name': name,
                'quantity': 100,
                'unit': 'g',
                'grams_whole_recipe': 100,
                'source_nutrition_reference': {'description': description},
            }
            result = process_ingredient(
                ing, {'id': 'test:states'}, self.dictionary, approvals, self.crea_foods, self.db_off
            )
            self.assertFalse(result['reviewed'], name)

    def test_false_approval_flags_are_not_promoted(self):
        approvals = copy.deepcopy(load_approved_mappings(DEFAULT_APPROVED))
        approvals['canonical_approvals']['pasta_semola_secca']['reviewed'] = False
        ing = {'key': '1', 'name': 'pasta', 'quantity': 100, 'unit': 'g', 'grams_whole_recipe': 100}
        result = process_ingredient(ing, {'id': 'test:flags'}, self.dictionary, approvals, self.crea_foods, self.db_off)
        self.assertFalse(result['reviewed'])

    def test_estimated_weight_is_not_approved_by_mapping_export(self):
        import tempfile
        from pathlib import Path

        approvals = {
            'canonical_approvals': {},
            'recipe_overrides': {
                'test:qty': {'1': {'source': 'CREA', 'id': '005000', 'reviewed': True, 'state_checked': True}}
            },
        }
        ing = {'key': '1', 'name': 'garlic', 'quantity': 2, 'unit': 'clove', 'grams_whole_recipe': None}
        result = process_ingredient(ing, {'id': 'test:qty'}, self.dictionary, approvals, self.crea_foods, self.db_off)
        self.assertEqual(result['quantity_status'], 'proposed_conversion')
        with tempfile.TemporaryDirectory() as temp:
            export_recipe_mappings([{'id': 'test:qty', 'ingredients': [result]}], Path(temp))
            mapping = json.loads((Path(temp) / 'test_qty.json').read_text())
            self.assertFalse(mapping['1']['reviewed'])

    def test_text_folding_and_singularization(self):
        """Test normalization handles case, accents, and English plurals."""
        self.assertEqual(fold("Cipolle, crude"), "cipolle, crude")
        self.assertEqual(fold("Café"), "cafe")
        self.assertEqual(singularize("tomatoes"), "tomato")
        self.assertEqual(singularize("potatoes"), "potato")
        self.assertEqual(singularize("onions"), "onion")
        self.assertEqual(singularize("eggs"), "egg")
        self.assertEqual(singularize("cloves"), "clove")

    def test_qualifier_extraction(self):
        """Test extraction of cooking, processing, and grain state qualifiers."""
        quals_dict = self.dictionary['qualifiers']

        # Raw vs Cooked
        q1 = extract_qualifiers("fresh raw chicken breast", None, "", quals_dict)
        self.assertEqual(q1['cooking_state'], 'raw')

        q2 = extract_qualifiers("boiled potatoes", "cooked in salted water", "", quals_dict)
        self.assertEqual(q2['cooking_state'], 'cooked')

        # Canned / Drained vs Dry
        q3 = extract_qualifiers("canned white beans, drained", None, "", quals_dict)
        self.assertEqual(q3['processing_state'], 'canned')
        self.assertEqual(q3['processing_state_evidence'], ['canned', 'drained'])

        # Whole vs Refined
        q4 = extract_qualifiers("wholemeal pasta", None, "", quals_dict)
        self.assertEqual(q4['grain_type'], 'whole')

        q5 = extract_qualifiers("white plain flour", None, "", quals_dict)
        self.assertEqual(q5['grain_type'], 'refined')

    def test_canonical_grouping_and_synonyms(self):
        """Test equivalent ingredient phrases map to the same canonical ID."""
        # Onion variations
        for phrase in ["onion", "Onion", "Onions", "yellow onions", "white onion"]:
            canonical = find_canonical_ingredient({'name': phrase}, self.dictionary)
            self.assertIsNotNone(canonical, f"Failed to match canonical for: {phrase}")
            self.assertEqual(canonical['id'], 'cipolla_cruda')

        # Olive oil variations
        for phrase in ["olive oil", "Olive oil", "extra virgin olive oil", "EVOO"]:
            canonical = find_canonical_ingredient({'name': phrase}, self.dictionary)
            self.assertIsNotNone(canonical, f"Failed to match canonical for: {phrase}")
            self.assertEqual(canonical['id'], 'olio_oliva_extravergine')

        # Foodose USDA reference matching
        foodose_ing = {
            'name': 'tomatoes',
            'source_nutrition_reference': {
                'id': '170457',
                'description': 'Tomatoes, red, ripe, raw, year round average',
            },
        }
        canonical = find_canonical_ingredient(foodose_ing, self.dictionary)
        self.assertIsNotNone(canonical)
        self.assertEqual(canonical['id'], 'pomodori_freschi')

    def test_raw_vs_cooked_distinction_preserves_nutrition(self):
        """Test raw ingredients do not match cooked foods and preserve caloric density."""
        # 1. Raw rice must match raw CREA 000100 (358 kcal), NOT cooked 000105 (130 kcal)
        rice_raw = find_canonical_ingredient({'name': 'white rice'}, self.dictionary)
        quals_raw = {'cooking_state': 'raw'}
        cands_raw = match_crea_candidates(rice_raw, quals_raw, self.crea_foods)
        self.assertTrue(any(c['id'] == '000100' and c['match_type'] == 'exact' for c in cands_raw))
        self.assertFalse(any(c['id'] == '000105' and c['match_type'] == 'exact' for c in cands_raw))

        # Check kcal difference
        kcal_raw = float(self.crea_foods['000100']['kcal_100g'])
        kcal_cooked = float(self.crea_foods['000105']['kcal_100g'])
        self.assertGreater(kcal_raw, 300)
        self.assertLess(kcal_cooked, 200)

        # 2. Cooked rice MUST match cooked alternate CREA 000105
        quals_cooked = {'cooking_state': 'cooked'}
        cands_cooked = match_crea_candidates(rice_raw, quals_cooked, self.crea_foods)
        self.assertTrue(any(c['id'] == '000105' and c['match_type'] == 'exact' for c in cands_cooked))
        self.assertFalse(any(c['id'] == '000100' and c['match_type'] == 'exact' for c in cands_cooked))

    def test_canned_vs_dry_legumes_distinction(self):
        """Test canned/drained beans match canned CREA food, avoiding 3x error from dry beans."""
        beans_canned = find_canonical_ingredient({'name': 'canned white beans'}, self.dictionary)
        self.assertEqual(beans_canned['id'], 'fagioli_cannellini_scatola')
        self.assertEqual(beans_canned['crea_matches']['primary']['id'], '004210')

        beans_dry = find_canonical_ingredient({'name': 'dry white beans'}, self.dictionary)
        self.assertEqual(beans_dry['id'], 'fagioli_cannellini_secchi')
        self.assertEqual(beans_dry['crea_matches']['primary']['id'], '004200')

        # Canned beans are hydrated (~102 kcal), dry beans are concentrated (~317 kcal)
        self.assertLess(float(self.crea_foods['004210']['kcal_100g']), 150)
        self.assertGreater(float(self.crea_foods['004200']['kcal_100g']), 300)

    def test_ambiguity_detection_for_unspecified_cooking_state(self):
        """When an ingredient lacks cooking state and multiple states exist, it is flagged as ambiguous."""
        ing = {'key': '1', 'name': 'onion', 'quantity': 1, 'unit': 'piece', 'grams_whole_recipe': 100.0}
        recipe = {'id': 'test:ambiguous', 'title': 'Test'}
        # Pass empty approved mappings so it's not pre-approved
        appr_empty = {'canonical_approvals': {}, 'recipe_overrides': {}}

        res = process_ingredient(ing, recipe, self.dictionary, appr_empty, self.crea_foods, self.db_off)
        self.assertEqual(res['match_status'], 'ambiguous')
        self.assertEqual(res['confidence'], 'low')
        self.assertFalse(res['reviewed'])
        self.assertFalse(res['state_checked'])
        # Candidates list should include both raw (005300) and cooked (005305) for disambiguation
        cand_ids = [c['id'] for c in res['candidates']]
        self.assertIn('005300', cand_ids)
        self.assertIn('005305', cand_ids)

    def test_composite_and_unabsorbed_oil_flags(self):
        """Test composite ingredients and oil for frying are not automatically matched."""
        recipe = {'id': 'test:flags', 'title': 'Test Flags'}
        appr_empty = {'canonical_approvals': {}, 'recipe_overrides': {}}

        # Salt and pepper
        sp_ing = {'key': '1', 'name': 'Salt and pepper', 'quantity': 1, 'unit': 'toTaste', 'grams_whole_recipe': None}
        res_sp = process_ingredient(sp_ing, recipe, self.dictionary, appr_empty, self.crea_foods, self.db_off)
        self.assertEqual(res_sp['match_status'], 'ambiguous')
        self.assertFalse(res_sp['reviewed'])

        # Oil for frying
        fry_ing = {'key': '2', 'name': 'Oil for frying', 'quantity': 500, 'unit': 'ml', 'grams_whole_recipe': None}
        res_fry = process_ingredient(fry_ing, recipe, self.dictionary, appr_empty, self.crea_foods, self.db_off)
        self.assertEqual(res_fry['match_status'], 'needs_review')
        self.assertFalse(res_fry['reviewed'])
        self.assertIn('assorbimento', res_fry['note'].lower())

    def test_missing_data_does_not_assume_zero(self):
        """Unconverted units and unmapped foods must have grams=None and not count as zero."""
        recipe = {'id': 'test:missing', 'title': 'Test Missing'}
        appr_empty = {'canonical_approvals': {}, 'recipe_overrides': {}}

        # toTaste unit
        salt_ing = {'key': '1', 'name': 'Salt', 'quantity': None, 'unit': 'toTaste', 'grams_whole_recipe': None}
        res_salt = process_ingredient(salt_ing, recipe, self.dictionary, appr_empty, self.crea_foods, self.db_off)
        self.assertIsNone(res_salt['grams'])
        self.assertEqual(res_salt['quantity_status'], 'needs_review')

        # Unknown exotic ingredient
        exotic = {
            'key': '2',
            'name': 'Exotic moonfruit 1234',
            'quantity': 100,
            'unit': 'g',
            'grams_whole_recipe': 100.0,
        }
        res_exotic = process_ingredient(exotic, recipe, self.dictionary, appr_empty, self.crea_foods, self.db_off)
        self.assertEqual(res_exotic['match_status'], 'missing')
        self.assertEqual(res_exotic['confidence'], 'none')
        self.assertIsNone(res_exotic['selected_candidate'])

    def test_reusable_approval_propagation(self):
        """Approving a canonical ingredient propagates reviewed=True across all recipes containing it."""
        mock_approved = {
            'version': '1.0',
            'canonical_approvals': {
                'aglio': {
                    'source': 'CREA',
                    'id': '005000',
                    'label': 'Aglio',
                    'reviewed': True,
                    'state_checked': True,
                    'approved_by': 'unit_test',
                }
            },
            'recipe_overrides': {},
        }

        # Process two different recipes having garlic
        rec1 = {'id': 'recipe:1', 'title': 'Recipe 1'}
        rec2 = {'id': 'recipe:2', 'title': 'Recipe 2'}
        garlic_ing = {'key': '1', 'name': 'Garlic', 'quantity': 2, 'unit': 'clove', 'grams_whole_recipe': 8.0}

        res1 = process_ingredient(garlic_ing, rec1, self.dictionary, mock_approved, self.crea_foods, self.db_off)
        res2 = process_ingredient(garlic_ing, rec2, self.dictionary, mock_approved, self.crea_foods, self.db_off)

        # Both recipes must immediately be approved
        self.assertEqual(res1['match_status'], 'approved')
        self.assertTrue(res1['reviewed'])
        self.assertTrue(res1['state_checked'])
        self.assertEqual(res1['selected_candidate']['id'], '005000')

        self.assertEqual(res2['match_status'], 'approved')
        self.assertTrue(res2['reviewed'])
        self.assertTrue(res2['state_checked'])
        self.assertEqual(res2['selected_candidate']['id'], '005000')

    def test_solver_export_safety(self):
        """Unreviewed proposals are NEVER exported as reviewed=True or included in solver recipes."""
        mock_approved = copy.deepcopy(load_approved_mappings(DEFAULT_APPROVED))

        # Recipe 1: 100% approved with grams (foodose:R315)
        # Recipe 2: Has unreviewed candidate
        recipes = [
            {
                'id': 'rec:approved',
                'title': 'Approved Recipe',
                'cuisine': 'Italian',
                'source': 'test',
                'servings': 1,
                'solver_ready': True,
                'ingredients': [
                    {
                        'ingredient_key': '1',
                        'original_name': 'olive oil',
                        'canonical_name': 'Olio extravergine',
                        'grams': 10.0,
                        'selected_candidate': {
                            'source': 'CREA',
                            'id': '009210',
                            'label': 'Olio EVO',
                            'reviewed': True,
                            'state_checked': True,
                        },
                    }
                ],
            },
            {
                'id': 'rec:unreviewed',
                'title': 'Unreviewed Recipe',
                'cuisine': 'Italian',
                'source': 'test',
                'servings': 1,
                'solver_ready': False,  # Not approved
                'ingredients': [
                    {
                        'ingredient_key': '1',
                        'original_name': 'chicken breast',
                        'canonical_name': 'Pollo petto crudo',
                        'grams': 150.0,
                        'selected_candidate': {
                            'source': 'CREA',
                            'id': '106500',
                            'name': 'Pollo, petto, crudo',
                            'reviewed': False,
                            'state_checked': False,
                        },
                    }
                ],
            },
        ]

        out_solver = Path('/tmp/unit_test_solver.json')
        export_solver_recipes(recipes, out_solver)
        data = json.loads(out_solver.read_text())

        # Only approved recipe exported!
        self.assertEqual(len(data['recipes']), 1)
        self.assertEqual(data['recipes'][0]['id'], 'rec:approved')
        self.assertTrue(data['recipes'][0]['ingredients'][0]['candidates'][0]['reviewed'])
        self.assertTrue(data['recipes'][0]['ingredients'][0]['candidates'][0]['state_checked'])

    def test_nutrient_calculator_integration(self):
        """Exported approved mappings produce complete=true in calculate_recipe_nutrients.py."""
        # Use existing foodose:R315 which is approved
        approved_data = load_approved_mappings(DEFAULT_APPROVED)
        with sqlite3.connect(DEFAULT_RECIPES) as db:
            row = db.execute("SELECT payload FROM recipes WHERE id='foodose:R315'").fetchone()
            self.assertIsNotNone(row)
            recipe = json.loads(row[0])

        ing_results = []
        for ing in recipe['ingredients']:
            res = process_ingredient(ing, recipe, self.dictionary, approved_data, self.crea_foods, self.db_off)
            ing_results.append(res)

        # Build mapping format for calculate_recipe_nutrients
        mapping = {
            r['ingredient_key']: {
                'source': r['selected_candidate']['source'],
                'id': r['selected_candidate']['id'],
                'reviewed': r['reviewed'],
                'state_checked': r['state_checked'],
                'grams_override': r['grams'],
            }
            for r in ing_results
        }

        calc_result = calc.calculate(recipe, mapping)
        self.assertTrue(calc_result['complete'])
        self.assertIsNotNone(calc_result['whole_recipe']['kcal'])
        self.assertIsNotNone(calc_result['per_serving']['kcal'])
        self.assertEqual(len(calc_result['blocked']), 0)

    def test_whole_milk_ricotta_is_not_misclassified_as_wholegrain(self):
        approved = load_approved_mappings(DEFAULT_APPROVED)
        ing = {
            'key': '4',
            'name': 'ricotta',
            'quantity': 180,
            'unit': 'g',
            'grams_whole_recipe': 180,
            'source_nutrition_reference': {'description': 'Cheese, ricotta, whole milk'},
        }
        result = process_ingredient(
            ing, {'id': 'foodose:R054'}, self.dictionary, approved, self.crea_foods, self.db_off
        )
        self.assertTrue(result['reviewed'])

    def test_verified_candidate_audit_covers_all_42_and_corrects_tuna_lentils(self):
        report = json.loads((ROOT / 'data/recipe_candidate_verification.json').read_text())
        self.assertEqual(len(report['recipes']), 42)
        self.assertEqual(report['approved_count'], 24)
        self.assertEqual(report['blocked_count'], 18)
        approved = load_approved_mappings(DEFAULT_APPROVED)
        self.assertEqual(approved['recipe_overrides']['foodose:R270']['6']['id'], '004505')
        self.assertEqual(approved['recipe_overrides']['foodose:R094']['4']['id'], '123550')
        self.assertNotIn('foodose:R105', approved['recipe_overrides'])

    def test_new_food_states_and_reference_ids_do_not_collide(self):
        from collections import defaultdict

        ids = defaultdict(list)
        for key, item in self.dictionary['canonical_ingredients'].items():
            for fid in item.get('usda_ids', []):
                ids[fid].append(key)
        self.assertFalse({fid: keys for fid, keys in ids.items() if len(keys) > 1})
        for name, expected in [('silken tofu', 'tofu_morbido'), ('firm tofu', 'tofu_fresco')]:
            self.assertEqual(find_canonical_ingredient({'name': name}, self.dictionary)['id'], expected)
        tofu = find_canonical_ingredient({'name': 'silken tofu'}, self.dictionary)
        self.assertFalse(tofu.get('off_brand_candidates'))
        turkey = find_canonical_ingredient(
            {'name': 'turkey breast', 'source_nutrition_reference': {'id': '171098'}}, self.dictionary
        )
        self.assertEqual(turkey['id'], 'tacchino_petto_crudo')
        candidates = match_crea_candidates(turkey, {'cooking_state': 'raw'}, self.crea_foods)
        self.assertTrue(all(candidate['match_type'] != 'exact' for candidate in candidates))
        yeast = find_canonical_ingredient({'name': 'active dry yeast'}, self.dictionary)
        self.assertFalse(yeast.get('off_brand_candidates'))

    def test_dry_vs_compressed_yeast_distinction(self):
        """Dry yeast (360+ kcal) must not be matched to compressed fresh yeast (70 kcal)."""
        dry_y = find_canonical_ingredient({'name': 'active dry yeast'}, self.dictionary)
        self.assertEqual(dry_y['id'], 'lievito_secco')
        # CREA only has compressed yeast 503100, which must NOT be the primary match for dry yeast
        self.assertNotIn('503100', [c['id'] for c in dry_y.get('crea_matches', {}).values()])

        fresh_y = find_canonical_ingredient({'name': 'fresh yeast'}, self.dictionary)
        self.assertEqual(fresh_y['id'], 'lievito_birra')
        self.assertEqual(fresh_y['crea_matches']['primary']['id'], '503100')

    def test_liquid_stock_is_not_equated_to_concentrated_bouillon_cube(self):
        """Ready liquid stock cannot be equated to concentrated bouillon cube without review."""
        stock_ing = {'key': '1', 'name': 'vegetable stock', 'quantity': 500, 'unit': 'ml', 'grams_whole_recipe': 500.0}
        recipe = {'id': 'test:stock', 'title': 'Soup Test'}
        appr_empty = {'canonical_approvals': {}, 'recipe_overrides': {}}

        res = process_ingredient(stock_ing, recipe, self.dictionary, appr_empty, self.crea_foods, self.db_off)
        self.assertEqual(res['match_status'], 'needs_review')
        self.assertFalse(res['reviewed'])
        self.assertIn('diluizione', res['note'].lower())


if __name__ == '__main__':
    unittest.main()

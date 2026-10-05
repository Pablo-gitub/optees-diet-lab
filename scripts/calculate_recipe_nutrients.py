"""Recalculate a recipe from explicit, reviewed ingredient-to-food mappings."""

import argparse
import csv
import json
import math
import sqlite3
from pathlib import Path

from recipe_special_sources import special_food,POLICY

ROOT = Path(__file__).resolve().parents[1]
NUTRIENTS = {
    'kcal': 'kcal_100g',
    'protein_g': 'protein_g_100g',
    'fat_g': 'fat_g_100g',
    'carbs_g': 'carbs_available_g_100g',
}


def finite(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) and n >= 0 else None


def food_lookup(source, identifier):
    if source in ('condiment','stock'):return special_food(source,identifier,food_lookup)
    if source == 'CREA':
        with (ROOT / 'dataset/crea/foods.csv').open(newline='') as f:
            for row in csv.DictReader(f):
                if row['source_id'] == identifier:
                    return dict(row, nutrient_basis='per_100_g')
    elif source == 'Open Food Facts':
        with sqlite3.connect(ROOT / 'dataset/open_food_facts/catalog.sqlite') as db:
            row = db.execute('SELECT payload FROM products WHERE barcode=?', (identifier,)).fetchone()
            if row:
                return json.loads(row[0])
    raise ValueError('Food reference not found: ' + source + ':' + identifier)


def calculate(recipe, mappings, lookup=food_lookup):
    servings = finite(recipe.get('servings'))
    if servings is None or servings <= 0:
        raise ValueError('Positive base servings required')
    totals = {key: 0.0 for key in NUTRIENTS}
    missing = {key: [] for key in NUTRIENTS}
    blocked = []
    used = []
    for ingredient in recipe['ingredients']:
        key = ingredient['key']
        mapping = mappings.get(key)
        if not mapping or mapping.get('reviewed') is not True or mapping.get('state_checked') is not True:
            blocked.append({'ingredient': key, 'reason': 'mapping_or_raw_cooked_state_not_reviewed'})
            for nutrient in missing:
                missing[nutrient].append(key)
            continue
        if mapping.get('source')=='condiment':
            grams=finite(mapping.get('grams_override',ingredient.get('grams_whole_recipe')))
            if mapping.get('id')!='trace' or mapping.get('declared_kcal')!=0 or mapping.get('category')!='condimento' or (grams is None and mapping.get('quantity_status')!='trace') or (grams is not None and grams/servings>POLICY['trace_condiment']['max_g_per_serving']):
                blocked.append(dict(ingredient=key,reason='trace_condiment_policy_required'))
                for nutrient in missing:missing[nutrient].append(key)
                continue
            used.append(dict(ingredient=key,source='condiment',source_id='trace',category='condimento',grams=grams,declared_kcal=0,approximation=POLICY['trace_condiment']['note']))
            continue
        grams = finite(mapping.get('grams_override', ingredient['grams_whole_recipe']))
        if grams is None:
            blocked.append({'ingredient': key, 'reason': 'quantity_not_converted_to_grams'})
            for nutrient in missing:
                missing[nutrient].append(key)
            continue
        if mapping.get('source') == 'water':
            # Explicitly reviewed plain water; stock, milk, juices etc. cannot use this shortcut.
            used.append(dict(ingredient=key, source='water', grams=grams))
            continue
        food = special_food(mapping['source'],mapping['id'],lookup) if mapping['source']=='stock' else lookup(mapping['source'], mapping['id'])
        basis = food.get('nutrient_basis', 'per_100_g')
        if basis == 'per_100_ml':
            density = finite(mapping.get('density_g_per_ml'))
            if density is None or density <= 0:
                blocked.append({'ingredient': key, 'reason': 'liquid_density_required'})
                for nutrient in missing:
                    missing[nutrient].append(key)
                continue
            amount = grams / density
        elif basis == 'per_100_g':
            amount = grams
        else:
            blocked.append({'ingredient': key, 'reason': 'nutrient_basis_unresolved'})
            for nutrient in missing:
                missing[nutrient].append(key)
            continue
        if food.get('source_quality_errors') or any(
            f.startswith(('implausible', 'inconsistent')) for f in food.get('quality_flags', [])
        ):
            blocked.append({'ingredient': key, 'reason': 'source_quality_error'})
            for nutrient in missing:
                missing[nutrient].append(key)
            continue
        for nutrient, column in NUTRIENTS.items():
            value = finite(food.get(column))
            if value is None:
                missing[nutrient].append(key)
            else:
                totals[nutrient] += amount * value / 100
        used.append(
            dict(ingredient=key, source=mapping['source'], source_id=mapping['id'], food=food['name'], grams=grams,**{k:food[k] for k in ('dilution','approximation','category') if k in food})
        )
    complete = not blocked and all(not ids for ids in missing.values())
    return dict(
        recipe_id=recipe['id'],
        base_servings=servings,
        complete=complete,
        blocked=blocked,
        missing_by_nutrient=missing,
        whole_recipe={n: None if missing[n] else round(v, 4) for n, v in totals.items()},
        per_serving={n: None if missing[n] else round(v / servings, 4) for n, v in totals.items()},
        ingredient_sources=used,
        declared_nutrition=recipe.get('declared_nutrition'),
        diet_eligibility='not_checked',
        note='Counts all mapped ingredients as consumed; cooking losses/yield not inferred. No per-100g cooked estimate without measured final yield.',
    )


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('recipe_id')
    p.add_argument('--mapping', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    with sqlite3.connect(ROOT / 'dataset/recipes/catalog.sqlite') as db:
        row = db.execute('SELECT payload FROM recipes WHERE id=?', (a.recipe_id,)).fetchone()
    if not row:
        raise ValueError('Recipe not found')
    result = calculate(json.loads(row[0]), json.loads(a.mapping.read_text()))
    if a.output:
        a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))

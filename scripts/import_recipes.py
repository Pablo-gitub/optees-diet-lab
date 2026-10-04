"""Import two independently licensed recipe sources into an offline catalog."""

import argparse
import collections
import csv
import datetime
import hashlib
import json
import math
import sqlite3
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'dataset/recipes'
FILES = {
    'unitools/raw/recipes.json': 'https://raw.githubusercontent.com/farcrak/unitools-recipes/main/unitools-recipes-v1.json',
    'unitools/LICENSE': 'https://raw.githubusercontent.com/farcrak/unitools-recipes/main/LICENSE',
    'foodose/raw/recipes.csv': 'https://www.foodose.co/glp1-recipes/nutrition-data/recipes.csv',
    'foodose/raw/ingredients.csv': 'https://www.foodose.co/glp1-recipes/nutrition-data/ingredients.csv',
}
NUTRIENTS = ['kcal', 'protein_g', 'fat_g', 'carbs_g']


def number(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) and n >= 0 else None


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def cuisine_name(text):
    return text.removesuffix(' cuisine').strip() or 'Unspecified'


def grams(quantity, unit):
    n = number(quantity)
    return n * (1000 if unit == 'kg' else 1) if n is not None and unit in ['g', 'kg'] else None


def common(source, identifier, title, cuisine, servings, ingredients, declared):
    return dict(
        id=source + ':' + identifier,
        source=source,
        title=title,
        cuisine=cuisine,
        cuisine_id=fold(cuisine).replace(' ', '-'),
        servings=number(servings),
        ingredients=ingredients,
        declared_nutrition=declared,
        declared_nutrition_basis='per_serving',
        calculated_nutrition=None,
        ingredient_mapping_status='unreviewed',
        solver_eligible=False,
        ingredients_with_grams=sum(i['grams_whole_recipe'] is not None for i in ingredients),
        all_ingredient_masses_known=bool(ingredients) and all(i['grams_whole_recipe'] is not None for i in ingredients),
    )


def import_unitools():
    data = json.loads((BASE / 'unitools/raw/recipes.json').read_text())
    countries = {x['code']: x for x in data['countries']}
    result = []
    for r in data['recipes']:
        ingredients = []
        for index, i in enumerate(r['ingredients']):
            ingredients.append(
                dict(
                    key=str(index + 1),
                    source_ingredient_id=i['id'],
                    name=i['name']['en'],
                    quantity=i['quantity'],
                    unit=i['unit'],
                    grams_whole_recipe=grams(i['quantity'], i['unit']),
                    scaling=i.get('scaling'),
                    note=i.get('note'),
                    source_nutrition_reference=None,
                )
            )
        n = r['nutritionPerServing']
        declared = {key: number(n.get(field)) for key, field in zip(NUTRIENTS, ['calories', 'protein', 'fat', 'carbs'])}
        item = common(
            'unitools',
            r['slug'],
            r['name']['en'],
            cuisine_name(countries[r['country']]['cuisine']['en']),
            r['baseServings'],
            ingredients,
            declared,
        )
        item.update(
            country=r['country'],
            native_title=r.get('nativeName'),
            summary=r['summary']['en'],
            category=r['category'],
            total_minutes=number(r['prepMinutes']) + number(r['cookMinutes']),
            steps=[s['text']['en'] for s in r['steps']],
            source_url=data['homepage'],
            license='CC BY-SA 4.0',
            attribution=data['attribution'],
        )
        result.append(item)
    return result


def import_foodose():
    groups = collections.defaultdict(list)
    with (BASE / 'foodose/raw/ingredients.csv').open(newline='') as stream:
        for r in csv.DictReader(stream):
            groups[r['recipe_id']].append(
                dict(
                    key=r['line'],
                    name=r['ingredient'],
                    quantity=r['amount'],
                    unit=r['unit'],
                    grams_whole_recipe=number(r['grams_whole_recipe']),
                    source_status=r['status'],
                    note=r['note'],
                    scaling='unspecified',
                    source_nutrition_reference=dict(
                        source='USDA FoodData Central', id=r['fdc_id'], description=r['fdc_description']
                    ),
                )
            )
    result = []
    identifiers = set()
    with (BASE / 'foodose/raw/recipes.csv').open(newline='') as stream:
        for r in csv.DictReader(stream):
            identifiers.add(r['recipe_id'])
            declared = {
                key: number(r.get(field))
                for key, field in zip(NUTRIENTS, ['kcal', 'protein_g', 'fat_g', 'carbohydrate_g'])
            }
            item = common(
                'foodose', r['recipe_id'], r['title'], r['cuisine'], r['servings'], groups[r['recipe_id']], declared
            )
            item.update(
                country=None,
                native_title=None,
                summary=r['serving_description'],
                category=r['meals'],
                total_minutes=number(r['total_minutes_estimated']),
                steps=[],
                source_url=r['url'],
                license='CC BY 4.0',
                attribution='foodose; underlying nutrition references: USDA FoodData Central',
                source_not_calculated=r['not_calculated'],
                source_cooked_yet=r['cooked_yet'],
                trace_max_kcal_per_recipe=number(r['trace_max_kcal_per_recipe']),
            )
            result.append(item)
    if set(groups) - identifiers:
        raise ValueError('Orphan foodose ingredients')
    return result


def run(download=False):
    if download:
        for relative, url in FILES.items():
            path = BASE / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    all_recipes = []
    manifests = {}
    for source, importer in [('unitools', import_unitools), ('foodose', import_foodose)]:
        recipes = importer()
        ids = [r['id'] for r in recipes]
        if len(set(ids)) != len(ids):
            raise ValueError('Duplicate recipe IDs')
        if any(not r['ingredients'] or r['servings'] is None or r['servings'] <= 0 for r in recipes):
            raise ValueError('Incomplete recipe structure')
        path = BASE / source / 'recipes.jsonl'
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recipes))
        manifest = dict(
            source=source,
            recipes=len(recipes),
            cuisines=dict(collections.Counter(r['cuisine'] for r in recipes)),
            all_ingredient_masses_known=sum(r['all_ingredient_masses_known'] for r in recipes),
            source_files={
                relative: dict(url=url, sha256=hashlib.sha256((BASE / relative).read_bytes()).hexdigest())
                for relative, url in FILES.items()
                if relative.startswith(source + '/')
            },
            normalized_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            license=recipes[0]['license'],
            imported_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            solver_eligible=0,
        )
        (BASE / source / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        manifests[source] = manifest
        all_recipes.extend(recipes)
    temporary = BASE / 'catalog.sqlite.tmp'
    if temporary.exists():
        temporary.unlink()
    with sqlite3.connect(temporary) as db:
        db.execute(
            'CREATE TABLE recipes(id TEXT PRIMARY KEY,source TEXT,title TEXT,cuisine TEXT,cuisine_id TEXT,search_text TEXT,payload TEXT)'
        )
        for r in all_recipes:
            db.execute(
                'INSERT INTO recipes VALUES(?,?,?,?,?,?,?)',
                (
                    r['id'],
                    r['source'],
                    r['title'],
                    r['cuisine'],
                    r['cuisine_id'],
                    fold(r['title'] + ' ' + r['cuisine']),
                    json.dumps(r, ensure_ascii=False),
                ),
            )
        db.execute('CREATE INDEX cuisine_index ON recipes(cuisine_id)')
    temporary.replace(BASE / 'catalog.sqlite')
    summary = dict(
        recipes=len(all_recipes),
        sources={k: v['recipes'] for k, v in manifests.items()},
        cuisines=dict(collections.Counter(r['cuisine'] for r in all_recipes)),
        note='Source-scoped records and licenses preserved; same dish from different sources is not deduplicated by title.',
    )
    (BASE / 'manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--download', action='store_true')
    a = p.parse_args()
    run(a.download)

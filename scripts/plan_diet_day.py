"""Partial, source-checked diet MILP. Quantities and targets are demonstration inputs."""
import argparse
import asyncio
import csv
import hashlib
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUTRIENTS = ['kcal_100g', 'protein_g_100g', 'fat_g_100g', 'carbs_available_g_100g']
# Exact CREA IDs: states (dry/cooked/raw) remain visible in the output.
STARCH = ['000800', '000100', '000530']
RICE = ['000100']
VEG = ['005730', '006600', '005410']  # excludes potatoes and legumes
FRUIT = ['007120', '007260']
LEGUMES = ['004005', '004125', '004505']
PROTEIN = ['106500', '121410', '181100', '123610']
CHEESE = ['166000']
OIL = ['009210']
def load_rules(config):
    if config['mode'] == 'free':
        return {}
    path = Path(config.get('rules_path', ROOT / 'data/personal/diet_combination_rules.json'))
    return json.loads(path.read_text())


def bounds(food):
    if food == 'recipe:vegetable_puree':
        return (200, 400)
    if food == '000720':
        return (80, 250)
    if food in OIL:
        return (0, 15)
    if food in VEG:
        return (100, 300)
    if food in FRUIT:
        return (100, 250)
    if food in STARCH:
        return (40, 120)
    if food in ['008570', '008540', '166000']:
        return (15, 50)
    return (80, 250)


def load_foods():
    with (ROOT / 'dataset/crea/foods.csv').open(newline='') as stream:
        foods = {row['source_id']: row for row in csv.DictReader(stream)}
    # Explicit demo recipe: equal cooked zucchini and water by final weight.
    base = foods['005735']
    foods['recipe:vegetable_puree'] = dict(source_id='recipe:vegetable_puree',
        name='Passato dimostrativo: 50% zucchine bollite CREA 005735, 50% acqua',
        **{n: str(float(base[n]) * .5) for n in NUTRIENTS})
    return foods


def formulate(config, foods):
    mode = config['mode']
    rules = load_rules(config)
    if mode not in [*rules, 'free']:
        raise ValueError('Unknown diet mode')
    variables, rows, choices = [], [], []
    def var(name, low, high, kind='C'):
        index = len(variables)
        variables.append(dict(name=name, lb=low, ub=high, integrality=kind))
        return index
    def add(coefficients, relation, rhs):
        rows.append((coefficients, relation, rhs))
    exclusions = set(config.get('excluded_crea_ids', []))
    # Use the actual source timetable, rather than accepting arbitrary letter/day pairs.
    if mode == 'free':
        slots = {'lunch': 'free', 'dinner': 'free'}
    else:
        path = Path(config.get('schedule_path', ROOT / f'data/personal/ocr/{mode}/schedule_visual_checked.json'))
        day = config['day_index']
        if isinstance(day, bool) or not isinstance(day, int) or not 0 <= day < 14:
            raise ValueError('day_index must be 0..13')
        record = json.loads(path.read_text())['weeks'][day // 7][day % 7]
        slots = {key: record[key] for key in ['lunch', 'dinner']}
    for meal, expression in slots.items():
        letters = expression.split(' oppure ')
        unsupported = [letter for letter in letters if mode != 'free' and letter not in rules[mode]]
        if unsupported:
            raise ValueError(f'{meal}: {expression}: rules not yet verified/implemented: {unsupported}. No automatic substitution.')
        branch_vars = []
        candidates = [('free', 0, [STARCH, VEG, PROTEIN + LEGUMES, FRUIT])] if mode == 'free' else [(letter, index, groups) for letter in letters for index, groups in enumerate(rules[mode][letter])]
        for letter, branch_index, groups in candidates:
            branch = var(f'{meal}_{letter}_{branch_index}', 0, 1, 'B')
            branch_vars.append(branch)
            # No extra oil added to the pizza-only branch.
            all_groups = groups if groups == [['000720']] else groups + [OIL]
            for group_number, group in enumerate(all_groups):
                selected = []
                for food_id in group:
                    if food_id in exclusions:
                        continue
                    food = foods[food_id]
                    if any(food[n] == '' for n in NUTRIENTS):
                        continue  # Unknown/trace values are never coerced to zero.
                    values = []
                    for nutrient in NUTRIENTS:
                        try:
                            value = float(food[nutrient])
                        except (TypeError, ValueError):
                            raise ValueError(f'Missing nutrient {nutrient}: {food_id}')
                        if not math.isfinite(value) or value < 0:
                            raise ValueError(f'Invalid nutrient: {food_id}')
                        values.append(value / 100)
                    low, high = bounds(food_id)
                    if food_id in config.get('portion_bounds_g', {}):
                        low, high = config['portion_bounds_g'][food_id]
                    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in [low, high]) or not 0 <= low <= high or high == 0:
                        raise ValueError(f'Invalid portion bounds: {food_id}')
                    y = var(f'y{len(choices)}', 0, 1, 'B')
                    q = var(f'q{len(choices)}', 0, high)
                    add({q: 1, y: -high}, '<=', 0)
                    add({q: 1, y: -low}, '>=', 0)
                    selected.append(y)
                    choices.append(dict(meal=meal, combination=letter, branch_index=branch_index, group=group_number, food_id=food_id,
                                        y=y, q=q, nutrients=values))
                add({**{y: 1 for y in selected}, branch: -1}, '=', 0)
            # One optional condiment group, with a zero lower bound for oil.
        add({b: 1 for b in branch_vars}, '=', 1)
    for meal, targets in config.get('meal_targets', {}).items():
        if meal not in slots:
            raise ValueError('Unknown meal in meal_targets')
        for nutrient, spec in targets.items():
            if nutrient not in NUTRIENTS:
                raise ValueError('Unknown nutrient in meal_targets')
            low, high = spec['min'], spec['max']
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in [low, high]) or not 0 <= low <= high:
                raise ValueError('Invalid local bounds')
            n = NUTRIENTS.index(nutrient)
            total = {c['q']: c['nutrients'][n] for c in choices if c['meal'] == meal}
            add(total, '>=', low)
            add(total, '<=', high)
    objective = {}
    for n, nutrient in enumerate(NUTRIENTS):
        if nutrient not in config['main_meals_targets']:
            continue
        spec = config['main_meals_targets'][nutrient]
        low, target, high = [spec[k] for k in ['min', 'target', 'max']]
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in [low, target, high]) or not 0 <= low <= target <= high or target == 0:
            raise ValueError(f'Invalid target: {nutrient}')
        total = {c['q']: c['nutrients'][n] for c in choices}
        add(total, '>=', low)
        add(total, '<=', high)
        deviation = var(f'dev{n}', 0, max(target - low, high - target))
        add({**total, deviation: -1}, '<=', target)
        add({**{i: -v for i, v in total.items()}, deviation: -1}, '<=', -target)
        objective[deviation] = 1 / target
    size = len(variables)
    dense = lambda values: [values.get(i, 0) for i in range(size)]
    problem = dict(version='1', variables=variables,
                   constraints=[dict(coefficients=dense(c), relation=r, rhs=v) for c, r, v in rows],
                   objective=dict(sense='min', coefficients=dense(objective)), solver=dict(time_limit=15))
    return problem, choices, slots


async def solve_problem(session, problem):
    async def call(name, args):
        reply = await session.call_tool('optees_' + name, args)
        data = reply.structuredContent or json.loads(next(x.text for x in reply.content if x.type == 'text'))
        if reply.isError or not data.get('ok'):
            raise RuntimeError(str(data))
        return data
    descriptor = await call('get_capability', dict(capability_id='milp.linear'))
    if not descriptor['capability']['available']:
        raise RuntimeError('MILP unavailable')
    args = dict(capability_id='milp.linear', problem=problem)
    validation = await call('validate_problem', args)
    if not validation['validation']['valid']:
        raise ValueError(str(validation))
    job_id = (await call('create_job', args))['job']['job_id']
    deadline = time.monotonic() + 60
    while True:
        status = (await call('get_job_status', dict(job_id=job_id)))['job']['job_status']
        if status in ['completed', 'failed', 'cancelled']:
            break
        if time.monotonic() > deadline:
            raise TimeoutError(job_id)
        await asyncio.sleep(.2)
    return (await call('get_job_result', dict(job_id=job_id)))['result']


def decode_result(config, problem, choices, slots, foods, result):
    record = dict(demo=config['demo'], scope='lunch_and_dinner_only', config=config, slots=slots,
                  status=result['mathematical_status'], selections=[], nutrients={}, result=result,
                  objective='sum of relative absolute deviations; no Pareto or min-max yet',
                  excluded_for_missing_nutrients=[i for i in sorted({i for mode_rules in load_rules(config).values() for branches in mode_rules.values() for groups in branches for group in groups for i in group}) if any(foods[i][n] == '' for n in NUTRIENTS)],
                  crea_sha256=hashlib.sha256((ROOT / 'dataset/crea/foods.csv').read_bytes()).hexdigest())
    if record['status'] in ['optimal', 'feasible']:
        if result['validation']['status'] != 'verified':
            raise ValueError('Unverified solution')
        values = {x['name']: x['value'] for x in result['result']['variables']}
        totals = [0.] * len(NUTRIENTS)
        for c in choices:
            grams = values[problem['variables'][c['q']]['name']]
            if grams <= 1e-6:
                continue
            food = foods[c['food_id']]
            record['selections'].append(dict(meal=c['meal'], combination=c['combination'], branch_index=c['branch_index'],
                                            crea_id=c['food_id'], food=food['name'], grams=round(grams, 2)))
            totals = [a + grams * b for a, b in zip(totals, c['nutrients'])]
        record['nutrients'] = {n.replace('_100g', ''): round(v, 3) for n, v in zip(NUTRIENTS, totals)}
    return record


async def run(config, output):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    foods = load_foods()
    problem, choices, slots = formulate(config, foods)
    async with stdio_client(StdioServerParameters(command=config['optees_command'])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await solve_problem(session, problem)
    record = decode_result(config, problem, choices, slots, foods, result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: record[k] for k in ['status', 'selections', 'nutrients']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/demo-diet-day.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/personal/diet_day.json')
    args = parser.parse_args()
    asyncio.run(run(json.loads(args.config.read_text()), args.output))

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
    foods['recipe:vegetable_puree'] = dict(
        source_id='recipe:vegetable_puree',
        name='Passato dimostrativo: 50% zucchine bollite CREA 005735, 50% acqua',
        **{n: str(float(base[n]) * 0.5) for n in NUTRIENTS},
    )
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
            raise ValueError(
                f'{meal}: {expression}: rules not yet verified/implemented: {unsupported}. No automatic substitution.'
            )
        branch_vars = []
        candidates = (
            [('free', 0, [STARCH, VEG, PROTEIN + LEGUMES, FRUIT])]
            if mode == 'free'
            else [(letter, index, groups) for letter in letters for index, groups in enumerate(rules[mode][letter])]
        )
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
                    if (
                        any(
                            isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
                            for x in [low, high]
                        )
                        or not 0 <= low <= high
                        or high == 0
                    ):
                        raise ValueError(f'Invalid portion bounds: {food_id}')
                    y = var(f'y{len(choices)}', 0, 1, 'B')
                    q = var(f'q{len(choices)}', 0, high)
                    add({q: 1, y: -high}, '<=', 0)
                    add({q: 1, y: -low}, '>=', 0)
                    selected.append(y)
                    choices.append(
                        dict(
                            meal=meal,
                            combination=letter,
                            branch_index=branch_index,
                            group=group_number,
                            food_id=food_id,
                            y=y,
                            q=q,
                            nutrients=values,
                        )
                    )
                add({**{y: 1 for y in selected}, branch: -1}, '=', 0)
            # One optional condiment group, with a zero lower bound for oil.
        add({b: 1 for b in branch_vars}, '=', 1)
    preference_cost={}
    if config.get('daily_meals',{}).get('enabled'):
        from daily_meals import add_choices
        preference_cost=add_choices(config,foods,var,add,choices)
        slots.update(breakfast='personalized_habits',morning_snack='personalized_habits',afternoon_snack='personalized_habits' if config['daily_meals']['afternoon_fruit'] else 'not_planned')
    for meal, targets in config.get('meal_targets', {}).items():
        if meal not in slots:
            raise ValueError('Unknown meal in meal_targets')
        for nutrient, spec in targets.items():
            if nutrient not in NUTRIENTS:
                raise ValueError('Unknown nutrient in meal_targets')
            low, high = spec['min'], spec['max']
            if (
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in [low, high])
                or not 0 <= low <= high
            ):
                raise ValueError('Invalid local bounds')
            n = NUTRIENTS.index(nutrient)
            total = {c['q']: c['nutrients'][n] for c in choices if c['meal'] == meal}
            add(total, '>=', low)
            add(total, '<=', high)
    objective = {}
    global_targets=config['daily_meals']['targets'] if config.get('daily_meals',{}).get('enabled') else config['main_meals_targets']
    for n, nutrient in enumerate(NUTRIENTS):
        if nutrient not in global_targets:
            continue
        spec = global_targets[nutrient]
        low, target, high = [spec[k] for k in ['min', 'target', 'max']]
        if (
            any(
                isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
                for x in [low, target, high]
            )
            or not 0 <= low <= target <= high
            or target == 0
        ):
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
    problem = dict(
        version='1',
        variables=variables,
        constraints=[dict(coefficients=dense(c), relation=r, rhs=v) for c, r, v in rows],
        objective=dict(sense='min', coefficients=dense(objective)),
        solver=dict(time_limit=15),
    )
    if preference_cost:problem['preference_coefficients']=dense(preference_cost)
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
        await asyncio.sleep(0.2)
    return (await call('get_job_result', dict(job_id=job_id)))['result']


async def optimize_day(session,problem):
    import copy
    from plan_recipe import values_verified
    active=copy.deepcopy(problem);preference=active.pop('preference_coefficients',None)
    if preference and any(preference):
        nutrient_objective=active['objective']['coefficients'][:]
        active['objective']['coefficients']=preference
        first=await solve_problem(session,active)
        if first['mathematical_status']!='optimal':return first
        values=values_verified(active,first);penalty=sum(c*x for c,x in zip(preference,values))
        active['constraints'].append(dict(coefficients=preference,relation='<=',rhs=penalty+1e-7))
        active['objective']['coefficients']=nutrient_objective
        result=await solve_problem(session,active)
        if result['mathematical_status'] not in ['optimal','feasible']:result=first
        else:values_verified(active,result)
        result['preference_penalty']=penalty
        return result
    result=await solve_problem(session,active)
    if result['mathematical_status'] in ['optimal','feasible']:values_verified(active,result)
    return result


def decode_result(config, problem, choices, slots, foods, result):
    record = dict(
        demo=config['demo'],
        scope='full_day_planned_meals' if config.get('daily_meals',{}).get('enabled') else 'lunch_and_dinner_only',
        config=config,
        slots=slots,
        status=result['mathematical_status'],
        selections=[],
        nutrients={},
        result=result,
        objective=result.get('optimization', {}).get('strategy', 'sum of relative absolute deviations'),
        excluded_for_missing_nutrients=[
            i
            for i in sorted(
                {
                    i
                    for mode_rules in load_rules(config).values()
                    for branches in mode_rules.values()
                    for groups in branches
                    for group in groups
                    for i in group
                }
            )
            if any(foods[i][n] == '' for n in NUTRIENTS)
        ],
        crea_sha256=hashlib.sha256((ROOT / 'dataset/crea/foods.csv').read_bytes()).hexdigest(),
    )
    if record['status'] in ['optimal', 'feasible']:
        if result['validation']['status'] != 'verified':
            raise ValueError('Unverified solution')
        from plan_recipe import values_verified
        checked=dict(problem);checked.pop('preference_coefficients',None)
        values_verified(checked,result)
        values = {x['name']: x['value'] for x in result['result']['variables']}
        totals = [0.0] * len(NUTRIENTS)
        meal_totals={meal:[0.]*len(NUTRIENTS) for meal in slots}
        for c in choices:
            grams = values[problem['variables'][c['q']]['name']]
            if grams <= 1e-6:
                continue
            food = foods[c['food_id']]
            record['selections'].append(
                dict(
                    meal=c['meal'],
                    combination=c['combination'],
                    branch_index=c['branch_index'],
                    crea_id=None if c['food_id'].startswith('personal:') else c['food_id'],
                    food_id=c['food_id'],
                    source=c.get('source','CREA'),
                    units=c.get('units'),
                    food=food['name'],
                    grams=round(grams, 2),
                )
            )
            totals = [a + grams * b for a, b in zip(totals, c['nutrients'])]
            meal_totals[c['meal']]=[a+grams*b for a,b in zip(meal_totals[c['meal']],c['nutrients'])]
        record['nutrients'] = {n.replace('_100g', ''): round(v, 3) for n, v in zip(NUTRIENTS, totals)}
    record['nutrients_by_meal']={meal:{n.replace('_100g',''):round(v,3) for n,v in zip(NUTRIENTS,values)} for meal,values in meal_totals.items()} if record['status'] in ['optimal','feasible'] else {}
    record['constraint_report'] = None
    if record['status'] in ['optimal', 'feasible']:
        targets = config['daily_meals']['targets'] if config.get('daily_meals', {}).get('enabled') else config['main_meals_targets']
        checks = []
        for meal, bounds, actuals in [('day', targets, totals)] + [
            (meal, bounds, meal_totals[meal]) for meal, bounds in config.get('meal_targets', {}).items()
        ]:
            for nutrient, spec in bounds.items():
                actual = actuals[NUTRIENTS.index(nutrient)]
                tolerance = 1e-6 * max(1, abs(spec['min']), abs(spec['max']))
                checks.append(dict(meal=meal, nutrient=nutrient.replace('_100g', ''),
                                   actual=actual, min=spec['min'], max=spec['max'],
                                   target=spec.get('target'),
                                   respected=spec['min'] - tolerance <= actual <= spec['max'] + tolerance))
        record['constraint_report'] = dict(verified=True, all_respected=all(c['respected'] for c in checks),
                                           checks=checks, quantities_verified=True,
                                           diet_scope='modeled_choices', rounding_note='Verifica sulle quantità non arrotondate; valori mostrati arrotondati.')
    record['daily_policy']='personalized_habits' if config.get('daily_meals',{}).get('enabled') else None
    record['preference_penalty']=result.get('preference_penalty')
    record['preference_changes']=[]
    if record['daily_policy']:
        preferred=config.get('food_preferences',{}).get('preferences',{})
        meal_names={'breakfast':'Colazione','morning_snack':'Metà mattina'}
        for selected in record['selections']:
            wanted=preferred.get(selected['meal'],{}).get('preferred_product_id')
            if wanted and selected['food_id']!='personal:'+wanted:
                record['preference_changes'].append(meal_names[selected['meal']]+': scelta un’alternativa al prodotto preferito per rispettare i vincoli.')
            elif wanted and selected.get('units',1)==2:
                record['preference_changes'].append(meal_names[selected['meal']]+': scelta la seconda unità facoltativa, consentita nel profilo.')

    record['diet_note']='Colazione e spuntini sono una variante personalizzata; non certificano la dieta originale. Bevande caloriche, extra e frequenze settimanali non inclusi.' if record['daily_policy'] else ''
    return record


async def run(config, output):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from optees_command import optees_command

    foods = load_foods()
    problem, choices, slots = formulate(config, foods)
    async with stdio_client(StdioServerParameters(command=optees_command(config))) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await optimize_day(session, problem)
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

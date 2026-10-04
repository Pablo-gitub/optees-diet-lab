"""Recipe MILP: reviewed food candidates, bounded ratios, lexicographic objectives."""

import argparse
import asyncio
import json
import math
from pathlib import Path
from optees_command import optees_command
from calculate_recipe_nutrients import food_lookup, NUTRIENTS
from plan_diet_day import solve_problem

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'config/recipe-solver.json'


def templates():
    return json.loads(TEMPLATES.read_text())['recipes']


def number(value, low, high, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError('Valore non valido: ' + label)
    return value


def formulate_recipe(recipe, config, lookup=food_lookup):
    flex = number(config.get('flexibility', 0.1), 0, 0.2, 'flessibilità')
    lower = number(config.get('scale_min', 0.5), 0.25, 3, 'porzione minima')
    upper = number(config.get('scale_max', 1.8), lower, 3, 'porzione massima')
    variables = []
    rows = []
    choices = []
    ratios = {}
    objective = {}

    def var(name, lb, ub, kind='C'):
        index = len(variables)
        variables.append(dict(name=name, lb=lb, ub=ub, integrality=kind))
        return index

    def add(c, r, b):
        rows.append((c, r, b))

    scale = var('portion_scale', lower, upper)
    excluded = set(config.get('excluded_crea_ids', []))
    disabled = set(config.get('disabled_products', []))
    for ingredient in recipe['ingredients']:
        base = number(ingredient['grams_per_reference_portion'], 0.001, 3000, 'peso ingrediente')
        key = ingredient['key']
        selected = []
        amounts = []
        candidates = ingredient['candidates']
        # Prefer usable branded alternatives per ingredient; preserve generic fallback
        # when brands are disabled or their nutrition/state cannot be used.
        cache = {}
        if config.get('prefer_branded', recipe.get('product_policy') == 'branded_first'):
            branded = []
            for candidate in candidates:
                if candidate['source'] != 'Open Food Facts':
                    continue
                identifier = candidate['id']
                if 'Open Food Facts:' + identifier in disabled:
                    continue
                if candidate.get('reviewed') is not True or candidate.get('state_checked') is not True:
                    raise ValueError('Associazione non verificata: ' + key)
                food = lookup('Open Food Facts', identifier)
                cache[identifier] = food
                if (
                    food.get('nutrient_basis', 'per_100_g') != 'per_100_g'
                    or food.get('source_quality_errors')
                    or any(f.startswith(('implausible', 'inconsistent')) for f in food.get('quality_flags', []))
                ):
                    continue
                try:
                    valid = all(math.isfinite(float(food[col])) and float(food[col]) >= 0 for col in NUTRIENTS.values())
                except (ValueError, TypeError, KeyError):
                    valid = False
                if valid:
                    branded.append(candidate)
            if branded:
                candidates = branded
        for candidate in candidates:
            if candidate.get('reviewed') is not True or candidate.get('state_checked') is not True:
                raise ValueError('Associazione non verificata: ' + key)
            source = candidate['source']
            identifier = candidate['id']
            if (source == 'CREA' and identifier in excluded) or source + ':' + identifier in disabled:
                continue
            food = (
                {'name': 'Acqua pura', 'nutrient_basis': 'per_100_g', **{col: 0.0 for col in NUTRIENTS.values()}}
                if source == 'water' and identifier == 'water'
                else (
                    cache[identifier]
                    if source == 'Open Food Facts' and identifier in cache
                    else lookup(source, identifier)
                )
            )
            if (
                food.get('nutrient_basis', 'per_100_g') != 'per_100_g'
                or food.get('source_quality_errors')
                or any(f.startswith(('implausible', 'inconsistent')) for f in food.get('quality_flags', []))
            ):
                continue
            values = {}
            for n, col in NUTRIENTS.items():
                try:
                    value = float(food[col])
                except (ValueError, TypeError, KeyError):
                    break
                if not math.isfinite(value) or value < 0:
                    break
                values[n] = value / 100
            if len(values) != len(NUTRIENTS):
                continue
            high = base * upper * (1 + flex)
            i = len(choices)
            y = var('select_' + str(i), 0, 1, 'B')
            q = var('grams_' + str(i), 0, high)
            add({q: 1, y: -high}, '<=', 0)
            selected.append(y)
            amounts.append(q)
            choices.append(
                dict(
                    key=key,
                    ingredient=ingredient['name'],
                    source=source,
                    id=identifier,
                    food=food['name'],
                    brands=food.get('brands', ''),
                    state=ingredient['state'],
                    source_url=food.get('source_url', ''),
                    q=q,
                    y=y,
                    nutrients=values,
                    base_grams=base,
                )
            )
        if not selected:
            raise ValueError('Nessun prodotto utilizzabile per ' + ingredient['name'])
        add({y: 1 for y in selected}, '=', 1)
        total = {q: 1 for q in amounts}
        add({**total, scale: -base * (1 - flex)}, '>=', 0)
        add({**total, scale: -base * (1 + flex)}, '<=', 0)
        deviation = var('ratio_' + key, 0, base * upper * flex)
        add({**total, scale: -base, deviation: -1}, '<=', 0)
        add({**{q: -1 for q in amounts}, scale: base, deviation: -1}, '<=', 0)
        ratios[deviation] = 1 / base
    targets = config.get('targets', {})
    if not targets or any(n not in NUTRIENTS for n in targets):
        raise ValueError('Obiettivi mancanti o non validi')
    for n, spec in targets.items():
        if not isinstance(spec, dict):
            raise ValueError('Obiettivo non valido')
        low = number(spec.get('min'), 0, 10000, n + ' minimo')
        high = number(spec.get('max'), low, 10000, n + ' massimo')
        target = number(spec.get('target'), max(low, 0.000001), high, n + ' bersaglio')
        total = {c['q']: c['nutrients'][n] for c in choices}
        add(total, '>=', low)
        add(total, '<=', high)
        deviation = var('nutrient_' + n, 0, max(target - low, high - target))
        add({**total, deviation: -1}, '<=', target)
        add({**{q: -v for q, v in total.items()}, deviation: -1}, '<=', -target)
        objective[deviation] = 1 / target
    dense = lambda c: [c.get(i, 0) for i in range(len(variables))]
    problem = dict(
        version='1',
        variables=variables,
        constraints=[dict(coefficients=dense(c), relation=r, rhs=b) for c, r, b in rows],
        objective=dict(sense='min', coefficients=dense(objective)),
        solver=dict(time_limit=15),
    )
    return problem, choices, dense(ratios)


def values_verified(problem, result):
    if result['validation']['status'] != 'verified':
        raise ValueError('Soluzione non verificata')
    by_name = {v['name']: v['value'] for v in result['result']['variables']}
    values = [by_name[v['name']] for v in problem['variables']]
    for v, x in zip(problem['variables'], values):
        if (
            not math.isfinite(x)
            or x < v['lb'] - 1e-5
            or x > v['ub'] + 1e-5
            or (v['integrality'] == 'B' and abs(x - round(x)) > 1e-5)
        ):
            raise ValueError('Variabile fuori limite')
    for row in problem['constraints']:
        lhs = sum(c * x for c, x in zip(row['coefficients'], values))
        rhs = row['rhs']
        r = row['relation']
        if (r == '=' and abs(lhs - rhs) > 1e-5) or (r == '<=' and lhs > rhs + 1e-5) or (r == '>=' and lhs < rhs - 1e-5):
            raise ValueError('Vincolo non rispettato')
    return values


def decode_recipe(recipe, config, problem, choices, result):
    record = dict(
        recipe_id=recipe['id'],
        title=recipe['title'],
        status=result['mathematical_status'],
        scope='single_recipe',
        diet_eligibility='not_checked',
        flexibility=config.get('flexibility', 0.1),
        targets=config['targets'],
        adaptation_notes=recipe.get('adaptation_notes', []),
        source_url=recipe.get('source_url'),
        license=recipe.get('license'),
        selections=[],
        nutrients={},
        note='Pesi degli ingredienti, non peso finale dopo cottura. Tutti gli ingredienti sono conteggiati come consumati. Gli abbinamenti delle diete personali non sono verificati.',
    )
    if record['status'] not in ['optimal', 'feasible']:
        return record
    values = values_verified(problem, result)
    scale = values[0]
    record['portion_scale'] = scale
    totals = {n: 0.0 for n in NUTRIENTS}
    for c in choices:
        if values[c['y']] < 0.5:
            continue
        grams = values[c['q']]
        base = c['base_grams'] * scale
        record['selections'].append(
            {
                **{k: c[k] for k in ['key', 'ingredient', 'source', 'id', 'food', 'brands', 'state', 'source_url']},
                'grams': round(grams, 2),
                'proportion_change_percent': round(100 * (grams / base - 1), 2),
            }
        )
        for n in totals:
            totals[n] += grams * c['nutrients'][n]
    record['nutrients'] = {n: round(v, 4) for n, v in totals.items()}
    record['nutrient_score'] = sum(abs(totals[n] - s['target']) / s['target'] for n, s in config['targets'].items())
    return record


async def optimize_recipe(session, recipe, config):
    problem, choices, ratios = formulate_recipe(recipe, config)
    first = await solve_problem(session, problem)
    if first['mathematical_status'] != 'optimal':
        record = decode_recipe(recipe, config, problem, choices, first)
        record['ratio_optimization'] = 'not_run'
        return record
    values = values_verified(problem, first)
    score = sum(c * x for c, x in zip(problem['objective']['coefficients'], values))
    problem['constraints'].append(
        dict(coefficients=problem['objective']['coefficients'][:], relation='<=', rhs=score + 1e-7)
    )
    problem['objective']['coefficients'] = ratios
    second = await solve_problem(session, problem)
    if second['mathematical_status'] in ['optimal', 'feasible']:
        record = decode_recipe(recipe, config, problem, choices, second)
        record['ratio_optimization'] = second['mathematical_status']
    else:
        problem['constraints'].pop()
        record = decode_recipe(recipe, config, problem, choices, first)
        record['ratio_optimization'] = 'fallback_to_nutrient_optimum'
    record['objective'] = 'lexicographic: relative nutrient deviation, then ingredient ratio deviation'
    return record


async def run(config):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    recipe = next(r for r in templates() if r['id'] == config['recipe_id'])
    async with stdio_client(StdioServerParameters(command=optees_command(config))) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await optimize_recipe(session, recipe, config)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=ROOT / 'config/demo-recipe.json')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = asyncio.run(run(json.loads(a.config.read_text())))
    if a.output:
        a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))

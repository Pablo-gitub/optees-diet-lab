"""Audit 28 diet days with Optees: local, global, and simultaneous constraints."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from optees_command import optees_command
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from plan_diet_day import ROOT, NUTRIENTS, load_foods, formulate, solve_problem, decode_result


def verify(problem, result):
    if result['mathematical_status'] not in ['optimal', 'feasible']:
        return None
    if result['validation']['status'] != 'verified':
        raise ValueError('Optees solution unverified')
    values = {v['name']: v['value'] for v in result['result']['variables']}
    x = [values[v['name']] for v in problem['variables']]
    for v, a in zip(problem['variables'], x):
        if not v['lb'] - 1e-5 <= a <= v['ub'] + 1e-5:
            raise ValueError('Bound violation')
        if v['integrality'] != 'C' and abs(a - round(a)) > 1e-5:
            raise ValueError('Integrality violation')
    for row in problem['constraints']:
        value = sum(a * b for a, b in zip(row['coefficients'], x))
        rhs = row['rhs']
        if (
            row['relation'] == '<='
            and value > rhs + 1e-5
            or row['relation'] == '>='
            and value < rhs - 1e-5
            or row['relation'] == '='
            and abs(value - rhs) > 1e-5
        ):
            raise ValueError('Constraint violation')
    return x


async def audit():
    base = json.loads((ROOT / 'config/demo-diet-day.json').read_text())
    local = json.loads((ROOT / 'config/demo-diet-audit.json').read_text())['meal_targets']
    foods = load_foods()
    records = []
    async with stdio_client(StdioServerParameters(command=optees_command(base))) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for mode in ['sedentary', 'training']:
                for day in range(14):
                    for scenario in ['local_only', 'global_only', 'local_and_global']:
                        config = copy.deepcopy(base)
                        config.update(mode=mode, day_index=day)
                        config['meal_targets'] = local if scenario != 'global_only' else {}
                        if scenario == 'local_only':
                            config['main_meals_targets'] = {}
                        problem, choices, slots = formulate(config, foods)
                        result = await solve_problem(session, problem)
                        x = verify(problem, result)
                        record = decode_result(config, problem, choices, slots, foods, result)
                        record.update(
                            scenario=scenario,
                            independent_verification=x is not None,
                            interpretation='feasible_witness_in_subset'
                            if x is not None
                            else 'no_solution_in_modeled_subset; full_diet_infeasibility_not_proven',
                        )
                        record['meal_nutrients'] = {}
                        if x is not None:
                            for meal in slots:
                                record['meal_nutrients'][meal] = {
                                    n.replace('_100g', ''): sum(
                                        x[c['q']] * c['nutrients'][k] for c in choices if c['meal'] == meal
                                    )
                                    for k, n in enumerate(NUTRIENTS)
                                }
                        records.append(record)
                        print(f'{mode} day {day + 1:02} {scenario}: {record["status"]}', flush=True)
    provenance = {}
    for mode in ['sedentary', 'training']:
        path = ROOT / f'data/personal/ocr/{mode}/schedule_visual_checked.json'
        provenance[mode] = hashlib.sha256(path.read_bytes()).hexdigest()
    output = ROOT / 'data/personal/diet_fortnight_audit.json'
    output.write_text(
        json.dumps(
            dict(
                demo=True,
                scope='lunch_and_dinner_only',
                schedule_sha256=provenance,
                model_sha256=hashlib.sha256((ROOT / 'scripts/plan_diet_day.py').read_bytes()).hexdigest(),
                records=records,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + '\n'
    )
    report = [
        '# Verifica delle due settimane di entrambe le diete',
        '',
        'Test dimostrativo su pranzo e cena, non sui fabbisogni personali né sulla giornata completa.',
        'Tutte le lettere del calendario hanno almeno un ramo modellato; copertura degli alimenti e dei rami parziale.',
        'Una soluzione è una prova di esistenza nel sottoinsieme; un fallimento non prova che la dieta completa sia impossibile.',
        '',
        '| Dieta | Giorno | Pranzo / cena | Solo locale | Solo globale | Entrambi |',
        '|---|---:|---|---|---|---|',
    ]
    for mode in ['sedentary', 'training']:
        for day in range(14):
            items = [r for r in records if r['config']['mode'] == mode and r['config']['day_index'] == day]
            labels = ['Sì' if r['independent_verification'] else r['status'] for r in items]
            report.append(
                f'| {mode} | {day + 1} | {items[0]["slots"]["lunch"]} / {items[0]["slots"]["dinner"]} | '
                + ' | '.join(labels)
                + ' |'
            )
    report += [
        '',
        '## Vincoli dimostrativi',
        '',
        'Globali (somma pranzo+cena): ' + json.dumps(base['main_meals_targets'], ensure_ascii=False),
        '',
        'Locali (ciascun pasto): ' + json.dumps(local, ensure_ascii=False),
        '',
        'I risultati non includono frequenze settimanali, colazione, spuntini, bevande energetiche, varietà o compensazioni fra giorni.',
        'Le settimane vengono controllate giorno per giorno: non è ancora una singola ottimizzazione con vincoli che collegano giorni diversi.',
        'M usa un passato dimostrativo con 50% zucchine bollite e 50% acqua; Q usa il ramo pizza con acqua.',
        'Porzioni e ricetta del passato sono ipotesi esplicite del modello. Alimenti con macronutrienti mancanti vengono esclusi.',
    ]
    (ROOT / 'data/personal/diet_fortnight_audit.md').write_text('\n'.join(report) + '\n')
    print('Report:', output, flush=True)


if __name__ == '__main__':
    asyncio.run(audit())

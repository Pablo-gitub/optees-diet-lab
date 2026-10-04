"""Weekly MILP demo, shared service entry point for CLI and future web UI."""
import argparse
import asyncio
import hashlib
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def formulate(config, catalog, mode):
    days = list(config['days'])
    numbers = [*config['days'].values(), config['weekly_minutes_max'],
               config['sessions_min'], config['sessions_max'], config['strength_sessions_min'],
               config['strength_sessions_max'], config['cardio_minutes_min'], config['strength_gap_days']]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in numbers):
        raise ValueError('Time and session limits must be finite nonnegative numbers')
    if len(days) != 7 or config['sessions_min'] > config['sessions_max']:
        raise ValueError('Seven ordered days and consistent session bounds required')
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0
           for v in config['muscle_targets_proxy'].values()):
        raise ValueError('Muscle proxy targets must be finite and positive')
    templates = catalog['templates']
    slots = [(day, t) for day in days for t in templates
             if t['duration_minutes_assumed'] <= config['days'][day]]
    if not slots:
        raise ValueError('No available slots')
    n = len(slots)
    variables = [{'name': f's{i}', 'lb': 0, 'ub': 1, 'integrality': 'B'} for i in range(n)]
    muscles = list(config['muscle_targets_proxy'])
    variables += [{'name': f'coverage_{i}', 'lb': 0, 'ub': 1, 'integrality': 'C'} for i in range(len(muscles))]
    size = len(variables)
    constraints = []

    def add(values, relation, rhs):
        constraints.append({'coefficients': values + [0] * (size - len(values)), 'relation': relation, 'rhs': rhs})

    strength = [bool(t['score_vector']['muscle_coverage_proxy']) for _, t in slots]
    duration = [t['duration_minutes_assumed'] for _, t in slots]
    for day in days:
        add([int(d == day) for d, _ in slots], '<=', 1)
    add(duration, '<=', config['weekly_minutes_max'])
    add([1] * n, '>=', config['sessions_min'])
    add([1] * n, '<=', config['sessions_max'])
    add([int(s) for s in strength], '>=', config['strength_sessions_min'])
    add([int(s) for s in strength], '<=', config['strength_sessions_max'])
    add([0 if s else minutes for s, minutes in zip(strength, duration)], '>=', config['cardio_minutes_min'])
    gap = config['strength_gap_days']
    if int(gap) != gap:
        raise ValueError('Recovery gap must be an integer')
    for i, day in enumerate(days):
        window = days[i:i + int(gap) + 1]
        add([int(d in window and s) for (d, _), s in zip(slots, strength)], '<=', 1)
    for k, muscle in enumerate(muscles):
        row = [-t['score_vector']['muscle_coverage_proxy'].get(muscle, 0) /
               config['muscle_targets_proxy'][muscle] for _, t in slots] + [0] * len(muscles)
        row[n + k] = 1
        add(row, '<=', 0)
    if mode == 'time':
        objective = duration + [0] * len(muscles)
        sense = 'min'
    else:
        objective = [0] * n + [1] * len(muscles)
        sense = 'max'
    return {'version': '1', 'variables': variables, 'constraints': constraints,
            'objective': {'sense': sense, 'coefficients': objective}, 'solver': {'time_limit': 15}}, slots


async def run(config_path, catalog_path, output):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    config = json.loads(config_path.read_text())
    catalog = json.loads(catalog_path.read_text())
    results = []
    async with stdio_client(StdioServerParameters(command=config['optees_command'])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call(name, args):
                reply = await session.call_tool('optees_' + name, args)
                data = reply.structuredContent or json.loads(next(x.text for x in reply.content if x.type == 'text'))
                if reply.isError or not data.get('ok'):
                    raise RuntimeError(str(data))
                return data

            descriptor = await call('get_capability', {'capability_id': 'milp.linear'})
            if not descriptor['capability']['available']:
                raise RuntimeError('MILP unavailable')
            for mode in ['time', 'coverage']:
                problem, slots = formulate(config, catalog, mode)
                args = {'capability_id': 'milp.linear', 'problem': problem}
                validation = await call('validate_problem', args)
                if not validation['validation']['valid']:
                    raise ValueError(str(validation))
                job = await call('create_job', args)
                job_id = job['job']['job_id']
                deadline = time.monotonic() + 60
                while True:
                    status = await call('get_job_status', {'job_id': job_id})
                    if status['job']['job_status'] in ['completed', 'failed', 'cancelled']:
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError('Optees job exceeded client wait limit')
                    await asyncio.sleep(0.2)
                result = await call('get_job_result', {'job_id': job_id})
                envelope = result['result']
                summary = {'status': envelope['mathematical_status'], 'sessions': []}
                if envelope['mathematical_status'] in ['optimal', 'feasible']:
                    if envelope['validation']['status'] != 'verified':
                        raise ValueError('Solution failed independent validation')
                    values = {v['name']: v['value'] for v in envelope['result']['variables']}
                    selected = [(d, t) for i, (d, t) in enumerate(slots) if values[f's{i}'] > 0.5]
                    summary['sessions'] = [{'day': d, 'template_id': t['id'],
                                            'minutes': t['duration_minutes_assumed']} for d, t in selected]
                    summary['weekly_minutes'] = sum(t['duration_minutes_assumed'] for _, t in selected)
                    summary['coverage_target_fraction'] = {
                        muscle: min(1, sum(t['score_vector']['muscle_coverage_proxy'].get(muscle, 0)
                                           for _, t in selected) / target)
                        for muscle, target in config['muscle_targets_proxy'].items()}
                results.append({'mode': mode, 'summary': summary, 'problem': problem, 'slots': [
                    {'day': d, 'template_id': t['id'], 'minutes': t['duration_minutes_assumed']}
                    for d, t in slots], 'validation': validation, 'result': result})
    record = {'demo': config.get('demo', False), 'config': config,
              'catalog_sha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest(), 'runs': results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(f'Saved {len(results)} runs to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/demo-week.json')
    parser.add_argument('--catalog', type=Path, default=ROOT / 'data/personal/workout_catalog.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/personal/workout_week.json')
    args = parser.parse_args()
    asyncio.run(run(args.config, args.catalog, args.output))

"""Weekly MILP demo, shared service entry point for CLI and future web UI."""

import argparse
import copy
import datetime as dt
from zoneinfo import ZoneInfo
import asyncio
import hashlib
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def formulate(config, catalog, mode):
    days = list(config['days'])
    numbers = [
        *config['days'].values(),
        config['weekly_minutes_max'],
        config['sessions_min'],
        config['sessions_max'],
        config['strength_sessions_min'],
        config['strength_sessions_max'],
        config['cardio_minutes_min'],
        config['strength_gap_days'],
    ]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in numbers):
        raise ValueError('Time and session limits must be finite nonnegative numbers')
    if len(days) != 7 or config['sessions_min'] > config['sessions_max']:
        raise ValueError('Seven ordered days and consistent session bounds required')
    if any(
        not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0
        for v in config['muscle_targets_proxy'].values()
    ):
        raise ValueError('Muscle proxy targets must be finite and positive')
    templates = [t for t in catalog['templates']
                 if t.get('equipment_feasible',True)
                 and (t.get('format')!='intervals' or t.get('high_intensity_ready',True))
                 and (t.get('kind')=='activity' or not config.get('goal') or config['goal'] in t.get('compatible_goals', []))
                 and (t.get('kind')=='activity' or not config.get('allowed_protocols') or t.get('protocol_id') in config['allowed_protocols'])
                 and (config.get('allow_high_intensity_demo',False) or t.get('format')!='intervals')
                 and (config.get('demo',False) or not t.get('pending_configuration'))]
    if catalog.get('model_version')=='workout-sessions-v2':
        from workout_sessions import validate_session
        for t in templates:validate_session(t)
    locked=config.get('locked_by_date',{})
    slots=[];per_day=config.get('max_sessions_per_day',1);cap=config.get('max_session_minutes',90)
    for day in days:
        starts=config.get('start_times',{}).get(day)
        if isinstance(starts,list) and len(starts)>per_day:raise ValueError('Più orari del massimo personale di sedute giornaliere')
        if starts is None:starts=[None] if per_day==1 else ['09:00']
        elif isinstance(starts,str):starts=[starts]
        starts=sorted(starts) if all(isinstance(t,str) for t in starts) else starts
        if per_day==2 and len(starts)==1:
            first=starts[0] or '09:00';h,m=map(int,first.split(':'));second=h*60+m+cap+config.get('min_gap_hours',4)*60
            if second<1440:starts=[first,f'{int(second//60):02d}:{int(second%60):02d}']
        for position,start in enumerate(starts):
            if day in locked and position>0:continue
            for original in (locked[day] if day in locked else templates):
                t=copy.deepcopy(original);t['_slot']=position;t['_start_time']=start
                start_minute=sum(v*f for v,f in zip(map(int,start.split(':')),(60,1))) if start else 0
                limit=1440-start_minute
                if t.get('locked_observation') or (t['duration_minutes_assumed']<=min(cap,limit) and max(t['score_vector']['muscle_coverage_proxy'].values(),default=0)<=10):
                    if t['duration_minutes_assumed']<=config['days'][day]:slots.append((day,t))
    if not slots and any(config[k]>0 for k in ('sessions_min','strength_sessions_min','cardio_minutes_min')):
        raise ValueError('No available slots')
    n = len(slots)
    activity_indices={}
    variables = [{'name': f's{i}', 'lb': 0, 'ub': 1, 'integrality': 'B'} for i in range(n)]
    for i,(day,t) in enumerate(slots):
        if t.get('kind')=='activity':
            limits=t['activity_duration'];step=limits['step']
            cap=min(limits['max'],config['days'][day],config.get('max_session_minutes',90),1440-(sum(v*f for v,f in zip(map(int,t['_start_time'].split(':')),(60,1))) if t.get('_start_time') else 0))
            activity_indices[i]=len(variables)
            variables.append(dict(name=f'activity_units_{i}',lb=0,ub=int(cap//step),integrality='I'))
    strength_day_indices={}
    if per_day==2:
        for day in days:
            strength_day_indices[day]=len(variables)
            variables.append(dict(name='strength_day_'+day,lb=0,ub=1,integrality='B'))
    coverage_start=len(variables)
    muscles = list(config['muscle_targets_proxy'])
    variables += [{'name': f'coverage_{i}', 'lb': 0, 'ub': 1, 'integrality': 'C'} for i in range(len(muscles))]
    if not variables:variables.append(dict(name='idle',lb=0,ub=0,integrality='C'))
    health_priority=config.get('health_priority',0)
    health_minutes_index=health_strength_index=None
    if health_priority:
        health_minutes_index=len(variables);variables.append(dict(name='health_minutes_coverage',lb=0,ub=1,integrality='C'))
        health_strength_index=len(variables);variables.append(dict(name='health_strength_coverage',lb=0,ub=1,integrality='C'))
    size = len(variables)
    constraints = []

    def add(values, relation, rhs):
        constraints.append({'coefficients': values + [0] * (size - len(values)), 'relation': relation, 'rhs': rhs})

    strength = [t.get('strength_count',int(t.get('resistance_session',bool(t['score_vector']['muscle_coverage_proxy'])))) for _, t in slots]
    duration = [t['duration_minutes_assumed'] for _, t in slots]
    for i,q in activity_indices.items():
        t=slots[i][1];limits=t['activity_duration'];step=limits['step']
        row=[0.]*size;row[q]=1;row[i]=-variables[q]['ub'];add(row,'<=',0)
        row=[0.]*size;row[q]=1;row[i]=-int(limits['min']//step);add(row,'>=',0)
        duration[i]=0
    duration += [0.]*(size-n)
    for i,q in activity_indices.items():duration[q]=slots[i][1]['activity_duration']['step']
    variable_dates={i:d for i,(d,_) in enumerate(slots)}
    variable_dates.update({q:slots[i][0] for i,q in activity_indices.items()})
    for day in days:
        add([duration[j] if variable_dates.get(j)==day else 0 for j in range(size)],'<=',config['days'][day])
        add([t.get('session_count',1) if d==day else 0 for d,t in slots],'<=' ,max(per_day,max((t.get('session_count',1) for d,t in slots if d==day and t.get('locked_observation')),default=0)))
        for position in range(per_day):add([int(d==day and t['_slot']==position) for d,t in slots],'<=',1)
        if per_day==2:
            z=strength_day_indices[day];indices=[i for i,(d,t) in enumerate(slots) if d==day and strength[i]>0]
            for i in indices:
                row=[0.]*size;row[i]=1;row[z]=-1;add(row,'<=',0)
            row=[0.]*size;row[z]=1
            for i in indices:row[i]-=1
            add(row,'<=',0)
            for i,(d,a) in enumerate(slots):
                if d!=day or a['_slot']!=0:continue
                for j,(other,b) in enumerate(slots):
                    if other!=day or b['_slot']!=1:continue
                    start=lambda t:dt.datetime.combine(dt.date.fromisoformat(day),dt.time.fromisoformat(t['_start_time']),ZoneInfo('Europe/Rome')).timestamp()/60
                    gap=start(b)-start(a)-config.get('min_gap_hours',4)*60
                    row=[0.]*size;row[i]=3000;row[j]=3000
                    row[activity_indices[i] if i in activity_indices else i]+=a['activity_duration']['step'] if i in activity_indices else a['duration_minutes_assumed']
                    add(row,'<=',gap+6000)
    add(duration, '<=', config['weekly_minutes_max'])
    counts=[t.get('session_count',1) for _,t in slots]
    add(counts, '>=', config['sessions_min'])
    add(counts, '<=', config['sessions_max'])
    for day,locked_templates in locked.items():
        if locked_templates:add([int(d==day) for d,_ in slots],'=',1)
    add(strength, '>=', config['strength_sessions_min'])
    add(strength, '<=', config['strength_sessions_max'])
    cardio = [t.get('cardio_work_seconds', t['duration_minutes_assumed']*60 if not s else 0)/60 for (_,t),s in zip(slots,strength)]
    cardio += [0.]*(size-n)
    for i,q in activity_indices.items():
        cardio[i]=0;cardio[q]=slots[i][1]['activity_duration']['step'] if slots[i][1]['cardio_work_seconds'] else 0
    add(cardio, '>=', config['cardio_minutes_min'])
    if health_priority:
        row=[0.]*size;row[health_minutes_index]=1
        for i,(d,t) in enumerate(slots):
            if i in activity_indices:row[activity_indices[i]]-=t['activity_duration']['step']*t['health_equivalent_factor']/150
            elif not strength[i]:row[i]-=t.get('cardio_work_seconds',0)/60/150
        add(row,'<=',0)
        row=[0.]*size;row[health_strength_index]=1
        if strength_day_indices:
            for z in strength_day_indices.values():row[z]-=.5
        else:
            for i,value in enumerate(strength):row[i]-=value/2
        add(row,'<=',0)
    gap = config['strength_gap_days']
    if int(gap) != gap:
        raise ValueError('Recovery gap must be an integer')
    for i, day in enumerate(days):
        window = days[i : i + int(gap) + 1]
        if strength_day_indices:
            row=[0.]*size
            for day_in_window in window:row[strength_day_indices[day_in_window]]=1
            add(row,'<=',1)
        else:add([s if d in window else 0 for (d, _), s in zip(slots, strength)], '<=', 1)
    for k, muscle in enumerate(muscles):
        row = [
            -t['score_vector']['muscle_coverage_proxy'].get(muscle, 0) / config['muscle_targets_proxy'][muscle]
            for _, t in slots
        ] + [0] * (size-n)
        row[coverage_start + k] = 1
        add(row, '<=', 0)
    if mode == 'time':
        objective = duration[:]
        for i,(d,t) in enumerate(slots):
            if config['days'][d]<40 and t['resistance_session']:
                efficiency=t.get('efficiency',{}).get('hard_sets_per_minute') or t.get('efficiency',{}).get('muscles_per_minute',0)
                objective[i]/=1+min(.25,efficiency)
        sense = 'min'
    else:
        objective = [0] * size
        for k in range(len(muscles)):objective[coverage_start+k]=1
        sense = 'max'
    objective += [0]*(size-len(objective))
    if health_priority:
        for i in (health_minutes_index,health_strength_index):objective[i]=(-200 if mode=='time' else 1)*health_priority/2
    return {
        'version': '1',
        'variables': variables,
        'constraints': constraints,
        'objective': {'sense': sense, 'coefficients': objective},
        'solver': {'time_limit': 15},
    }, slots


async def run(config_path, catalog_path, output):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from optees_command import optees_command

    config = json.loads(config_path.read_text())
    catalog = json.loads(catalog_path.read_text())
    results = []
    async with stdio_client(StdioServerParameters(command=optees_command(config))) as (read, write):
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
                    from plan_recipe import values_verified
                    values_verified(problem,envelope)
                    values = {v['name']: v['value'] for v in envelope['result']['variables']}
                    selected = [(d, t) for i, (d, t) in enumerate(slots) if values[f's{i}'] > 0.5]
                    summary['sessions'] = [
                        {'day': d, 'template_id': t['id'], 'minutes': t['duration_minutes_assumed'], 'session': t}
                        for d, t in selected
                    ]
                    summary['weekly_minutes'] = sum(t['duration_minutes_assumed'] for _, t in selected)
                    summary['coverage_target_fraction'] = {
                        muscle: min(
                            1,
                            sum(t['score_vector']['muscle_coverage_proxy'].get(muscle, 0) for _, t in selected)
                            / target,
                        )
                        for muscle, target in config['muscle_targets_proxy'].items()
                    }
                results.append(
                    {
                        'mode': mode,
                        'summary': summary,
                        'problem': problem,
                        'slots': [
                            {'day': d, 'template_id': t['id'], 'minutes': t['duration_minutes_assumed']}
                            for d, t in slots
                        ],
                        'validation': validation,
                        'result': result,
                    }
                )
    record = {
        'demo': config.get('demo', False),
        'config': config,
        'catalog_sha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        'runs': results,
    }
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

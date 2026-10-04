"""Finite-pool robust selection with independently checked Optees one-hot solves."""
import asyncio
import json
import math
import time

SCENARIOS=('low','central','high')
CAPABILITY='scenario.linear.min_max_loss'


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def annotate(plans,balance):
    comparable=[]
    for index,plan in enumerate(plans):
        plan['candidate_index']=index
        reason=None
        if not finite(balance):reason='Bilancio energetico obiettivo non esplicitamente configurato.'
        elif len(plan['days'])!=7:reason='Servono sette giornate complete.'
        elif any(d.get('energy_scenarios',{}).get('status')!='available' or not finite(d['nutrients'].get('kcal')) or any(not finite(d['energy_scenarios'].get('consumption_kcal',{}).get(s)) for s in SCENARIOS) for d in plan['days']):reason='Scenari Salute o modelli attività incompleti.'
        if reason:plan['robustness']=dict(status='unavailable',reason=reason);continue
        losses={s:sum(abs(d['nutrients']['kcal']-d['energy_scenarios']['consumption_kcal'][s]-balance) for d in plan['days'])/7 for s in SCENARIOS}
        plan['robustness']=dict(status='available',scenarios=losses,max_loss_kcal=max(losses.values()),scope='sampled_joint_pool',aggregation='mean_daily_absolute_error',energy_balance_target_kcal=balance)
        comparable.append(plan)
    if comparable:
        minima={s:min(p['robustness']['scenarios'][s] for p in comparable) for s in SCENARIOS}
        for p in comparable:
            r=p['robustness'];r['regret_scenarios']={s:r['scenarios'][s]-minima[s] for s in SCENARIOS};r['max_regret_kcal']=max(r['regret_scenarios'].values());r['scenario_minima_kcal']=minima
    return comparable


def problem_for(plans,metric):
    return dict(version='1',problem_type='linear_scenario',orientation='minimize_maximum_loss',variables=[dict(name=f'pick_{p["candidate_index"]}',lower_bound=0,upper_bound=1,integrality='B') for p in plans],scenarios=[dict(id=s,coefficients=[p['robustness'][metric][s] for p in plans],offset=0) for s in SCENARIOS],shared_constraints=[dict(coefficients=[1]*len(plans),relation='=',rhs=1)],options=dict(time_limit_seconds=5,tolerance=1e-7,binding_tolerance=1e-6))


def verify(problem,envelope):
    if envelope.get('mathematical_status') not in ('optimal','feasible') or envelope.get('validation',{}).get('status')!='verified':raise ValueError('Selettore robusto non verificato da Optees')
    result=envelope['result'];values=result['variables'];names=[v['name'] for v in problem['variables']]
    if len(values)!=len(names) or {v['name'] for v in values}!=set(names):raise ValueError('Variabili robuste mancanti o duplicate')
    mapping={v['name']:v['value'] for v in values};weights=[mapping[n] for n in names]
    if any(not finite(v) or min(abs(v),abs(v-1))>1e-6 for v in weights) or abs(sum(weights)-1)>1e-6:raise ValueError('Il selettore deve scegliere una settimana intera')
    selected=max(range(len(weights)),key=weights.__getitem__)
    expected={s['id']:s['coefficients'][selected]+s['offset'] for s in problem['scenarios']}
    reported=result['scenario_values']
    if len(reported)!=len(expected) or {s['scenario_id'] for s in reported}!=set(expected):raise ValueError('Scenari robusti mancanti o duplicati')
    if any(not finite(s['value']) or abs(s['value']-expected[s['scenario_id']])>1e-5 for s in reported):raise ValueError('Perdite scenario incoerenti')
    worst=max(expected.values())
    if result.get('orientation')!='minimize_maximum_loss' or not finite(result.get('guaranteed_value')) or abs(result['guaranteed_value']-worst)>1e-5:raise ValueError('Valore garantito incoerente')
    optimum=min(max(s['coefficients'][i]+s['offset'] for s in problem['scenarios']) for i in range(len(weights)))
    if envelope['mathematical_status']=='optimal' and abs(worst-optimum)>1e-5:raise ValueError('Ottimo robusto non confermato dal controllo indipendente')
    return dict(candidate_index=int(names[selected].split('_')[1]),mathematical_status=envelope['mathematical_status'],verified=True,guaranteed_value=worst,scenario_values=expected,scope='sampled_joint_pool')


async def call(session,name,args):
    reply=await session.call_tool('optees_'+name,args)
    data=reply.structuredContent or json.loads(next(x.text for x in reply.content if x.type=='text'))
    if reply.isError or not data.get('ok'):raise RuntimeError(str(data))
    return data


async def solve(session,problem):
    args=dict(capability_id=CAPABILITY,problem=problem)
    validation=await call(session,'validate_problem',args)
    if not validation['validation']['valid']:raise ValueError(str(validation))
    job=(await call(session,'create_job',args))['job']['job_id'];deadline=time.monotonic()+30
    while True:
        status=(await call(session,'get_job_status',dict(job_id=job)))['job']['job_status']
        if status in ('completed','failed','cancelled'):break
        if time.monotonic()>deadline:raise TimeoutError(job)
        await asyncio.sleep(.1)
    return (await call(session,'get_job_result',dict(job_id=job)))['result']


async def annotate_pool(session,plans,balance):
    comparable=annotate(plans,balance)
    summary=dict(scope='sampled_joint_pool',comparable_candidates=len(comparable),total_candidates=len(plans))
    if not comparable:return dict(summary,status='unavailable',reason='Bilancio esplicito e scenari completi richiesti.')
    descriptor=await call(session,'get_capability',dict(capability_id=CAPABILITY))
    if not descriptor['capability']['available']:
        return dict(summary,status='local_finite_pool',backend_status='unavailable',min_max=dict(candidate_index=min(comparable,key=lambda p:p['robustness']['max_loss_kcal'])['candidate_index']),minimax_regret=dict(candidate_index=min(comparable,key=lambda p:p['robustness']['max_regret_kcal'])['candidate_index']))
    audits={}
    for key,metric in (('min_max','scenarios'),('minimax_regret','regret_scenarios')):
        problem=problem_for(comparable,metric);audits[key]=verify(problem,await solve(session,problem))
    return dict(summary,status='verified',capability_id=CAPABILITY,**audits)

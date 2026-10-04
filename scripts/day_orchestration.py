"""Deterministic daily S0–S7 orchestration over independently verified MILPs."""
import copy
import hashlib
import json
import math
import time
from plan_diet_day import formulate, decode_result, NUTRIENTS, PROTEIN, LEGUMES, STARCH, CHEESE, load_rules
from multiobjective_day import solve_strategy
from target_validation import target_warnings

VERSION = 'orchestration-v1'
SAFE = ['demo','scope','slots','status','selections','nutrients','nutrients_by_meal','daily_policy','diet_note','preference_penalty','preference_changes','constraint_report']


def active_choices(choices):
    return [c for c in choices if c.get('diversity_eligible',c['meal'] in ('lunch','dinner')) and not c.get('locked')]


def selection_keys(plan):
    return {(s['meal'],s['food_id']) for s in plan['selections'] if s.get('diversity_eligible',s['meal'] in ('lunch','dinner')) and not s.get('locked')}


def distance(a,b):
    return len(selection_keys(a)-selection_keys(b))


def family(food_id):
    if food_id in LEGUMES:return 'legumes'
    return {'106500':'white_meat','121410':'fish','181100':'eggs','123610':'fish','110020':'red_meat','110400':'red_meat','166000':'cheese','000720':'cheese','008540':'nuts','008570':'nuts'}.get(food_id)


def arms(plan):
    result=set()
    for s in plan['selections']:
        if s['meal'] not in ('lunch','dinner'):continue
        f=family(s['food_id'])
        if f:result.add('protein:'+f)
        starch={'000800':'pasta','000100':'rice','000530':'bread'}.get(s['food_id'])
        if starch:result.add('starch:'+starch)
    if not any(x.startswith('starch:') for x in result):result.add('starch:none')
    result.add('structure:single' if any(s['food_id']=='000720' for s in plan['selections']) else 'structure:components')
    return sorted(result)


def context_key(config):
    from contextual_bandit import context
    full=config.get('daily_meals',{}).get('enabled')
    return context(config['mode'],config.get('day_type','rest'),config['daily_meals']['targets'] if full else config['main_meals_targets'],'full_day_planned_meals' if full else 'lunch_and_dinner_only')


def sampled_front(plans):
    keys=('nutrition_error','worst_error','preference','variety')
    point=lambda p:tuple(p['objectives'][k]*(-1 if k in ('preference','variety') else 1) for k in keys)
    return [p for p in plans if not any(all(x<=y+1e-8 for x,y in zip(point(q),point(p))) and any(x<y-1e-8 for x,y in zip(point(q),point(p))) for q in plans if q is not p)]


def plan_diff(reference,plan):
    key=lambda s:(s['meal'],s['food_id'])
    before={key(s):s for s in reference['selections']};after={key(s):s for s in plan['selections']}
    item=lambda s:dict(meal=s['meal'],food=s['food'],food_id=s['food_id'],grams=s['grams'])
    changed=[]
    for k in sorted(before.keys() & after.keys()):
        a,b=before[k],after[k];delta=abs(a['grams']-b['grams'])
        if delta>=10 or delta/max(a['grams'],1)>=.15:changed.append(dict(meal=b['meal'],food=b['food'],food_id=b['food_id'],from_g=a['grams'],to_g=b['grams']))
    return dict(reference_plan='best',distance=distance(reference,plan),added=[item(after[k]) for k in sorted(after.keys()-before.keys())],removed=[item(before[k]) for k in sorted(before.keys()-after.keys())],changed=changed,nutrients={k:round(plan['nutrients'][k]-reference['nutrients'][k]) for k in reference['nutrients']})


def exploration_score(plan,observations):
    if isinstance(observations,dict):
        from contextual_bandit import ucb
        return ucb(plan,observations)
    counts={a:[] for a in plan['arms']}
    total=len(observations)
    for arm,reward in observations:
        if arm in counts:counts[arm].append(reward)
    untried=sum(not v for v in counts.values())
    score=sum(sum(v)/len(v)+math.sqrt(2*math.log(max(total,1))/len(v)) if v else 0 for v in counts.values())/max(len(counts),1)
    return (untried,score,-sum(map(len,counts.values())))


async def orchestrate_day(session,config,foods,request=None,history=(),observations=(),health=None,balance=None):
    request=request or {};config=copy.deepcopy(config)
    if 'day_type' in request:
        if request['day_type'] not in ('rest','training'):raise ValueError('Tipo di giornata non valido')
        config['day_type']=request['day_type']
    k=request.get('k',4);pool_size=request.get('pool_size',12);epsilon=request.get('epsilon',.05);seed=request.get('seed',20261004)
    div=request.get('diversity',{});minimum=div.get('min_distance',3);structural=div.get('structural',True)
    if any(isinstance(x,bool) or not isinstance(x,int) for x in (k,pool_size,seed,minimum)) or not 1<=k<=5 or not k<=pool_size<=30 or not 1<=minimum<=10 or not isinstance(structural,bool) or isinstance(epsilon,bool) or not isinstance(epsilon,(int,float)) or not math.isfinite(epsilon) or not 0<=epsilon<=1:
        raise ValueError('Parametri di orchestrazione non validi')
    if request.get('locked'):raise ValueError('Pasti bloccati richiedono la generazione settimanale o per pasto')
    targets=config['daily_meals']['targets'] if config.get('daily_meals',{}).get('enabled') else config['main_meals_targets']
    warnings=target_warnings(targets)
    if 'strategy' in request:warnings.append(dict(code='legacy_strategy_ignored',message='Il parametro strategy è ignorato: i metodi sono stadi della catena.'))
    problem,choices,slots=formulate(config,foods);base=copy.deepcopy(problem)
    context=context_key(config)
    if isinstance(observations,dict):observations=observations.get(context,[])
    envelope=dict(spec_version=VERSION,versions=dict(engine=VERSION,catalog=hashlib.sha256(json.dumps(foods,sort_keys=True).encode()).hexdigest(),rules=hashlib.sha256(json.dumps(dict(slots=slots,rules=load_rules(config)),sort_keys=True).encode()).hexdigest(),health_report=(health or {}).get('version')),request_hash=hashlib.sha256(json.dumps(dict(config=config,request=request,history=sorted(history),observations=list(observations),health=health,balance=balance),sort_keys=True).encode()).hexdigest(),horizon=dict(day_index=config['day_index'],days=1),mode=config['mode'],status='ok',warnings=warnings,pool=dict(candidates=0,front=0,epsilon=epsilon,min_distance=minimum,diversity_relaxed=[]),plans=[],seed=seed)
    start=time.monotonic();budget=request.get('time_limit',20)
    if isinstance(budget,bool) or not isinstance(budget,(int,float)) or not math.isfinite(budget) or not 1<=budget<=120:raise ValueError('Tempo massimo non valido')
    first=await solve_strategy(session,base,config,choices,'balanced')
    if first['mathematical_status'] not in ('optimal','feasible'):
        envelope.update(status='infeasible',infeasibility=dict(status=first['mathematical_status'],constraints='Limiti nutrizionali, porzioni, esclusioni e abbinamenti configurati'));return envelope
    if first['mathematical_status']!='optimal':
        envelope['status']='partial';warnings.append(dict(code='reference_not_optimal',message='Ottimo di riferimento non certificato; pool limitato al piano verificato.'))
    decoded=decode_result(config,base,choices,slots,foods,first)
    reference_error=sum(first['optimization']['relative_errors'].values());near=reference_error*(1+epsilon)+.01
    base['constraints'].append(dict(coefficients=problem['objective']['coefficients'][:],relation='<=',rhs=near))
    if first.get('preference_penalty') is not None:
        base['constraints'].append(dict(coefficients=problem['preference_coefficients'][:],relation='<=',rhs=first['preference_penalty']+1e-7))
    pool=[];seen=set();past=set(history)
    def collect(result,p,objective):
        record=decode_result(config,p,choices,slots,foods,result)
        if not record['constraint_report']['all_respected']:raise ValueError('Vincoli non verificati')
        signature=tuple(sorted((s['meal'],s['food_id']) for s in record['selections']))
        if signature in seen:return False
        seen.add(signature);safe={key:record[key] for key in SAFE};safe.update(mode=config['mode'],day_index=config['day_index'])
        errors=result['optimization']['relative_errors'];variable=selection_keys(safe)
        safe['objectives']=dict(nutrition_error=sum(errors.values()),worst_error=max(errors.values()),preference=1-(result.get('preference_penalty') or 0)/max(len(slots),1),variety=len(variable-past)/max(len(variable),1),prep_minutes=None)
        safe['optimization']=dict(stage='S2',objective=objective,near_optimal_gap=(sum(errors.values())-reference_error)/max(reference_error,.01),context=context,relative_errors=errors)
        safe['arms']=arms(safe)
        safe.update(day_type=config.get('day_type','rest'),targets=copy.deepcopy(targets),bandit_context=context,bandit_features=[dict(context=context,arms=safe['arms'])])
        safe['optimization']['bandit']=dict(version='contextual-bandit-v2',rating_weight=.5,adherence_weight=.5,observed_features=len(observations))
        rewards=[reward for arm,reward in observations if arm in safe['arms']]
        if rewards:safe['objectives']['preference']=sum(rewards)/len(rewards)
        pool.append(safe);return True
    collect(first,problem,'balanced')
    d=minimum;struct=structural;round_no=1
    while len(pool)<pool_size and envelope['status']!='partial':
        remaining=budget-(time.monotonic()-start)
        if remaining<=0:envelope['status']='partial';break
        p=copy.deepcopy(base);p['solver']['time_limit']=max(.1,remaining)
        for previous in pool:
            selected=selection_keys(previous);indices=[c['y'] for c in active_choices(choices) if (c['meal'],c['food_id']) in selected]
            row=[0.]*len(p['variables'])
            for i in indices:row[i]=1
            p['constraints'].append(dict(coefficients=row,relation='<=',rhs=len(selected)-d))
            if struct:
                for meal in ('lunch','dinner'):
                    protein=next((food for m,food in sorted(selected) if m==meal and family(food)),None);starch=next((food for m,food in sorted(selected) if m==meal and food in STARCH),None)
                    if protein and starch:
                        row=[0.]*len(p['variables'])
                        for c in active_choices(choices):
                            if c['meal']==meal and c['food_id'] in (protein,starch):row[c['y']]=1
                        p['constraints'].append(dict(coefficients=row,relation='<=',rhs=1))
        objective=('minmax','maxmin','preference','variety')[min(round_no-1,3)] if round_no<=4 else 'weighted'
        strategy=objective if objective in ('minmax','maxmin') else 'balanced';weights=None;custom=None
        if objective=='weighted':weights={NUTRIENTS[(round_no-5)%4].replace('_100g',''):4.}
        if objective in ('preference','variety'):
            custom=[0.]*len(p['variables'])
            used=past|set().union(*(selection_keys(x) for x in pool))
            if objective=='variety':
                for c in active_choices(choices):custom[c['y']]=1. if (c['meal'],c['food_id']) in used else -1.
            else:
                rewards={}
                for arm,reward in observations:rewards.setdefault(arm,[]).append(reward)
                for c in active_choices(choices):
                    arm='protein:'+str(family(c['food_id']));custom[c['y']]=-sum(rewards.get(arm,[]))/max(len(rewards.get(arm,[])),1)
        result=await solve_strategy(session,p,config,choices,strategy,weights,objective_override=custom)
        if result['mathematical_status'] in ('optimal','feasible'):
            collect(result,p,objective);round_no+=1
            if result['mathematical_status']!='optimal':envelope['status']='partial';break
        elif d>1 or struct:
            if d>1:d-=1
            else:struct=False
            envelope['pool']['diversity_relaxed'].append(dict(min_distance=d,structural=struct))
        else:break
    front=sampled_front(pool)
    usable=(health or {}).get('usable_consumption_baseline') and isinstance(balance,(int,float)) and not isinstance(balance,bool) and math.isfinite(balance)
    scenario=(health or {}).get('consumption_scenarios',{})
    if usable:
        values={key:scenario[key+'_kcal'] for key in ('low','central','high')}
        for plan in pool:plan['robustness']=dict(status='available',scenarios={key:abs(plan['nutrients']['kcal']-value-balance) for key,value in values.items()})
        minima={key:min(p['robustness']['scenarios'][key] for p in pool) for key in values}
        for plan in pool:
            losses=plan['robustness']['scenarios'];plan['robustness'].update(max_loss_kcal=max(losses.values()),max_regret_kcal=max(losses[key]-minima[key] for key in values))
    else:
        for plan in pool:plan['robustness']=dict(status='unavailable',reason='Base Salute o bilancio energetico obiettivo non disponibile.')
    chosen=[]
    def take(role,key,eligible=None):
        options=[p for p in front if p not in chosen and (eligible is None or eligible(p))]
        if options and len(chosen)<k:
            plan=sorted(options,key=key)[0];plan['role']=role;chosen.append(plan)
    take('best',lambda p:(p['objectives']['nutrition_error'],-p['objectives']['preference']))
    best=chosen[0]
    take('varied',lambda p:(-p['objectives']['variety'],p['objectives']['nutrition_error']),lambda p:distance(best,p)>=d)
    if usable:take('robust',lambda p:(p['robustness']['max_regret_kcal'],p['objectives']['nutrition_error']))
    if observations:take('preferred',lambda p:-p['objectives']['preference'])
    take('explore',lambda p:tuple(-x for x in exploration_score(p,observations)))
    headlines=dict(best='Il più vicino ai tuoi obiettivi',varied='Più vario: cambia gli alimenti principali',robust='Più sicuro se consumi meno/più del previsto',preferred='Con gli alimenti che apprezzi di più',explore='Da provare: una combinazione poco esplorata')
    for rank,plan in enumerate(chosen,1):
        plan['rank']=rank;plan['diff']=None if plan is best else plan_diff(best,plan)
        tradeoffs=[f'{key}: scarto peggiore di {100*(value-best["optimization"]["relative_errors"][key]):.1f} punti percentuali' for key,value in plan['optimization']['relative_errors'].items() if value-best['optimization']['relative_errors'][key]>.05]
        plan['explanation']=dict(headline=headlines[plan['role']],reasons=[f'Scarto nutrizionale relativo totale: {plan["objectives"]["nutrition_error"]:.3f}',*([f'{distance(best,plan)} alimenti principali diversi dal riferimento'] if plan is not best else [])][:3],tradeoffs=tradeoffs[:2])
    if len(chosen)>1 and envelope['pool']['diversity_relaxed']:warnings.append(dict(code='diversity_relaxed',message=f'Alternative limitate: distanza minima ridotta a {d}; diversità strutturale {"attiva" if struct else "ridotta"}.'))
    if len(chosen)==1:warnings.append(dict(code='limited_alternatives',message='Un solo piano non dominato disponibile entro i vincoli e il budget di calcolo.'))
    envelope['pool'].update(candidates=len(pool),front=len(front),min_distance=d,structural=struct,reference_error=reference_error,near_optimal_limit=near)
    envelope['plans']=chosen
    return envelope

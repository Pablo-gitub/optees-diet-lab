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
ENGINE_VERSION = 'orchestration-v3-gram-overlap'
SAFE = ['meal_timing','demo','scope','slots','status','selections','nutrients','nutrients_by_meal','daily_policy','diet_note','preference_penalty','preference_changes','constraint_report']


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
        if s.get('match_id'):result.add('match:'+s['match_id'])
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
    envelope=dict(spec_version=VERSION,versions=dict(engine=ENGINE_VERSION,catalog=hashlib.sha256(json.dumps(foods,sort_keys=True).encode()).hexdigest(),rules=hashlib.sha256(json.dumps(dict(slots=slots,rules=load_rules(config)),sort_keys=True).encode()).hexdigest(),health_report=(health or {}).get('version')),request_hash=hashlib.sha256(json.dumps(dict(config=config,request=request,history=sorted(history),observations=list(observations),health=health,balance=balance),sort_keys=True).encode()).hexdigest(),horizon=dict(day_index=config['day_index'],days=1),mode=config['mode'],status='ok',warnings=warnings,pool=dict(candidates=0,front=0,epsilon=epsilon,min_distance=minimum,diversity_relaxed=[],overlap_target=10,overlap_achieved=None),plans=[],seed=seed)
    start=time.monotonic();budget=request.get('time_limit',20)
    if isinstance(budget,bool) or not isinstance(budget,(int,float)) or not math.isfinite(budget) or not 1<=budget<=120:raise ValueError('Tempo massimo non valido')
    first=await solve_strategy(session,base,config,choices,'balanced')
    if first['mathematical_status'] not in ('optimal','feasible'):
        envelope.update(status='infeasible',infeasibility=dict(status=first['mathematical_status'],constraints='Limiti nutrizionali, porzioni, esclusioni e abbinamenti configurati'));return envelope
    if first['mathematical_status']!='optimal':
        envelope['status']='partial';warnings.append(dict(code='reference_not_optimal',message='Ottimo di riferimento non certificato; si cercano comunque altre combinazioni fattibili.'))
    decode_result(config,base,choices,slots,foods,first)
    if 'optimization' not in first:
        by_name={v['name']:v['value'] for v in first['result']['variables']}
        errors={n.replace('_100g',''):abs(sum(c['nutrients'][j]*by_name[problem['variables'][c['q']]['name']] for c in choices)-targets[n]['target'])/targets[n]['target'] for j,n in enumerate(NUTRIENTS)}
        first['optimization']=dict(relative_errors=errors,strategy='balanced_uncertified')
    reference_error=sum(first['optimization']['relative_errors'].values());near=reference_error*(1+epsilon)+.01
    pool=[];seen=set();past=set(history)
    def collect(result,p,objective):
        if problem.get('preference_coefficients'):
            by_name={v['name']:v['value'] for v in result['result']['variables']}
            result['preference_penalty']=sum(coef*by_name[var['name']] for coef,var in zip(problem['preference_coefficients'],problem['variables']))
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
    from ingredient_overlap import minimax_candidate,report,amounts,overlap
    existing=request.get('_existing_plans',[]);slot=config.get('alternative_slot')
    if existing:pool.clear();seen.clear()
    d=0;struct=False;searches=[]
    # Diversity optimizes within the original nutritional/portion constraints.
    # Near-optimal error and preference are soft goals, not feasibility bounds.
    while len(pool)<pool_size:
        if time.monotonic()-start>=budget:
            searches.append(dict(certified=False,reason='Tempo di calcolo esaurito.'))
            envelope['status']='partial';break
        previous=existing+pool
        if not any(not c.get('locked') and (not slot or c['meal']==slot) for c in choices):break
        p=copy.deepcopy(problem)
        for prior in previous:
            selected={(s['meal'],s['food_id']) for s in prior['selections'] if (not slot or s['meal']==slot) and not s.get('locked')}
            eligible=[c for c in choices if (not slot or c['meal']==slot) and not c.get('locked')]
            row=[0.]*len(p['variables'])
            for c in eligible:
                if (c['meal'],c['food_id']) in selected:row[c['y']]=1
            if selected:p['constraints'].append(dict(coefficients=row,relation='<=',rhs=len(selected)-1))
        strategy='diversity_minimax'
        async def solve(candidate):
            active=copy.deepcopy(candidate);active.pop('preference_coefficients',None)
            return await solve_strategy(session,active,config,choices,'balanced',objective_override=[0.]*len(active['variables']))
        r,p,certificate=await minimax_candidate(p,choices,previous,foods,solve,start+budget,config,slot)
        searches.append(certificate)
        if r is None:
            if not certificate.get('certified'):envelope['status']='partial'
            break
        record=decode_result(config,p,choices,slots,foods,r)
        actual=max((overlap(amounts(record,foods,config,slot),amounts(prior,foods,config,slot)) for prior in previous),default=0)
        if actual>certificate['threshold']+1e-6:raise ValueError('Sovrapposizione non verificata')
        if existing and actual>.5+1e-6:break
        if not collect(r,p,strategy):break
    envelope['pool']['overlap_searches']=searches
    front=sampled_front(pool)
    if not pool:
        report(envelope,[],foods,config,slot,existing)
        envelope.update(status='no_more_alternatives',reason='Non ci sono altre alternative abbastanza diverse entro i vincoli e il budget.');return envelope
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
    best=chosen[0] if chosen else None
    take('varied',lambda p:(-p['objectives']['variety'],p['objectives']['nutrition_error']),lambda p:distance(best,p)>=d)
    if usable:take('robust',lambda p:(p['robustness']['max_regret_kcal'],p['objectives']['nutrition_error']))
    if observations:take('preferred',lambda p:-p['objectives']['preference'])
    take('explore',lambda p:tuple(-x for x in exploration_score(p,observations)))
    for extra in pool:
        if len(chosen)>=min(k,3):break
        if extra not in chosen:
            extra['role']='alternative_'+str(len(chosen)+1);chosen.append(extra)
    if not chosen:
        envelope['plans']=[];report(envelope,[],foods,config,slot,existing)
        envelope.update(status='no_more_alternatives',reason='Non ci sono altre alternative abbastanza diverse entro i vincoli e il budget.');return envelope
    headlines=dict(best='Il più vicino ai tuoi obiettivi',varied='Più vario: cambia gli alimenti principali',robust='Più sicuro se consumi meno/più del previsto',preferred='Con gli alimenti che apprezzi di più',explore='Da provare: una combinazione poco esplorata')
    for rank,plan in enumerate(chosen,1):
        plan['rank']=rank;plan['diff']=None if plan is best else plan_diff(best,plan)
        tradeoffs=[f'{key}: scarto peggiore di {100*(value-best["optimization"]["relative_errors"][key]):.1f} punti percentuali' for key,value in plan['optimization']['relative_errors'].items() if value-best['optimization']['relative_errors'][key]>.05]
        if plan not in front:tradeoffs.append('Alternative fattibile aggiunta per offrire almeno tre scelte; fuori dal fronte Pareto campionato.')
        plan['explanation']=dict(headline=headlines.get(plan['role'],'Un’altra combinazione fattibile'),reasons=[f'Scarto nutrizionale relativo totale: {plan["objectives"]["nutrition_error"]:.3f}',*([f'{distance(best,plan)} alimenti principali diversi dal riferimento'] if plan is not best else [])][:3],tradeoffs=tradeoffs[:2])
    if len(chosen)>1 and envelope['pool']['diversity_relaxed']:warnings.append(dict(code='diversity_relaxed',message=f'Alternative limitate: distanza minima ridotta a {d}; diversità strutturale {"attiva" if struct else "ridotta"}.'))
    if len(chosen)==2 and k>=3:warnings.append(dict(code='limited_alternatives',message='Solo due alternative verificate entro i vincoli e il tempo disponibile.'))
    if len(chosen)==1:warnings.append(dict(code='limited_alternatives',message='Un solo piano non dominato disponibile entro i vincoli e il budget di calcolo.'))
    envelope['pool'].update(candidates=len(pool),front=len(front),min_distance=d,structural=struct,reference_error=reference_error,near_optimal_limit=near,near_optimal_enforced=False,nutritional_constraints_relaxed=False)
    envelope['plans']=chosen
    report(envelope,chosen,foods,config,slot,existing)
    return envelope

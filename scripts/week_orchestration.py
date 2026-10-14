"""Seven-day MILP with shared repetition constraints and meal-lock reoptimization."""
import copy
import datetime as dt
import hashlib
import json
import math
import time
from plan_diet_day import formulate,decode_result,optimize_day,NUTRIENTS
from plan_recipe import values_verified
from multiobjective_day import extend
from day_orchestration import family,sampled_front,arms,plan_diff,exploration_score,context_key
from diary_service import DomainError,valid_date,valid_slot,resolve_food,quantity,day_view,SLOTS


def add_lock(config,foods,slot,items,profile):
    valid_slot(slot)
    fixed=[]
    for item in items:
        ref=item.get('food');food=resolve_food(ref,profile);grams,units=quantity(item,food)
        if any(v is None for v in food['per_100g'].values()):raise DomainError('Nutrienti mancanti nel pasto bloccato: impossibile verificare il bilancio')
        identifier=ref['id'] if ref['source']=='CREA' else ('personal:' if ref['source']=='user_label' else 'locked:'+ref['source']+':')+ref['id']
        foods[identifier]=dict(name=food['name'],source=ref['source'],source_id=ref['id'],composition_provenance=food.get('composition_provenance'),fiber_g_100g=food.get('fiber_g_100g'),nutrient_ranges=food.get('nutrient_ranges'),recipe_id=food.get('recipe_id'),principal_food_id=food.get('principal_food_id'),**{n:str(food['per_100g'][n.replace('_100g','')]) for n in NUTRIENTS})
        fixed.append(dict(food_id=identifier,grams=grams,units=units,source=ref['source'],reference_id=ref['id']))
    config.setdefault('locked_meals',{})[slot]=fixed


def weekly_model(profile,request,make_config,foods):
    import recipe_intents
    profile=copy.deepcopy(profile)
    request,recipe_ids,intents=recipe_intents.prepare(profile,request)
    start=dt.date.fromisoformat(valid_date(request.get('week_start')));index=request.get('day_index',start.weekday())
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<14:raise DomainError('Indice della dieta non valido')
    maximum=request.get('max_protein_repetitions',3)
    if isinstance(maximum,bool) or not isinstance(maximum,int) or not 1<=maximum<=14:raise DomainError('Limite ripetizioni non valido')
    raw_locks=request.get('locked',[])
    if not isinstance(raw_locks,list):raise DomainError('Blocchi non validi')
    locks={}
    for entry in raw_locks:
        if not isinstance(entry,dict):raise DomainError('Blocco non valido')
        date=valid_date(entry.get('date'));slot=valid_slot(entry.get('slot'));items=entry.get('items')
        if not isinstance(items,list):raise DomainError('Alimenti del blocco non validi')
        if not start<=dt.date.fromisoformat(date)<=start+dt.timedelta(days=6):raise DomainError('Blocco esterno alla settimana')
        if (date,slot) in locks:raise DomainError('Blocco duplicato')
        locks[date,slot]=items
    blocks=[];variables=[];sparse_rows=[];objectives=[];preferences=[];all_choices=[]
    for offset in range(7):
        date=(start+dt.timedelta(days=offset)).isoformat()
        if request.get('_active_dates') is not None and date not in request['_active_dates']:continue
        model_index=len(blocks);config=make_config(profile,(index+offset)%14)
        config['_match_cards']=copy.deepcopy(profile.get('_match_cards',[]))
        config['_match_profile']=profile
        config.setdefault('_timing_profile',profile)
        config.setdefault('_timing_sessions',profile.get('_timing_sessions_by_date',{}).get(date,[]))
        config['portion_bounds_g']=request.get('portion_bounds_g',config.get('portion_bounds_g',{}))
        for (lock_date,slot),items in locks.items():
            if lock_date==date:add_lock(config,foods,slot,items,profile)
        recipe_intents.configure(config,foods,profile,recipe_ids)
        if intents and (not config.get('daily_meals',{}).get('enabled') or config['daily_meals'].get('targets_demo',True)):raise DomainError('Per un piatto bloccato servono target personali confermati per la giornata intera','full_day_targets_required')
        if intents and config.get('daily_meals',{}).get('enabled'):
            config['daily_meals']=copy.deepcopy(config['daily_meals'])
            from meal_rebalance import FLOORS
            target=config['daily_meals']['targets']
            for key,minimum in FLOORS.items():target[key]['min']=max(target[key]['min'],minimum)
            center=target['kcal_100g']['target']
            scheduled=profile.get('_scheduled_energy_by_date',{}).get(date)
            fallback=scheduled.get('consumption_kcal',{}).get('low') if scheduled else profile.get('_energy_baseline_low')
            low=config.get('_energy_low',fallback)
            if isinstance(low,bool) or not isinstance(low,(int,float)) or not math.isfinite(low) or low<=0:raise DomainError('Serve uno scenario energetico basso verificabile per programmare il rientro anticipato','energy_scenario_unavailable')
            target['kcal_100g']['min']=max(target['kcal_100g']['min'],center-200,low-500)
            target['kcal_100g']['max']=min(target['kcal_100g']['max'],center+200)
            if any(spec['min']>spec['max'] for spec in target.values()):raise DomainError('I target personali non ammettono un rientro anticipato entro i minimi e il deficit massimo','unsafe_proposal')
            for spec in target.values():spec['target']=max(spec['min'],min(spec['target'],spec['max']))
            config['_anticipatory_rebalance']=True
        for dish in intents.get(date,[]):
            if config['mode']!='free':
                if dish['kind']!='recipe':raise DomainError('Gli ingredienti di un piatto stimato non permettono di verificare gli abbinamenti della dieta','dish_compatibility_unavailable')
                from recipe_diet_compatibility import meal_options
                check=meal_options(config['mode'],config['day_index'],dish['slot'],[recipe_intents.template(dish['recipe']['id'])])['recipes'][0]
                if check['status']=='needs_review':raise DomainError('Gli abbinamenti del piatto bloccato non sono verificati per questo pasto','dish_compatibility_unavailable')
                if check['status']=='needs_complements':
                    config['locked_meals'].pop(dish['slot'])
                    config.setdefault('_locked_recipe_by_slot',{})[dish['slot']]=dish['recipe']
        p,choices,slots=formulate(config,foods);shift=len(variables)
        variables.extend(dict(v,name=f'd{model_index}_{v["name"]}') for v in p['variables'])
        sparse_rows.extend(({i+shift:v for i,v in enumerate(r['coefficients']) if v},r['relation'],r['rhs']) for r in p['constraints'])
        objectives.extend(p['objective']['coefficients']);preferences.extend(p.get('preference_coefficients',[0.]*len(p['variables'])))
        for c in choices:
            c['principal_food_id']=c.get('principal_food_id') or foods[c['food_id']].get('principal_food_id')
        frequency_id=lambda c:c.get('principal_food_id') or c['food_id']
        for c in choices:
            candidates=[other['group'] for other in choices if other['meal']==c['meal'] and other['combination']==c['combination'] and other['branch_index']==c['branch_index'] and family(frequency_id(other))]
            c['principal_protein']=bool(family(frequency_id(c))) and c['group']==max(candidates,default=-1)
            recipe_main=next((other for other in choices if other['meal']==c['meal'] and other['combination']==c['combination'] and other['branch_index']==c['branch_index'] and other.get('recipe_id') and family(frequency_id(other))),None)
            if recipe_main:c['principal_protein']=c is recipe_main
            if c.get('locked'):
                fixed=[other for other in choices if other['meal']==c['meal'] and other.get('locked') and family(frequency_id(other))]
                principal=max(fixed,key=lambda other:(other['nutrients'][1]*other.get('locked_grams',p['variables'][other['q']]['lb']),other['food_id']),default=None)
                c['principal_protein']=c is principal and c['nutrients'][1]>0
        all_choices.extend(dict(c,q=c['q']+shift,y=c['y']+shift,date=date,day=offset) for c in choices)
        blocks.append(dict(date=date,config=config,problem=p,choices=choices,slots=slots,shift=shift))
    # Count a principal source once per meal, even if it appears in multiple components.
    families=sorted({c.get('principal_food_id') or c['food_id'] for c in all_choices if c.get('principal_protein')})
    freq={f:[] for f in families}
    for block in blocks:
        for slot in ('lunch','dinner'):
            for f in families:
                ys=[c['y'] for c in all_choices if c['date']==block['date'] and c['meal']==slot and (c.get('principal_food_id') or c['food_id'])==f and c.get('principal_protein')]
                if not ys:continue
                indicator=len(variables);variables.append(dict(name=f'frequency_{block["date"]}_{slot}_{f}',lb=0,ub=1,integrality='B'));objectives.append(0.);preferences.append(0.);freq[f].append(indicator)
                for y in ys:sparse_rows.append(({y:1,indicator:-1},'<=',0))
                sparse_rows.append(({indicator:1,**{y:-1 for y in ys}},'<=',0))
    for f,indices in freq.items():sparse_rows.append(({i:1 for i in indices},'<=',max(0,maximum-request.get('_prior_frequencies',{}).get(f,0))))
    # Optional reviewed frequency rules are explicit hard bounds, never inferred.
    frequencies=request.get('protein_frequencies',{})
    if not isinstance(frequencies,dict) or any(f not in freq for f in frequencies):raise DomainError('Frequenze non valide')
    for f,spec in frequencies.items():
        if not isinstance(spec,dict):raise DomainError('Frequenza non valida')
        low,high=spec.get('min',0),spec.get('max',maximum)
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (low,high)) or not 0<=low<=high<=maximum:raise DomainError('Frequenza non valida')
        sparse_rows.extend([({i:1 for i in freq[f]},'>=',low),({i:1 for i in freq[f]},'<=',high)])
    # Provisional variety tie-break: principal source repeats beyond two meals.
    # The existing hard maximum is unchanged. Weight is explicit and small.
    for f,indices in (freq.items() if request.get('_variety_penalty',False) else []):
        repeat=len(variables);variables.append(dict(name='repeat_excess_'+f,lb=0,ub=14,integrality='C'));objectives.append(.002);preferences.append(0.)
        sparse_rows.append(({**{i:1 for i in indices},repeat:-1},'<=',2))
    recipe_choices={}
    for c in all_choices:
        recipe_id=c.get('recipe_id') or foods[c['food_id']].get('recipe_id')
        if recipe_id:recipe_choices.setdefault(recipe_id,[]).append(c['y'])
    for recipe_id,ys in recipe_choices.items():sparse_rows.append(({y:1 for y in ys},'<=',recipe_intents.MAX_OCCURRENCES))
    match_ys={}
    for c in all_choices:
        if c.get('match_id'):match_ys.setdefault(c['match_id'],set()).add(c['y'])
    from meal_matches import POLICY as match_policy
    for ys in match_ys.values():sparse_rows.append(({y:1 for y in ys},'<=',match_policy['maximum_weekly_occurrences']))
    if intents:
        # Worst-case deviation from the original weekly energy target;
        # fixed interval plates are checked on both ends, never treated as zero.
        lower={};upper={};target_sum=0
        for b in blocks:
            targets=b['config']['daily_meals']['targets'] if b['config'].get('daily_meals',{}).get('enabled') else b['config']['main_meals_targets']
            target_sum+=targets['kcal_100g']['target']
            for c in b['choices']:
                ranges=foods[c['food_id']].get('nutrient_ranges')
                lower[c['q']+b['shift']]=(ranges['kcal']['min']/100 if ranges else c['nutrients'][0])
                upper[c['q']+b['shift']]=(ranges['kcal']['max']/100 if ranges else c['nutrients'][0])
        deviation=len(variables);variables.append(dict(name='anticipatory_weekly_deviation',lb=0,ub=1000000,integrality='C'));objectives.append(10/max(1,target_sum));preferences.append(0.)
        sparse_rows.extend([({**upper,deviation:-1},'<=',target_sum),({**{j:-v for j,v in lower.items()},deviation:-1},'<=',-target_sum)])
        kcal_rows=[]
        for block in blocks:
            row={c['q']+block['shift']:c['nutrients'][0] for c in block['choices']}
            center=(block['config']['daily_meals']['targets'] if block['config'].get('daily_meals',{}).get('enabled') else block['config']['main_meals_targets'])['kcal_100g']['target']
            kcal_rows.append((row,center))
        for i,(row,center) in enumerate(kcal_rows):
            for j in range(i+1,len(kcal_rows)):
                if blocks[i]['date'] in intents or blocks[j]['date'] in intents:continue
                other,other_center=kcal_rows[j]
                diff={k:row.get(k,0)-other.get(k,0) for k in set(row)|set(other)}
                sparse_rows.extend([(diff,'<=',center-other_center+25),(diff,'>=',center-other_center-25)])
    size=len(variables);dense=lambda r:[r.get(i,0.) for i in range(size)]
    problem=dict(version='1',variables=variables,constraints=[dict(coefficients=dense(row),relation=relation,rhs=rhs) for row,relation,rhs in sparse_rows],objective=dict(sense='min',coefficients=objectives),solver=dict(time_limit=request.get('solve_time_limit',15),mip_gap=0.05))
    timing={}
    for block in blocks:
        for i,v in enumerate(block['problem'].get('timing_coefficients',[])):
            if v:timing[i+block['shift']]=v
    if timing:
        problem['timing_coefficients']=dense(timing)
        problem['timing_kcal_rows']=[dense({c['q']+b['shift']:c['nutrients'][0] for c in b['choices']}) for b in blocks]
    if any(preferences):problem['preference_coefficients']=preferences
    return problem,blocks,all_choices,maximum


def decode_week(problem,blocks,foods,result,maximum):
    clean=copy.deepcopy(problem);clean.pop('preference_coefficients',None);values_verified(clean,result)
    by_name={v['name']:v['value'] for v in result['result']['variables']};days=[]
    for offset,block in enumerate(blocks):
        sub=dict(mathematical_status=result['mathematical_status'],validation=result['validation'],result=dict(variables=[dict(name=v['name'],value=by_name[f'd{offset}_{v["name"]}']) for v in block['problem']['variables']]))
        if 'timing_optimization' in result:sub['timing_optimization']=copy.deepcopy(result['timing_optimization'])
        day=decode_result(block['config'],block['problem'],block['choices'],block['slots'],foods,sub)
        day={k:v for k,v in day.items() if k not in ('config','result','excluded_for_missing_nutrients','crea_sha256')}
        day_targets=block['config']['daily_meals']['targets'] if block['config'].get('daily_meals',{}).get('enabled') else block['config']['main_meals_targets']
        day.update(_recipe_snapshots=copy.deepcopy(block['config'].get('_recipe_snapshots',{})),_dish_estimates=copy.deepcopy(block['config'].get('_dish_estimates',{})),_recipe_unavailable=block['config'].get('_recipe_unavailable',[]),_recipe_candidates_summary=block['config'].get('_recipe_candidates_summary',[]),day_type=block['config'].get('day_type','rest'),bandit_context=context_key(block['config']),targets=copy.deepcopy(day_targets),date=block['date'],mode=block['config']['mode'],day_index=block['config']['day_index'],locked_slots=list(set(block['config'].get('locked_meals',{}))|set(block['config'].get('_locked_recipe_by_slot',{}))))
        if not day['constraint_report']['all_respected']:raise DomainError('Vincoli della giornata non verificati')
        days.append(day)
    frequencies={}
    for day in days:
        for slot in ('lunch','dinner'):
            for f in {s.get('principal_food_id') or s['food_id'] for s in day['selections'] if s['meal']==slot and s.get('principal_protein')}:frequencies[f]=frequencies.get(f,0)+1
    if any(v>maximum for v in frequencies.values()):raise DomainError('Frequenze non rispettate')
    targets=blocks[0]['config']['daily_meals']['targets'] if blocks[0]['config'].get('daily_meals',{}).get('enabled') else blocks[0]['config']['main_meals_targets']
    errors=[abs(day['nutrients'][n.replace('_100g','')]-day['targets'][n]['target'])/day['targets'][n]['target'] for day in days for n in NUTRIENTS]
    penalty=sum(c*by_name[v['name']] for c,v in zip(problem.get('preference_coefficients',[]),problem['variables']))
    recipe_counts={}
    for d in days:
        for sel in d['selections']:
            if sel.get('recipe_id'):recipe_counts[sel['recipe_id']]=recipe_counts.get(sel['recipe_id'],0)+1
    if any(v>__import__('recipe_intents').MAX_OCCURRENCES for v in recipe_counts.values()):raise DomainError('Frequenza ricette non verificata')
    decoded=dict(preference_penalty=penalty,bandit_features=[dict(context=d['bandit_context'],arms=arms(d)) for d in days],days=days,targets=targets,targets_by_date={d['date']:d['targets'] for d in days},nutrients={n:round(sum(day['nutrients'][n] for day in days),3) for n in days[0]['nutrients']},objectives=dict(nutrition_error=sum(errors),worst_error=max(errors),preference=1-penalty/max(len(days)*3,1),variety=len({s['food_id'] for day in days for s in day['selections']})/max(sum(len(day['selections']) for day in days),1),prep_minutes=None),constraint_report=dict(verified=True,all_respected=True,protein_frequencies=frequencies,max_protein_repetitions=maximum,frequency_scope='principal_food_id_per_meal'),arms=sorted(set(a for day in days for a in arms(day))),robustness=dict(status='unavailable',reason='Robustezza congiunta settimanale prevista nel passo 4.2.'))

    import recipe_intents
    decoded['recipe_preferences']=recipe_intents.explain(decoded,dict(_preferred_recipe_ids=blocks[0]['config'].get('_preferred_recipe_ids',[])))
    decoded['constraint_report']['recipe_frequencies']=recipe_counts
    if any(b['config'].get('_anticipatory_rebalance') for b in blocks):
        target=sum(d['targets']['kcal_100g']['target'] for d in days)
        observed={side:sum(d['nutrient_ranges']['kcal'][side] for d in days) for side in ('min','max')}
        error=max(abs(v-target) for v in observed.values())
        decoded['anticipatory_rebalance']=dict(status='full' if error<=1 else 'partial',target_week_kcal=target,planned_week_kcal=observed,worst_deviation_kcal=round(error,3),limits=dict(maximum_energy_deficit_kcal=500,maximum_daily_target_adjustment_kcal=200,maximum_spread_kcal=25),explanation='Bilancio settimanale ottimizzato senza rilassare i minimi: scostamento residuo mostrato anche quando un rientro completo non entra nei limiti.')
    return decoded


def week_keys(plan):return {(day['date'],s['meal'],s['food_id']) for day in plan['days'] for s in day['selections'] if s['meal'] in ('lunch','dinner') and s['meal'] not in day.get('locked_slots',[])}


async def generate_week(session,profile,request,make_config,foods,history=(),observations=()):
    from plan_diet_day import solve_problem
    foods=copy.deepcopy(foods);problem,blocks,choices,maximum=weekly_model(profile,dict(request,_variety_penalty=True),make_config,foods)
    warnings=[]
    from target_validation import target_warnings
    for block in blocks:
        targets=block['config']['daily_meals']['targets'] if block['config'].get('daily_meals',{}).get('enabled') else block['config']['main_meals_targets']
        for w in target_warnings(targets):
            if w not in warnings:warnings.append(w)
    result=dict(spec_version='orchestration-v2',mode=profile['mode'],week_start=request['week_start'],horizon=dict(days=7),status='ok',warnings=warnings,plans=[],pool=dict(candidates=0,front=0,min_distance=3,diversity_relaxed=[],overlap_target=10,overlap_achieved=None),request_hash=hashlib.sha256(json.dumps(dict(profile=profile,request=request),sort_keys=True).encode()).hexdigest(),seed=request.get('seed',20261004),versions=dict(engine='weekly-milp-v2-gram-overlap',catalog=hashlib.sha256(json.dumps(foods,sort_keys=True).encode()).hexdigest()))
    from ingredient_overlap import demo_week_feasibility
    feasibility=demo_week_feasibility(blocks)
    if feasibility:result['pool']['overlap_feasibility']=feasibility
    first=await optimize_day(session,problem)
    if first['mathematical_status'] not in ('optimal','feasible'):result['status']='infeasible';return result
    reference=decode_week(problem,blocks,foods,first,maximum);pool=[reference];original=problem['objective']['coefficients'];raw=copy.deepcopy(problem);raw.pop('preference_coefficients',None)
    vals=values_verified(raw,first);z=sum(a*b for a,b in zip(original,vals));epsilon=request.get('epsilon',.05)
    if isinstance(epsilon,bool) or not isinstance(epsilon,(int,float)) or not math.isfinite(epsilon) or not 0<=epsilon<=1:raise DomainError('Epsilon non valido')
    k=request.get('k',4);pool_size=request.get('pool_size',6);minimum=3;structural=True
    if any(isinstance(v,bool) or not isinstance(v,int) for v in (k,pool_size)) or not 1<=k<=5 or not k<=pool_size<=12:raise DomainError('Numero alternative non valido')
    start=time.monotonic();budget=request.get('time_limit',45)
    if not isinstance(budget,(int,float)) or isinstance(budget,bool) or not math.isfinite(budget) or not 1<=budget<=180:raise DomainError('Tempo massimo non valido')
    if first['mathematical_status']!='optimal':result['status']='partial';warnings.append(dict(code='reference_not_optimal',message='Settimana fattibile verificata; ottimo non certificato entro il tempo disponibile.'))
    from ingredient_overlap import minimax_candidate,report,amounts,overlap
    existing=request.get('_existing_plans',[])
    if existing:pool=[]
    minimum=0;structural=False;searches=[]
    while len(pool)<pool_size:
        remaining=budget-(time.monotonic()-start)
        if remaining<=0:
            searches.append(dict(certified=False,reason='Tempo di calcolo esaurito.'))
            result['status']='partial';break
        previous=existing+pool;p=copy.deepcopy(problem);p.pop('preference_coefficients',None)
        for prior in previous:
            keys=week_keys(prior);row=[0.]*len(p['variables'])
            for c in choices:
                if not c.get('locked') and (c['date'],c['meal'],c['food_id']) in keys:row[c['y']]=1
            if keys:p['constraints'].append(dict(coefficients=row,relation='<=',rhs=len(keys)-1))
        async def solve(candidate):
            active=copy.deepcopy(candidate);active['objective']['coefficients']=[0.]*len(active['variables'])
            return await solve_problem(session,active)
        candidate,p,certificate=await minimax_candidate(p,choices,previous,foods,solve,start+budget,profile)
        searches.append(certificate)
        if candidate is None:
            if not certificate.get('certified'):result['status']='partial'
            break
        import nutrient_timing
        if p.get('timing_coefficients') and time.monotonic()>=start+budget:
            candidate['timing_optimization']=dict(status='unavailable',reason='Tempo esaurito: mantenuto il candidato verificato senza redistribuzione.',daily_kcal_unchanged=True)
        else:
            if p.get('timing_coefficients'):p['solver']['time_limit']=min(p['solver'].get('time_limit',15),max(.1,start+budget-time.monotonic()))
            candidate=await nutrient_timing.refine(session,p,candidate,solve_problem)
        values_verified(p,candidate);plan=decode_week(problem,blocks,foods,candidate,maximum)
        actual=max((overlap(amounts(plan,foods,profile),amounts(prior,foods,profile)) for prior in previous),default=0)
        if actual>certificate['threshold']+1e-6:raise DomainError('Sovrapposizione non verificata')
        if existing and actual>.5+1e-6:break
        pool.append(plan)
    result['pool']['overlap_searches']=searches
    if not pool:
        result.update(status='no_more_alternatives',reason='Non ci sono altre alternative abbastanza diverse entro i vincoli e il budget.')
        report(result,[],foods,profile,existing=existing);return result
    for plan in pool:
        from contextual_bandit import rewards as contextual_rewards
        rewards=contextual_rewards(plan,observations)
        if rewards:plan['objectives']['preference']=sum(rewards)/len(rewards)
        if history:
            ids={s['food_id'] for day in plan['days'] for s in day['selections']}
            plan['objectives']['variety']=len(ids-set(history))/max(len(ids),1)
    front=sampled_front(pool);front.sort(key=lambda p:(p['objectives']['nutrition_error'],-p['objectives']['variety']))
    best=front[0];selected=[best]
    if len(front)>1:selected.append(max(front[1:],key=lambda p:p['objectives']['variety']))
    roles=['best']+(['varied'] if len(selected)>1 else [])
    if any(contextual_rewards(p,observations) for p in front) and len(selected)<k:
        options=[p for p in front if p not in selected]
        if options:selected.append(max(options,key=lambda p:p['objectives']['preference']));roles.append('preferred')
    options=[p for p in front if p not in selected]
    if options and len(selected)<k:selected.append(max(options,key=lambda p:exploration_score(p,observations)));roles.append('explore')
    for extra in pool:
        if len(selected)>=min(k,3):break
        if extra not in selected:selected.append(extra);roles.append('alternative_'+str(len(selected)))
    selected=selected[:k];context=context_key(blocks[0]['config'])
    headlines=dict(best='Il più vicino ai tuoi obiettivi',varied='Più varia durante la settimana',preferred='Con gli alimenti che apprezzi di più',explore='Da provare: una settimana diversa')
    for i,plan in enumerate(selected):
        plan.update(role=roles[i],rank=i+1,status='optimal' if result['status']=='ok' else 'feasible',mode=profile['mode'],demo=any(d['demo'] for d in plan['days']),optimization=dict(bandit=dict(version='contextual-bandit-v2',rating_weight=.5,adherence_weight=.5),stage='S2',context=context,near_optimal_gap=(plan['objectives']['nutrition_error']-reference['objectives']['nutrition_error'])/max(reference['objectives']['nutrition_error'],.01)),explanation=dict(headline=headlines.get(roles[i],'Un’altra settimana fattibile'),reasons=['Vincoli giornalieri e frequenze settimanali verificati'],tradeoffs=[]),diff=None if i==0 else dict(reference_plan='best',distance=len(week_keys(best)-week_keys(plan)),days=[dict(date=d['date'],**plan_diff(b,d)) for b,d in zip(best['days'],plan['days'])]))
    for plan in selected:
        if plan not in front:plan['explanation']['tradeoffs'].append('Alternative fattibile aggiunta per offrire almeno tre scelte; fuori dal fronte Pareto campionato.')
    result['plans']=selected;result['pool'].update(candidates=len(pool),front=len(front),min_distance=minimum,structural=structural,epsilon=epsilon,reference_error=reference['objectives']['nutrition_error'],reference_objective=z,near_optimal_objective_scope='nutrition_deviation_with_explicit_soft_preferences_and_weekly_balance',near_optimal_limit=z+abs(z)*epsilon+.01,near_optimal_enforced=False,nutritional_constraints_relaxed=False)
    result['pool']['within_week_variety']=dict(scope='principal_food_id_per_meal',repeat_threshold=2,excess_weight=.002,hard_max=maximum)
    if len(selected)<min(k,3):warnings.append(dict(code='limited_alternatives',message=f'Solo {len(selected)} alternative verificate entro i vincoli e il tempo disponibile.'))
    if result['pool']['diversity_relaxed']:warnings.append(dict(code='diversity_relaxed',message=f'Diversità settimanale ridotta a {minimum} alimenti.'))
    report(result,selected,foods,profile,existing=existing)
    return result


def generate_meal_alternatives(db,user,profile,request,make_config):
    from day_orchestration import orchestrate_day
    from plan_diet_day import load_foods
    date=valid_date(request.get('date'));slot=valid_slot(request.get('slot'));view=day_view(db,user,profile,date)
    current=next(m for m in view['meals'] if m['slot']==slot)
    if current['state']!='unknown':raise DomainError('Pasto già registrato','slot_already_logged',409)
    if not current['planned']:raise DomainError('Pasto non pianificato','not_found',404)
    if current['planned']['locked']:raise DomainError('Pasto bloccato','slot_locked',409)
    if view['week_plan_id']:
        week=db.execute('SELECT * FROM week_plan WHERE id=? AND user_id=?',(view['week_plan_id'],user)).fetchone()
        profile=copy.deepcopy(profile);profile['mode']=view['mode'];index=current['planned'].get('day_index',0)
        if profile.get('daily_meals',{}).get('enabled'):profile['daily_meals']['targets']={n:view['targets'][n.replace('_100g','')] for n in NUTRIENTS}
    else:index=0
    config=make_config(profile,index);config['alternative_slot']=slot;config['day_type']='training' if view['day_type']=='training' else 'rest';foods=load_foods()
    from contextual_bandit import observations as recorded_observations
    observations=recorded_observations(db,user,profile)
    for meal in view['meals']:
        if meal.get('consumed_estimate'):raise DomainError('Nutrienti a intervallo: bilancio esatto non disponibile','interval_nutrients_unavailable')
        if meal['slot']==slot:continue
        source=meal['eaten'] if meal['eaten'] is not None else meal['planned']
        if source is None:
            if config.get('daily_meals',{}).get('enabled') or meal['slot'] in ('lunch','dinner'):raise DomainError('Completa il piano degli altri pasti prima di cercare alternative')
            continue
        add_lock(config,foods,meal['slot'],source['items'],profile)
    async def run(session):
        result=await orchestrate_day(session,config,foods,dict(k=request.get('k',4),pool_size=request.get('pool_size',6),time_limit=request.get('time_limit',30),_existing_plans=request.get('_existing_plans',[]),diversity=dict(min_distance=1,structural=False)),observations=observations)
        result['date']=date;result['slot']=slot;result['week_start']=week['week_start'] if view['week_plan_id'] else date
        result['horizon']=dict(days=1,date=date,slot=slot)
        reference=dict(selections=[dict(meal=slot,food_id=item['food']['id'],food=item['name'],grams=item['grams'],diversity_eligible=True) for item in current['planned']['items']],nutrients={n:current['planned'][n] for n in current['planned'] if n in ('kcal','protein_g','fat_g','carbs_available_g')})
        for plan in result['plans']:
            plan['selections']=[s for s in plan['selections'] if s['meal']==slot];plan['arms']=arms(plan);plan['bandit_features']=[dict(context=plan['bandit_context'],arms=plan['arms'])];plan['nutrients']=plan['nutrients_by_meal'][slot];plan['diff']=plan_diff(reference,plan);plan['diff']['reference_plan']='current_meal';plan['date']=date
        return result
    return run

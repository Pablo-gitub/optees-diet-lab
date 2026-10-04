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
        foods[identifier]=dict(name=food['name'],source=ref['source'],source_id=ref['id'],**{n:str(food['per_100g'][n.replace('_100g','')]) for n in NUTRIENTS})
        fixed.append(dict(food_id=identifier,grams=grams,units=units,source=ref['source'],reference_id=ref['id']))
    config.setdefault('locked_meals',{})[slot]=fixed


def weekly_model(profile,request,make_config,foods):
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
        date=(start+dt.timedelta(days=offset)).isoformat();config=make_config(profile,(index+offset)%14)
        config['portion_bounds_g']=request.get('portion_bounds_g',config.get('portion_bounds_g',{}))
        for (lock_date,slot),items in locks.items():
            if lock_date==date:add_lock(config,foods,slot,items,profile)
        p,choices,slots=formulate(config,foods);shift=len(variables)
        variables.extend(dict(v,name=f'd{offset}_{v["name"]}') for v in p['variables'])
        sparse_rows.extend(({i+shift:v for i,v in enumerate(r['coefficients']) if v},r['relation'],r['rhs']) for r in p['constraints'])
        objectives.extend(p['objective']['coefficients']);preferences.extend(p.get('preference_coefficients',[0.]*len(p['variables'])))
        for c in choices:
            candidates=[other['group'] for other in choices if other['meal']==c['meal'] and other['combination']==c['combination'] and other['branch_index']==c['branch_index'] and family(other['food_id'])]
            c['principal_protein']=bool(family(c['food_id'])) and c['group']==max(candidates,default=-1)
            if c.get('locked'):
                fixed=[other for other in choices if other['meal']==c['meal'] and other.get('locked')]
                principal=max(fixed,key=lambda other:(other['nutrients'][1]*other.get('locked_grams',p['variables'][other['q']]['lb']),other['food_id']),default=None)
                c['principal_protein']=c is principal and c['nutrients'][1]>0
        all_choices.extend(dict(c,q=c['q']+shift,y=c['y']+shift,date=date,day=offset) for c in choices)
        blocks.append(dict(date=date,config=config,problem=p,choices=choices,slots=slots,shift=shift))
    # Count a principal source once per meal, even if it appears in multiple components.
    families=sorted({c['food_id'] for c in all_choices if c.get('principal_protein')})
    freq={f:[] for f in families}
    for block in blocks:
        for slot in ('lunch','dinner'):
            for f in families:
                ys=[c['y'] for c in all_choices if c['date']==block['date'] and c['meal']==slot and c['food_id']==f and c.get('principal_protein')]
                if not ys:continue
                indicator=len(variables);variables.append(dict(name=f'frequency_{block["date"]}_{slot}_{f}',lb=0,ub=1,integrality='B'));objectives.append(0.);preferences.append(0.);freq[f].append(indicator)
                for y in ys:sparse_rows.append(({y:1,indicator:-1},'<=',0))
                sparse_rows.append(({indicator:1,**{y:-1 for y in ys}},'<=',0))
    for f,indices in freq.items():sparse_rows.append(({i:1 for i in indices},'<=',maximum))
    # Optional reviewed frequency rules are explicit hard bounds, never inferred.
    frequencies=request.get('protein_frequencies',{})
    if not isinstance(frequencies,dict) or any(f not in freq for f in frequencies):raise DomainError('Frequenze non valide')
    for f,spec in frequencies.items():
        if not isinstance(spec,dict):raise DomainError('Frequenza non valida')
        low,high=spec.get('min',0),spec.get('max',maximum)
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (low,high)) or not 0<=low<=high<=maximum:raise DomainError('Frequenza non valida')
        sparse_rows.extend([({i:1 for i in freq[f]},'>=',low),({i:1 for i in freq[f]},'<=',high)])
    size=len(variables);dense=lambda r:[r.get(i,0.) for i in range(size)]
    problem=dict(version='1',variables=variables,constraints=[dict(coefficients=dense(row),relation=relation,rhs=rhs) for row,relation,rhs in sparse_rows],objective=dict(sense='min',coefficients=objectives),solver=dict(time_limit=request.get('solve_time_limit',15)))
    if any(preferences):problem['preference_coefficients']=preferences
    return problem,blocks,all_choices,maximum


def decode_week(problem,blocks,foods,result,maximum):
    clean=copy.deepcopy(problem);clean.pop('preference_coefficients',None);values_verified(clean,result)
    by_name={v['name']:v['value'] for v in result['result']['variables']};days=[]
    for offset,block in enumerate(blocks):
        sub=dict(mathematical_status=result['mathematical_status'],validation=result['validation'],result=dict(variables=[dict(name=v['name'],value=by_name[f'd{offset}_{v["name"]}']) for v in block['problem']['variables']]))
        day=decode_result(block['config'],block['problem'],block['choices'],block['slots'],foods,sub)
        day={k:v for k,v in day.items() if k not in ('config','result','excluded_for_missing_nutrients','crea_sha256')}
        day_targets=block['config']['daily_meals']['targets'] if block['config'].get('daily_meals',{}).get('enabled') else block['config']['main_meals_targets']
        day.update(targets=copy.deepcopy(day_targets),date=block['date'],mode=block['config']['mode'],day_index=block['config']['day_index'],locked_slots=list(block['config'].get('locked_meals',{})))
        if not day['constraint_report']['all_respected']:raise DomainError('Vincoli della giornata non verificati')
        days.append(day)
    frequencies={}
    for day in days:
        for slot in ('lunch','dinner'):
            for f in {s['food_id'] for s in day['selections'] if s['meal']==slot and s.get('principal_protein')}:frequencies[f]=frequencies.get(f,0)+1
    if any(v>maximum for v in frequencies.values()):raise DomainError('Frequenze non rispettate')
    targets=blocks[0]['config']['daily_meals']['targets'] if blocks[0]['config'].get('daily_meals',{}).get('enabled') else blocks[0]['config']['main_meals_targets']
    errors=[abs(day['nutrients'][n.replace('_100g','')]-day['targets'][n]['target'])/day['targets'][n]['target'] for day in days for n in NUTRIENTS]
    return dict(days=days,targets=targets,targets_by_date={d['date']:d['targets'] for d in days},nutrients={n:round(sum(day['nutrients'][n] for day in days),3) for n in days[0]['nutrients']},objectives=dict(nutrition_error=sum(errors),worst_error=max(errors),preference=1.,variety=len({s['food_id'] for day in days for s in day['selections']})/max(sum(len(day['selections']) for day in days),1),prep_minutes=None),constraint_report=dict(verified=True,all_respected=True,protein_frequencies=frequencies,max_protein_repetitions=maximum,frequency_scope='principal_food_id_per_meal'),arms=sorted(set(a for day in days for a in arms(day))),robustness=dict(status='unavailable',reason='Robustezza congiunta settimanale prevista nel passo 4.2.'))


def week_keys(plan):return {(day['date'],s['meal'],s['food_id']) for day in plan['days'] for s in day['selections'] if s['meal'] in ('lunch','dinner') and s['meal'] not in day.get('locked_slots',[])}


async def generate_week(session,profile,request,make_config,foods,history=(),observations=()):
    from plan_diet_day import solve_problem
    foods=copy.deepcopy(foods);problem,blocks,choices,maximum=weekly_model(profile,request,make_config,foods)
    warnings=[]
    from target_validation import target_warnings
    for block in blocks:
        targets=block['config']['daily_meals']['targets'] if block['config'].get('daily_meals',{}).get('enabled') else block['config']['main_meals_targets']
        for w in target_warnings(targets):
            if w not in warnings:warnings.append(w)
    result=dict(spec_version='orchestration-v2',mode=profile['mode'],week_start=request['week_start'],horizon=dict(days=7),status='ok',warnings=warnings,plans=[],pool=dict(candidates=0,front=0,min_distance=3,diversity_relaxed=[]),request_hash=hashlib.sha256(json.dumps(dict(profile=profile,request=request),sort_keys=True).encode()).hexdigest(),seed=request.get('seed',20261004),versions=dict(engine='weekly-milp-v1',catalog=hashlib.sha256(json.dumps(foods,sort_keys=True).encode()).hexdigest()))
    first=await optimize_day(session,problem)
    if first['mathematical_status'] not in ('optimal','feasible'):result['status']='infeasible';return result
    reference=decode_week(problem,blocks,foods,first,maximum);pool=[reference];original=problem['objective']['coefficients'];raw=copy.deepcopy(problem);raw.pop('preference_coefficients',None)
    vals=values_verified(raw,first);z=sum(a*b for a,b in zip(original,vals));epsilon=request.get('epsilon',.05)
    if isinstance(epsilon,bool) or not isinstance(epsilon,(int,float)) or not math.isfinite(epsilon) or not 0<=epsilon<=1:raise DomainError('Epsilon non valido')
    raw['constraints'].append(dict(coefficients=original[:],relation='<=',rhs=z*(1+epsilon)+.01))
    if first.get('preference_penalty') is not None:raw['constraints'].append(dict(coefficients=problem['preference_coefficients'][:],relation='<=',rhs=first['preference_penalty']+1e-7))
    k=request.get('k',4);pool_size=request.get('pool_size',6);minimum=3;structural=True
    if any(isinstance(v,bool) or not isinstance(v,int) for v in (k,pool_size)) or not 1<=k<=5 or not k<=pool_size<=12:raise DomainError('Numero alternative non valido')
    start=time.monotonic();budget=request.get('time_limit',45)
    if not isinstance(budget,(int,float)) or isinstance(budget,bool) or not math.isfinite(budget) or not 1<=budget<=180:raise DomainError('Tempo massimo non valido')
    if first['mathematical_status']!='optimal':result['status']='partial';warnings.append(dict(code='reference_not_optimal',message='Settimana fattibile verificata; ottimo non certificato entro il tempo disponibile.'))
    while len(pool)<pool_size and result['status']!='partial':
        remaining=budget-(time.monotonic()-start)
        if remaining<=0:result['status']='partial';break
        p=copy.deepcopy(raw);p['solver']['time_limit']=min(15,remaining)
        for previous in pool:
            selected=week_keys(previous);row=[0.]*len(p['variables'])
            for c in choices:
                if (c['date'],c['meal'],c['food_id']) in selected:row[c['y']]=1.
            p['constraints'].append(dict(coefficients=row,relation='<=',rhs=len(selected)-minimum))
            if structural:
                # Require a changed protein/starch pair somewhere in the week.
                pairs=[c['y'] for c in choices if (c['date'],c['meal'],c['food_id']) in selected and (family(c['food_id']) or c['food_id'] in ('000800','000100','000530'))]
                if pairs:
                    row=[0.]*len(p['variables'])
                    for index in pairs:row[index]=1
                    p['constraints'].append(dict(coefficients=row,relation='<=',rhs=sum(1 for day in previous['days'] for s in day['selections'] if (day['date'],s['meal'],s['food_id']) in selected and (family(s['food_id']) or s['food_id'] in ('000800','000100','000530')))-1))
        stage=len(pool)%4
        if stage in (1,2):
            worst=extend(p,dict(name='weekly_worst',lb=0,ub=1e6,integrality='C'))
            for offset,block in enumerate(blocks):
                targets=block['config']['daily_meals']['targets'] if block['config'].get('daily_meals',{}).get('enabled') else block['config']['main_meals_targets']
                for n,key in enumerate(NUTRIENTS):
                    dev=next(i for i,v in enumerate(p['variables']) if v['name']==f'd{offset}_dev{n}')
                    spec=targets[key];scale=spec['target'] if stage==1 else max(spec['target']-spec['min'],spec['max']-spec['target'])
                    if scale:
                        row=[0.]*len(p['variables']);row[dev]=1/scale;row[worst]=-1;p['constraints'].append(dict(coefficients=row,relation='<=',rhs=0))
            p['objective']['coefficients']=[0.]*len(p['variables']);p['objective']['coefficients'][worst]=1
        else:
            objective=original[:]
            if stage==3:
                used=set().union(*(week_keys(x) for x in pool))
                objective=[0.]*len(p['variables'])
                for c in choices:objective[c['y']]=1 if (c['date'],c['meal'],c['food_id']) in used or c['food_id'] in history else -1
            else:
                focus=(len(pool)//4)%4
                for i,v in enumerate(p['variables']):
                    if v['name'].endswith(f'_dev{focus}'):objective[i]*=4
            p['objective']['coefficients']=objective
        candidate=await solve_problem(session,p)
        if candidate['mathematical_status'] in ('optimal','feasible'):
            values_verified(p,candidate);plan=decode_week(problem,blocks,foods,candidate,maximum);pool.append(plan)
            if candidate['mathematical_status']!='optimal':result['status']='partial';break
        elif minimum>1 or structural:
            if minimum>1:minimum-=1
            else:structural=False
            result['pool']['diversity_relaxed'].append(dict(min_distance=minimum,structural=structural))
        else:break
    for plan in pool:
        rewards=[reward for arm,reward in observations if arm in plan['arms']]
        if rewards:plan['objectives']['preference']=sum(rewards)/len(rewards)
        if history:
            ids={s['food_id'] for day in plan['days'] for s in day['selections']}
            plan['objectives']['variety']=len(ids-set(history))/max(len(ids),1)
    front=sampled_front(pool);front.sort(key=lambda p:(p['objectives']['nutrition_error'],-p['objectives']['variety']))
    best=front[0];selected=[best]
    if len(front)>1:selected.append(max(front[1:],key=lambda p:p['objectives']['variety']))
    roles=['best']+(['varied'] if len(selected)>1 else [])
    if observations and len(selected)<k:
        options=[p for p in front if p not in selected]
        if options:selected.append(max(options,key=lambda p:p['objectives']['preference']));roles.append('preferred')
    options=[p for p in front if p not in selected]
    if options and len(selected)<k:selected.append(max(options,key=lambda p:exploration_score(p,observations)));roles.append('explore')
    selected=selected[:k];context=context_key(blocks[0]['config'])
    headlines=dict(best='Il più vicino ai tuoi obiettivi',varied='Più varia durante la settimana',preferred='Con gli alimenti che apprezzi di più',explore='Da provare: una settimana diversa')
    for i,plan in enumerate(selected):
        plan.update(role=roles[i],rank=i+1,status='optimal' if result['status']=='ok' else 'feasible',mode=profile['mode'],demo=any(d['demo'] for d in plan['days']),optimization=dict(stage='S2',context=context,near_optimal_gap=(plan['objectives']['nutrition_error']-z)/max(z,.01)),explanation=dict(headline=headlines[roles[i]],reasons=['Vincoli giornalieri e frequenze settimanali verificati'],tradeoffs=[]),diff=None if i==0 else dict(reference_plan='best',distance=len(week_keys(best)-week_keys(plan)),days=[dict(date=d['date'],**plan_diff(b,d)) for b,d in zip(best['days'],plan['days'])]))
    result['plans']=selected;result['pool'].update(candidates=len(pool),front=len(front),min_distance=minimum,structural=structural,epsilon=epsilon,reference_error=z,near_optimal_limit=z*(1+epsilon)+.01)
    if result['pool']['diversity_relaxed']:warnings.append(dict(code='diversity_relaxed',message=f'Diversità settimanale ridotta a {minimum} alimenti.'))
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
    config=make_config(profile,index);config['alternative_slot']=slot;foods=load_foods()
    for meal in view['meals']:
        if meal['slot']==slot:continue
        source=meal['eaten'] if meal['eaten'] is not None else meal['planned']
        if source is None:
            if config.get('daily_meals',{}).get('enabled') or meal['slot'] in ('lunch','dinner'):raise DomainError('Completa il piano degli altri pasti prima di cercare alternative')
            continue
        add_lock(config,foods,meal['slot'],source['items'],profile)
    async def run(session):
        result=await orchestrate_day(session,config,foods,dict(k=4,pool_size=6,time_limit=30,diversity=dict(min_distance=1,structural=False)))
        result['date']=date;result['slot']=slot;result['week_start']=week['week_start'] if view['week_plan_id'] else date
        result['horizon']=dict(days=1,date=date,slot=slot)
        reference=dict(selections=[dict(meal=slot,food_id=item['food']['id'],food=item['name'],grams=item['grams'],diversity_eligible=True) for item in current['planned']['items']],nutrients={n:current['planned'][n] for n in current['planned'] if n in ('kcal','protein_g','fat_g','carbs_available_g')})
        for plan in result['plans']:
            plan['selections']=[s for s in plan['selections'] if s['meal']==slot];plan['nutrients']=plan['nutrients_by_meal'][slot];plan['diff']=plan_diff(reference,plan);plan['diff']['reference_plan']='current_meal';plan['date']=date
        return result
    return run

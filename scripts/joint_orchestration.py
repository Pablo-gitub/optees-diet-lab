"""Verified diet/workout combinations over bounded, explicitly sampled week pools."""
import copy
import datetime as dt
import hashlib
import json
from diary_service import DomainError,valid_date,integer,day_view
from daily_meals import validate as validate_daily
from day_orchestration import plan_diff,exploration_score
from joint_energy import day_scenarios
from joint_robustness import annotate_pool
import week_orchestration as diet_engine
import workout_service as workout_engine


def dates(start):return [(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat() for i in range(7)]


def validate_request(profile,data):
    if not isinstance(data,dict):raise DomainError('Corpo della richiesta non valido')
    start=valid_date(data.get('week_start'));integer(data.get('k',4),1,5)
    if not profile.get('daily_meals',{}).get('enabled'):raise DomainError('Attiva colazione e spuntini nel bilancio completo prima della settimana congiunta')
    targets=data.get('day_targets',profile.get('day_type_targets'))
    if not isinstance(targets,dict) or set(targets)!= {'rest','training'}:raise DomainError('Indica i target completi per riposo e allenamento')
    for target in targets.values():
        try:validate_daily(dict(profile['daily_meals'],targets=target))
        except ValueError as exc:raise DomainError(str(exc))
    modes=data.get('day_modes',dict(rest='sedentary',training='training') if profile['mode']!='free' and profile.get('personal_diets') else dict(rest=profile['mode'],training=profile['mode']))
    if not isinstance(modes,dict) or set(modes)!= {'rest','training'} or any(v not in (('free','sedentary','training') if profile.get('personal_diets') else ('free',)) for v in modes.values()):raise DomainError('Programmi per tipo di giornata non validi')
    workout=data.get('workout')
    if not isinstance(workout,dict) or 'week_start' in workout and workout['week_start']!=start:raise DomainError('Orizzonte palestra non valido')
    cfg,_=workout_engine.week_config(dict(workout,week_start=start))
    from activity_service import candidates
    candidates(profile,workout)
    budget=data.get('energy_balance_target_kcal',profile.get('energy_balance_target_kcal'))
    workout_engine.finite(budget,'Bilancio calorico',-10000,10000,True)
    mapping=data.get('workout_activity_map',{})
    if not isinstance(mapping,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not v.startswith('HKWorkoutActivityType') for k,v in mapping.items()):raise DomainError('Corrispondenze attività Salute non valide')
    diet=data.get('diet',{})
    if not isinstance(diet,dict) or set(diet)-{'k','pool_size','epsilon','time_limit','solve_time_limit','max_protein_repetitions','protein_frequencies','portion_bounds_g'}:raise DomainError('Parametri dieta non validi')
    integer(diet.get('pool_size',4),1,12);integer(diet.get('k',min(4,diet.get('pool_size',4))),1,5)
    return modes,budget


def state_hash(db,user,profile,start):
    # Snapshot only scheduling/diary facts, without private health identifiers.
    views=[day_view(db,user,profile,d) for d in dates(start)]
    return hashlib.sha256(json.dumps(views,sort_keys=True).encode()).hexdigest()


def locked_workouts(db,user,start):
    from workout_sessions import validate_session
    locked={}
    for date in dates(start):
        rows=db.execute("SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? AND w.status='active' AND s.date=?",(user,date)).fetchall()
        logs=db.execute('SELECT * FROM workout_log WHERE user_id=? AND date=?',(user,date)).fetchall()
        if not logs and not any(r['status'] in ('done','in_progress','skipped') for r in rows):continue
        linked={r['planned_session_id']:r for r in logs if r['planned_session_id'] is not None};members=[]
        for row in rows:
            if row['status']=='skipped':continue
            log=linked.get(row['id']);snapshot=json.loads(log['snapshot'] if log else row['snapshot'])
            members.append(dict(session_id=row['session_id'],session=snapshot,start_time=row['start_time']))
        ids={r['id'] for r in rows}
        for log in logs:
            if log['planned_session_id'] not in ids:members.append(dict(session_id=log['session_id'],session=json.loads(log['snapshot']),start_time=None))
        if not members:locked[date]=[];continue
        timeline=[];clock=0;coverage={};totals={}
        for member in members:
            s=member['session'];validate_session(s)
            for event in s['timeline']:
                e=dict(event,start_seconds=event['start_seconds']+clock,end_seconds=event['end_seconds']+clock);timeline.append(e);totals[e['kind']]=totals.get(e['kind'],0)+e['duration_seconds']
            clock+=s['duration_seconds']
            for key,value in s['score_vector']['muscle_coverage_proxy'].items():coverage[key]=coverage.get(key,0)+value
        pack=copy.deepcopy(members[0]['session'])
        pack.update(id='observed_'+date,format='observed_bundle',locked_observation=True,locked_members=members,session_count=len(members),strength_count=sum(bool(m['session']['resistance_session']) for m in members),duration_seconds=clock,duration_minutes_assumed=clock/60,timeline=timeline,time_breakdown_seconds=totals,pending_configuration=[],equipment_feasible=True,high_intensity_ready=True,cardio_work_seconds=sum(m['session']['cardio_work_seconds'] for m in members))
        pack['score_vector'].update(muscle_coverage_proxy=coverage,time_cost_minutes=clock/60);locked[date]=[pack]
    return locked


def context_key(profile,data):
    modes,_=validate_request(profile,data)
    return hashlib.sha256(json.dumps(dict(version='joint-v1',targets=data.get('day_targets',profile.get('day_type_targets')),modes=modes,goal=data['workout'].get('goal'),settings=profile.get('_workout_settings',{})),sort_keys=True).encode()).hexdigest()


def front(plans):
    orientations=dict(nutrition_error=1,worst_error=1,preference=-1,variety=-1,training_fit=-1,training_minutes=1)
    orientations={key:sign for key,sign in orientations.items() if all(p['objectives'].get(key) is not None for p in plans)}
    vector=lambda p:[p['objectives'][key]*sign for key,sign in orientations.items()]
    return [p for p in plans if not any(all(a<=b+1e-8 for a,b in zip(vector(q),vector(p))) and any(a<b-1e-8 for a,b in zip(vector(q),vector(p))) for q in plans if q is not p)]


def session_diff(before,after):
    keys=lambda p:{(s['date'],s['session_id']) for s in p['workout_sessions']}
    removed=sorted(keys(before)-keys(after));added=sorted(keys(after)-keys(before));moved=[]
    for old in removed[:]:
        new=next((item for item in added if item[1]==old[1]),None)
        if new:moved.append(dict(session_id=old[1],from_date=old[0],to_date=new[0]));removed.remove(old);added.remove(new)
    return dict(sessions_added=[dict(date=d,session_id=s) for d,s in added],sessions_removed=[dict(date=d,session_id=s) for d,s in removed],sessions_moved=moved)


def select(result,pool,data,observations=()):
    candidates=front(pool);best=min(candidates,key=lambda p:(p['objectives']['nutrition_error'],-p['objectives']['preference'],-(p['objectives']['training_fit'] or 0)));selected=[best];best['role']='best'
    def take(role,key,eligible=lambda p:True):
        choices=[p for p in candidates if p not in selected and eligible(p)]
        if choices and len(selected)<data.get('k',4):p=min(choices,key=key);p['role']=role;selected.append(p)
    # Reserve a distinct robust role before filling the varied/exploration slots.
    take('robust',lambda p:(p['robustness']['max_regret_kcal'],p['robustness']['max_loss_kcal']),lambda p:p['robustness']['status']=='available')
    take('varied',lambda p:(-p['objectives']['variety'],-(p['objectives']['training_fit'] or 0)))
    from contextual_bandit import rewards as contextual_rewards
    if any(contextual_rewards(p,observations) for p in candidates):take('preferred',lambda p:-p['objectives']['preference'])
    def workout_signature(p):
        return tuple(sorted((s['date'],s['session_id'],json.dumps(s.get('session',{}),sort_keys=True)) for s in p['workout_sessions']))
    varied=next((p for p in selected if p['role']=='varied'),None)
    # Preserve Pareto feasibility; prefer exploration of a different workout too.
    take('explore',lambda p:(workout_signature(p)==workout_signature(varied) if varied else False,tuple(-v for v in exploration_score(p,observations))))
    headlines=dict(best='Dieta e allenamento vicini ai tuoi obiettivi',varied='Una settimana con alimenti e sessioni diversi',robust='Più stabile negli scenari di consumo',preferred='Più vicina alle combinazioni che apprezzi',explore='Una combinazione nuova da provare')
    for rank,p in enumerate(selected,1):
        p.update(rank=rank,explanation=dict(headline=headlines[p['role']],reasons=['Vincoli di dieta e palestra verificati',f"Copertura degli obiettivi di allenamento: {p['objectives']['training_fit']:.2f}" if p['objectives']['training_fit'] is not None else 'Obiettivi di copertura muscolare non configurati'],tradeoffs=[]))
        if p['role']=='explore' and varied and workout_signature(p)==workout_signature(varied):
            p['explanation']['reasons'].append('Esplorazione alimentare: la scheda palestra coincide con il piano varied; nessuna scheda diversa resta selezionabile sul fronte.')
        p['diff']=None if p is best else dict(reference_plan='best',distance=len(diet_engine.week_keys(best)-diet_engine.week_keys(p)),days=[dict(date=a['date'],**plan_diff(a,b)) for a,b in zip(best['days'],p['days'])],**session_diff(best,p))
    if not any(p['role']=='robust' for p in selected):result['warnings'].append(dict(code='robust_role_omitted',message='Nessun ulteriore candidato distinto con scenari completi sul fronte, oppure numero di piani richiesto insufficiente.'))
    result['plans']=selected;result['pool'].update(candidates=len(pool),front=len(candidates))
    if len(selected)==1:result['warnings'].append(dict(code='limited_alternatives',message='Una sola combinazione distinta sul fronte campionato.'))
    return result


async def generate_week(session,profile,data,make_config,foods,health=None,workout_locks=None,observations=(),history=()):
    data=copy.deepcopy(data);explicit_targets='day_targets' in data
    data.setdefault('day_targets',copy.deepcopy(profile.get('day_type_targets')))
    modes,balance=validate_request(profile,data);start=data['week_start'];index=data.get('day_index',dt.date.fromisoformat(start).weekday());integer(index,0,13)
    workout_request=dict(data['workout'],week_start=start)
    workout_set=await workout_engine.generate_week(session,profile,workout_request,workout_locks,health)
    result=dict(kind='joint',energy_balance_target_kcal=balance,spec_version='orchestration-v2-joint',mode=profile['mode'],week_start=start,horizon=dict(days=7),status=workout_set['status'],plans=[],pool=dict(candidates=0,front=0),warnings=copy.deepcopy(workout_set['warnings']),configuration_hash=workout_engine.configuration_hash(profile),versions=dict(engine='joint-v1',health=(health or {}).get('version')),request_hash=hashlib.sha256(json.dumps(dict(profile=profile,request=data),sort_keys=True).encode()).hexdigest())
    if not workout_set['plans']:return result
    from activity_targets import context_key as approved_context_key
    approved=profile.get('approved_activity_targets',{})
    if approved and approved.get('context_key')!=approved_context_key(profile):
        result['warnings'].append(dict(code='activity_targets_profile_changed',message='Profilo modificato dopo l’approvazione: target specifici per data e base stimata non riutilizzati.'))
        approved={}
    from activity_targets import approved_baseline
    fallback=approved_baseline(profile)
    if (health or {}).get('non_workout_consumption_scenarios',{}).get('status')!='available' and fallback is not None:
        health=dict(health or {},non_workout_consumption_scenarios=fallback)
        result['warnings'].append(dict(code='estimated_non_workout_baseline',message='Base energetica stimata e approvata; non misurata da Salute.'))
    from activity_targets import session_energy,signature as activity_signature
    for workout in workout_set['plans']:
        for item in workout['workout_sessions']:
            if item['session'].get('kind')!='activity' and approved:
                estimate=session_energy(item,profile.get('_filtered_weight_kg'),health)
                if estimate['status']=='available':item['session']['approved_energy_estimate']=estimate
    pool=[];seen=set();context=context_key(profile,data)
    for workout in workout_set['plans']:
        by_date={d:[s for s in workout['workout_sessions'] if s['date']==d] for d in dates(start)}
        day_types={d:'training' if by_date[d] else 'rest' for d in dates(start)}
        offsets={(index+i)%14:d for i,d in enumerate(dates(start))}
        def config_for_day(original,day):
            date=offsets[day];kind=day_types[date];personal=copy.deepcopy(original);personal['mode']=modes[kind];personal['daily_meals']['targets']=copy.deepcopy(data['day_targets'][kind]);dated=approved.get('days',{}).get(date)
            if not explicit_targets and dated and dated['session_signature']==activity_signature(by_date[date]):personal['daily_meals']['targets']=copy.deepcopy(dated['targets'])
            config=make_config(personal,day);config['day_type']=kind
            config['_timing_profile']=personal
            config['_timing_sessions']=copy.deepcopy(by_date[date])
            from joint_energy import day_scenarios
            forecast=day_scenarios(health,by_date[date])
            if forecast['status']=='available':config['_energy_low']=forecast['consumption_kcal']['low']
            return config
        diet_request=dict(data.get('diet',{}),week_start=start,day_index=index,locked=data.get('locked',[]),locked_dishes=data.get('locked_dishes',[]))
        diet_request.setdefault('pool_size',4);diet_request.setdefault('k',min(4,diet_request['pool_size']))
        diet_set=await diet_engine.generate_week(session,profile,diet_request,config_for_day,foods,history,observations)
        for warning in diet_set['warnings']:
            if warning not in result['warnings']:result['warnings'].append(warning)
        if diet_set['status']=='partial':result['status']='partial'
        if not diet_set['plans']:result['warnings'].append(dict(code='infeasible_combination',message='Una scheda palestra non ammette una settimana dieta con i target e vincoli indicati.'));continue
        cfg,_=workout_engine.week_config(workout_request);coverage={}
        if profile.get('goals',{}).get('activity',{}).get('gym')=='no':cfg['muscle_targets_proxy']={}
        for s in workout['workout_sessions']:
            for key,value in s['session']['score_vector']['muscle_coverage_proxy'].items():coverage[key]=coverage.get(key,0)+value
        fractions=[min(1,coverage.get(k,0)/target) for k,target in cfg['muscle_targets_proxy'].items()]
        cardio=sum(s['session']['cardio_work_seconds'] for s in workout['workout_sessions'])/60
        if cfg['cardio_minutes_min']>0:fractions.append(min(1,cardio/cfg['cardio_minutes_min']))
        priorities=profile.get('goals',{}).get('training_priorities',{})
        if priorities.get('health',0):
            equivalent=sum(s['session'].get('health_equivalent_factor',1 if s['session']['cardio_work_seconds'] else 0)*(s['session']['duration_seconds'] if s['session'].get('kind')=='activity' else s['session']['cardio_work_seconds'])/60 for s in workout['workout_sessions'])
            fractions.extend([min(1,equivalent/150),min(1,len({s['date'] for s in workout['workout_sessions'] if s['session']['resistance_session']})/2)])
        fit=sum(fractions)/len(fractions) if fractions else None
        for plan in diet_set['plans']:
            signature=json.dumps(dict(days=[[d['date'],[(s['meal'],s['food_id'],s['grams']) for s in d['selections']]] for d in plan['days']],sessions=[(s['date'],s['session_id']) for s in workout['workout_sessions']]),sort_keys=True)
            if signature in seen:continue
            seen.add(signature);p=copy.deepcopy(plan);p.pop('diff',None);p['workout_sessions']=copy.deepcopy(workout['workout_sessions']);p['configuration_hash']=result['configuration_hash'];p['status']='feasible';p['demo']=p['demo'] or any(s['session']['demo'] for s in p['workout_sessions'])
            p['optimization']['scope']='sampled_combinations_not_global_joint_optimum'
            p['constraint_report']['workout']=workout['constraint_report'];p['training_metrics']=dict(coverage_fraction_by_muscle={k:min(1,coverage.get(k,0)/v) for k,v in cfg['muscle_targets_proxy'].items()},cardio_work_minutes=cardio,duration_seconds=workout['weekly_duration_seconds'],basis='heuristic_muscle_set_proxy_not_effectiveness')
            p['objectives'].update(training_fit=fit,training_minutes=workout['weekly_duration_seconds']/60)
            p['optimization']['context']=context;p['arms']=sorted(set(p['arms'])|{'protocol:'+s['session']['protocol_id'] for s in p['workout_sessions']})
            from contextual_bandit import rewards as contextual_rewards
            for feature,day in zip(p['bandit_features'],p['days']):feature['arms']=sorted(set(feature['arms'])|{'protocol:'+s['session']['protocol_id'] for s in by_date[day['date']]})
            rewards=contextual_rewards(p,observations)
            if rewards:p['objectives']['preference']=sum(rewards)/len(rewards)
            for day in p['days']:
                day.update(day_type=day_types[day['date']],workout_sessions=copy.deepcopy(by_date[day['date']]),energy_scenarios=day_scenarios(health,by_date[day['date']],data.get('workout_activity_map')))
            p['robustness']=dict(status='unavailable',reason='Robustezza sul pool congiunto nel passo 4.2.');pool.append(p)
    if not pool:result['status']='infeasible';return result
    result['robust_selection']=await annotate_pool(session,pool,balance)
    if result['robust_selection']['status']=='unavailable':result['warnings'].append(dict(code='robustness_unavailable',message=result['robust_selection']['reason']))
    return select(result,pool,data,observations)


def apply_week(db,user,profile,plan_set,plan,data):
    from diary_service import apply_plan
    if data.get('scope')!='week':raise DomainError('Il piano congiunto richiede scope week')
    if plan_set['configuration_hash']!=workout_engine.configuration_hash(profile):raise DomainError('Configurazione palestra cambiata; rigenera','configuration_changed',409)
    if plan_set.get('state_hash')!=state_hash(db,user,profile,plan_set['week_start']):raise DomainError('Piano o registri cambiati; rigenera la settimana congiunta','planning_state_changed',409)
    diet=apply_plan(db,user,profile,plan_set,plan,data);workout=workout_engine.apply_week(db,user,profile,plan_set,plan,data)
    from progress_analysis import invalidate_forecast
    for item in workout['skipped_slots']:invalidate_forecast(db,user,item['date'],'workout_slot_protected')
    view=day_view(db,user,profile,plan_set['week_start']);view.update(applied_slots=diet['applied_slots']+workout['applied_slots'],skipped_slots=diet['skipped_slots']+workout['skipped_slots']);return view

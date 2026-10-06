"""Provisional, soft meal timing; redistribution never changes daily energy."""
import copy
import json
import math
from pathlib import Path
from diary_service import DomainError
from plan_recipe import values_verified
ROOT=Path(__file__).resolve().parents[1]


def parameters():return json.loads((ROOT/'config/nutrient-timing.json').read_text())


def clock(value):
    if not isinstance(value,str) or len(value)!=5 or value[2]!=':':raise DomainError('Orario: usa HH:MM')
    try:h,m=map(int,value.split(':'))
    except ValueError:raise DomainError('Orario: usa HH:MM')
    if not 0<=h<=23 or not 0<=m<=59:raise DomainError('Orario fuori intervallo')
    return h*60+m


def validate(value):
    if not isinstance(value,dict) or set(value)-{'mode','meals','explicit_session'} or value.get('mode') not in ('auto','explicit','off'):raise DomainError('Distribuzione pasti: scegli auto, explicit oppure off')
    result=copy.deepcopy(value);meals=result.setdefault('meals',{})
    if not isinstance(meals,dict) or set(meals)-set(parameters()['default_meals']):raise DomainError('Orari dei pasti non validi')
    for times in meals.values():
        if not isinstance(times,dict) or set(times)!= {'start_time','end_time'}:raise DomainError('Servono inizio e fine del pasto')
        a,b=clock(times['start_time']),clock(times['end_time'])
        if b<a or b-a>180:raise DomainError('Il pasto deve finire dopo l’inizio, entro tre ore')
    explicit=result.get('explicit_session')
    if explicit is not None:
        if not isinstance(explicit,dict) or set(explicit)!= {'start_time','duration_minutes'}:raise DomainError('Sessione esplicita: servono inizio e durata')
        clock(explicit['start_time']);minutes=explicit['duration_minutes']
        if isinstance(minutes,bool) or not isinstance(minutes,(int,float)) or not math.isfinite(minutes) or not 1<=minutes<=300:raise DomainError('Durata esplicita: 1–300 minuti')
    return result


def context(profile,sessions,slots):
    p=parameters();setting=validate(profile.get('meal_timing',dict(mode='auto')));mode=setting['mode']
    base=dict(status='inactive',parameters_version=p['version'],parameters_status=p['status'],rules=[],sessions=[],daily_kcal_unchanged=True,explanation='Distribuzione per comfort e qualità dell’allenamento; obiettivi quotidiani invariati.')
    if mode=='off':return base
    eligible=[]
    for item in sessions:
        seconds=item.get('session',{}).get('duration_seconds');start=item.get('start_time')
        if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<=0 or not start:continue
        if mode=='auto' and seconds<=p['minimum_session_minutes']*60:continue
        try:begin=clock(start)
        except DomainError:continue
        eligible.append(dict(session_id=item['session_id'],start_minutes=begin,end_minutes=begin+seconds/60,duration_minutes=seconds/60,cardio=bool(item['session'].get('cardio_work_seconds'))))
    if not eligible and mode=='explicit' and setting.get('explicit_session'):
        item=setting['explicit_session'];begin=clock(item['start_time'])
        eligible.append(dict(session_id='profile_explicit',start_minutes=begin,end_minutes=begin+item['duration_minutes'],duration_minutes=item['duration_minutes'],cardio=False,explicit=True))
    if not eligible:
        if mode=='explicit':base.update(status='unavailable',reason='Indica l’orario della sessione per scegliere i pasti prima e dopo.')
        return base
    weight=profile.get('_filtered_weight_kg')
    if isinstance(weight,bool) or not isinstance(weight,(int,float)) or not math.isfinite(weight) or not 30<=weight<=300:return dict(base,status='unavailable',reason='Serve un peso filtrato recente tra 30 e 300 kg.')
    meals=dict(p['default_meals'],**setting['meals']);available={s:t for s,t in meals.items() if s in slots and slots[s]!='not_planned'}
    for session in eligible:
        before=[s for s,t in available.items() if p['pre_min_hours']*60<=session['start_minutes']-clock(t['end_time'])<=p['pre_max_hours']*60]
        after=[s for s,t in available.items() if 0<=clock(t['start_time'])-session['end_minutes']<=p['post_max_hours']*60]
        session.update(before=max(before,key=lambda s:clock(meals[s]['end_time'])) if before else None,after=min(after,key=lambda s:clock(meals[s]['start_time'])) if after else None)
        if session['duration_minutes']>p['during_after_minutes']:session['during_suggestion']=dict(status='provvisorio',carbs_g_per_hour=p['during_carbs_g_per_hour'],planned=False,reason='Suggerimento informativo durante attività lunga; non incluso nei pasti o nelle kcal.')
        if session['end_minutes']>=1440:session['after_reason']='La sessione termina il giorno seguente: nessun pasto successivo di questo giorno viene inventato.'
    return dict(base,status='active',weight_kg=weight,schedule_source='profile' if setting['meals'] else 'provisional_default',meal_times=meals,sessions=eligible,parameters=p)


def fiber(food):
    try:value=float(food.get('fiber_g_100g'))
    except (ValueError,TypeError):return None
    return value if math.isfinite(value) and value>=0 else None


def add_rules(config,foods,choices,slots,var,add):
    ctx=context(config.get('_timing_profile',{}),config.get('_timing_sessions',[]),slots)
    config['_timing_context']=ctx
    if ctx['status']!='active':return {},[]
    p=ctx['parameters'];weight=ctx['weight_kg'];count=len({c['meal'] for c in choices});penalties={};seen=set()
    def rule(identifier,meal,n,relation,target,mean_factor=None,multiplier=1):
        key=(identifier,meal)
        if key in seen:return
        seen.add(key)
        row={};unknown=set()
        for c in choices:
            value=fiber(foods[c['food_id']]) if n=='fiber' else c['nutrients'][n]*100
            if value is None:unknown.add(c['y']);continue
            coefficient=value/100*((1 if c['meal']==meal else 0)-(mean_factor/count if mean_factor is not None else 0))
            if coefficient:row[c['q']]=row.get(c['q'],0)+coefficient
        # With a missing selected fiber vector the average cannot be known.
        if unknown:
            for y in unknown:row[y]=row.get(y,0)-1e6 if relation=='<=' else row.get(y,0)+1e6
        slack=var('timing_'+identifier+'_'+meal,0,1e8)
        row[slack]=-1 if relation=='<=' else 1;add(row,relation,0 if mean_factor is not None else target)
        scale=max(1,target if mean_factor is None else config.get('daily_meals',{}).get('targets',config['main_meals_targets']).get('fat_g_100g' if n==2 else 'carbs_available_g_100g',{}).get('target',1)/count)
        penalties[slack]=p['soft_weight']*multiplier/scale
        ctx['rules'].append(dict(id=identifier,slot=meal,nutrient=n,relation=relation,target_g=target if mean_factor is None else None,mean_factor=mean_factor,slack_index=slack,unknown_fiber=bool(unknown)))
    for session in ctx['sessions']:
        before=session['before'];after=session['after']
        if before:
            rule('pre_carbs',before,3,'>=',p['pre_carbs_g_per_kg']*weight)
            rule('pre_fat',before,2,'<=',0,p['pre_fat_mean_factor'])
            rule('pre_fiber',before,'fiber','<=',0,p['pre_fiber_mean_factor'])
        if after:
            rule('post_protein_min',after,1,'>=',p['post_protein_min_g_per_kg']*weight)
            rule('post_protein_max',after,1,'<=',p['post_protein_max_g_per_kg']*weight)
            rule('post_carbs',after,3,'>=',0,p['post_carbs_mean_factor'],p['cardio_carbs_priority_multiplier'] if session['cardio'] else 1)
    for meal in ('lunch','dinner'):
        if meal in slots:rule('main_protein',meal,1,'>=',p['main_protein_min_g_per_kg']*weight)
    kcal={c['q']:c['nutrients'][0] for c in choices}
    return penalties,[kcal]


async def refine(session,problem,result,solver):
    coeff=problem.get('timing_coefficients')
    if not coeff or not any(coeff) or result['mathematical_status'] not in ('optimal','feasible'):return result
    values=values_verified(problem,result);p=copy.deepcopy(problem);size=len(p['variables'])
    pad=lambda row:row+[0]*(size-len(row))
    old_objective=p['objective']['coefficients'][:]
    old_value=sum(a*b for a,b in zip(old_objective,values))
    p['constraints'].append(dict(coefficients=old_objective,relation='<=' if p['objective']['sense']=='min' else '>=',rhs=old_value+(1e-7 if p['objective']['sense']=='min' else -1e-7)))
    energy=[]
    for raw in p['timing_kcal_rows']:
        row=pad(raw);value=sum(a*b for a,b in zip(row,values));energy.append(value)
        p['constraints'].append(dict(coefficients=row,relation='=',rhs=value))
    p['objective']=dict(sense='min',coefficients=pad(coeff))
    try:
        improved=await solver(session,p)
        if improved['mathematical_status'] not in ('optimal','feasible'):raise ValueError('Nessuna redistribuzione verificata')
        values_verified(p,improved)
    except (ValueError,RuntimeError,TimeoutError,KeyError,TypeError) as exc:
        fallback=copy.deepcopy(result);fallback['timing_optimization']=dict(status='unavailable',reason='Redistribuzione non verificata: mantenuto il piano iniziale.',daily_kcal=energy);return fallback
    for field in ('preference_penalty','optimization'):
        if field in result:improved[field]=copy.deepcopy(result[field])
    improved['timing_optimization']=dict(status=improved['mathematical_status'],daily_kcal=energy,daily_kcal_unchanged=True)
    if result['mathematical_status']=='feasible':improved['mathematical_status']='feasible'  # Timing optimum does not certify the original nutritional optimum.
    return improved


def report(config,selections,foods,result):
    ctx=copy.deepcopy(config.get('_timing_context',{}))
    if not ctx:return None
    if ctx['status']!='active':return ctx
    if not selections:return dict(ctx,status='unavailable',rules=[],reason='Nessun piano fattibile da valutare.')
    by={};unknown=False
    for s in selections:
        row=foods[s['food_id']];f=fiber(row)
        if f is None:unknown=True
        vector=[float(row[n])*s['grams']/100 for n in ('kcal_100g','protein_g_100g','fat_g_100g','carbs_available_g_100g')]
        vector.append(None if f is None else f*s['grams']/100)
        target=by.setdefault(s['meal'],[0.,0.,0.,0.,0.])
        for i,value in enumerate(vector):target[i]=None if value is None or target[i] is None else target[i]+value
    count=len(by)
    for rule in ctx['rules']:
        n=4 if rule['nutrient']=='fiber' else rule['nutrient'];observed=by.get(rule['slot'],[None]*5)[n]
        if n==4 and unknown:observed=None
        if rule['mean_factor'] is not None:
            totals=[v[n] for v in by.values()]
            target=None if any(v is None for v in totals) else sum(totals)*rule['mean_factor']/count
        else:target=rule['target_g']
        satisfied=None if observed is None or target is None else observed>=target-.001 if rule['relation']=='>=' else observed<=target+.001
        rule.update(observed_g=None if observed is None else round(observed,3),target_g=None if target is None else round(target,3),satisfied=satisfied,reason='Fibre mancanti in un alimento selezionato: media non valutabile.' if satisfied is None else None if satisfied else 'Quota provvisoria non raggiunta entro i vincoli del piano; il pasto può essere bloccato o la redistribuzione limitata.')
        rule.pop('slack_index',None)
    ctx['optimization']=result.get('timing_optimization',dict(status='not_refined'))
    ctx['reasons']=[s.get('after_reason') or 'Nessun pasto nella finestra '+kind+'.' for s in ctx['sessions'] for kind in ('prima','dopo') if s['before' if kind=='prima' else 'after'] is None]
    return ctx

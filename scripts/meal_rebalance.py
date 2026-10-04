"""Owner-scoped, read-only MILP previews and atomic explicit decisions."""
import copy
import datetime as dt
import hashlib
import json
import math
import time
from pathlib import Path
import diary_service as diary
import progress_recalibration as recalibration
from plan_diet_day import NUTRIENTS
from plan_recipe import values_verified
from week_orchestration import weekly_model,decode_week

ROOT=Path(__file__).resolve().parents[1]
LIMITS=dict(maximum_daily_reduction_kcal=200,maximum_energy_deficit_kcal=500,minimum_kcal=1400,minimum_protein_g=45,maximum_reduction_spread_kcal=25)
FLOORS=recalibration.FLOORS


def catalog():
    data=json.loads((ROOT/'config/meal-presets.json').read_text())
    for preset in data['presets'].values():
        for size in preset['sizes'].values():
            size['available']=all(valid_interval(size.get(key)) for key in ('calories_kcal','protein_g','fat_g','carbs_g'))
    return data


def valid_interval(value):
    return isinstance(value,dict) and set(value)=={'min','max'} and all(isinstance(value[k],(int,float)) and not isinstance(value[k],bool) and math.isfinite(value[k]) and value[k]>=0 for k in value) and value['min']<=value['max']


def estimate(data,today):
    if not isinstance(data,dict) or set(data)-{'date','slot','preset','custom'}:raise diary.DomainError('Richiesta non valida')
    date=diary.valid_date(data.get('date'));slot=diary.valid_slot(data.get('slot'));day=dt.date.fromisoformat(date)
    if not today-dt.timedelta(days=today.weekday())<=day<=today:raise diary.DomainError('Scegli un pasto già consumato nella settimana corrente')
    if ('preset' in data)==('custom' in data):raise diary.DomainError('Scegli preset oppure valori liberi')
    if 'preset' in data:
        ref=data['preset'];cat=catalog()
        if not isinstance(ref,dict) or set(ref)!={'id','size'} or not isinstance(ref['id'],str) or not isinstance(ref['size'],str):raise diary.DomainError('Preset non valido')
        size=cat['presets'].get(ref['id'],{}).get('sizes',{}).get(ref['size'])
        if not size or not size['available']:raise diary.DomainError('Questa taglia non ha dati nutrizionali verificabili','unavailable_preset')
        nutrients={key:copy.deepcopy(size[source]) for key,source in zip(diary.KEYS,('calories_kcal','protein_g','fat_g','carbs_g'))}
        provenance=dict(source='preset',preset_id=ref['id'],size=ref['size'],catalog_version=cat['version'],sources=size.get('sources',[]),calculation=size.get('calculation'))
    else:
        custom=data['custom']
        if not isinstance(custom,dict) or set(custom)!=set(diary.KEYS):raise diary.DomainError('Servono tutti e quattro i nutrienti')
        nutrients={key:(dict(min=value,max=value) if isinstance(value,(int,float)) and not isinstance(value,bool) else value) for key,value in custom.items()}
        provenance=dict(source='user_estimate',description='Intervallo dichiarato dall’utente')
    for key,value in nutrients.items():
        if not valid_interval(value) or value['max']>(10000 if key=='kcal' else 1000):raise diary.DomainError('Intervallo nutrizionale non valido')
    return dict(date=date,slot=slot,nutrients=nutrients,provenance=provenance)


def migrate(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS consumed_estimate(user_id INTEGER,date TEXT,slot TEXT,payload TEXT,created REAL,PRIMARY KEY(user_id,date,slot));
    CREATE TABLE IF NOT EXISTS rebalance_decision(id INTEGER PRIMARY KEY,user_id INTEGER,preview_id TEXT UNIQUE,decision TEXT,created REAL,payload TEXT);
    INSERT OR IGNORE INTO schema_migration VALUES(5,strftime('%s','now'));''')


def fingerprint(db,user,profile):
    base=recalibration.fingerprint(db,user,profile,None,[])
    estimates=[dict(r) for r in db.execute('SELECT * FROM consumed_estimate WHERE user_id=? ORDER BY date,slot',(user,))]
    return hashlib.sha256(json.dumps([base,estimates],sort_keys=True).encode()).hexdigest()


def snapshot(db,user,profile,meal):
    view=diary.day_view(db,user,profile,meal['date'])
    slot=next(m for m in view['meals'] if m['slot']==meal['slot'])
    if slot['state']!='unknown' or db.execute('SELECT 1 FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,meal['date'],meal['slot'])).fetchone():raise diary.DomainError('Pasto già registrato','slot_already_logged',409)
    start=(dt.date.fromisoformat(meal['date'])-dt.timedelta(days=dt.date.fromisoformat(meal['date']).weekday())).isoformat()
    views=[diary.day_view(db,user,profile,(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat()) for i in range(7)]
    week=db.execute("SELECT * FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,start)).fetchone()
    return dict(start=start,views=views,context=json.loads(week['day_context'] or '{}') if week else {},week_id=week['id'] if week else None,original_kcal=slot['planned']['kcal'] if slot['planned'] else 0,state=fingerprint(db,user,profile))


async def preview(session,profile,meal,snap,make_config,foods):
    original=snap['original_kcal'];known=isinstance(original,(int,float))
    excess={k:round(meal['nutrients']['kcal'][k]-original,3) if known else None for k in ('min','max')}
    totals=[v['totals']['planned']['kcal'] if v['totals']['planned'] else None for v in snap['views']]
    reference={k:0. for k in ('min','max')}
    reference_known=True
    for view in snap['views']:
        for slot in view['meals']:
            if slot.get('consumed_estimate'):
                for k in reference:reference[k]+=slot['consumed_estimate']['nutrients']['kcal'][k]
            else:
                value=(slot['eaten'] if slot['eaten'] is not None else slot['planned'])
                if value is None or value.get('kcal') is None:reference_known=False;continue
                for k in reference:reference[k]+=value['kcal']
    response=dict(status='unavailable',estimate=meal,budget=dict(planned_week_kcal=sum(totals) if all(isinstance(v,(int,float)) for v in totals) else None,excess_kcal=excess,correction_kcal=0,remaining_excess_kcal=excess.copy()),limits=LIMITS.copy(),days=[],workout=dict(required=False,status='optional',explanation='Nessun allenamento aggiunto automaticamente.'))
    response['budget'].update(reference_week_kcal=reference if reference_known else None,reference_scope='consumed_where_known_otherwise_planned')
    if reference_known and known:response['budget']['after_week_kcal']={k:round(reference[k]+excess[k],3) for k in reference}
    def unavailable(reason):
        response.update(reason=reason,explanation=reason+' Puoi lasciare invariato il piano.');return response
    if not known or response['budget']['planned_week_kcal'] is None:return unavailable('Manca un piano completo con calorie note.')
    if not profile.get('daily_meals',{}).get('enabled') or profile['daily_meals'].get('targets_demo',True):return unavailable('Servono target personali confermati per la giornata intera.')
    surplus=max(0,excess['min'])
    if surplus<=0:
        response.update(status='unchanged',explanation='L’intervallo non indica un surplus certo: nessuna riduzione proposta.');return response
    active=[v for v in snap['views'] if v['date']>diary.local_today().isoformat() and any(m['planned'] and m['state']=='unknown' and not m['planned']['locked'] for m in v['meals'])]
    if not active:return unavailable('Non restano giorni modificabili nella settimana.')
    by_date={v['date']:v for v in active};configs={};locks=[];prior={}
    from day_orchestration import family
    for v in snap['views']:
        if v['date'] in by_date:continue
        for m in v['meals']:
            if m['slot'] not in ('lunch','dinner') or not m['planned']:continue
            candidates=[x for x in (m['eaten']['items'] if m['eaten'] is not None else m['planned']['items']) if x['food']['source']=='CREA' and family(x['food']['id'])]
            if candidates:
                identifier=max(candidates,key=lambda x:x['protein_g'])['food']['id'];prior[identifier]=prior.get(identifier,0)+1
    for view in active:
        date=view['date'];ctx=snap['context'].get(date,{});energy=ctx.get('progress_forecast',{}).get('energy_scenarios',ctx.get('energy_scenarios',{}))
        low=energy.get('consumption_kcal',{}).get('low')
        if energy.get('status')!='available' or not isinstance(low,(int,float)) or not math.isfinite(low) or low<=0:return unavailable('Manca lo scenario basso del consumo da Salute per '+date+'.')
        if not all(m['planned'] for m in view['meals']):return unavailable('Il piano di '+date+' non copre tutti i pasti.')
        index=next((m['planned']['day_index'] for m in view['meals'] if m['planned']),0)
        cfg=copy.deepcopy(make_config(profile,index));cfg.update(mode=view['mode'],day_index=index)
        targets={n:copy.deepcopy(view['targets'][n.replace('_100g','')]) for n in NUTRIENTS}
        for n,floor in FLOORS.items():targets[n]['min']=max(targets[n]['min'],floor)
        targets['kcal_100g']['min']=max(targets['kcal_100g']['min'],low-500,view['totals']['planned']['kcal']-200)
        targets['kcal_100g']['max']=min(targets['kcal_100g']['max'],view['totals']['planned']['kcal'])
        if any(t['min']>t['max'] for t in targets.values()):return unavailable('I minimi protetti impediscono una riduzione sicura per '+date+'.')
        for spec in targets.values():spec['target']=max(spec['min'],min(spec['target'],spec['max']))
        cfg['daily_meals']['targets']=targets;configs[date]=cfg
        for m in view['meals']:
            if m['state']!='unknown' or m['planned']['locked']:
                if m.get('consumed_estimate'):return unavailable('Un pasto futuro stimato a intervallo richiede una verifica manuale.')
                items=m['eaten']['items'] if m['eaten'] is not None else m['planned']['items']
                locks.append(dict(date=date,slot=m['slot'],items=[{k:x[k] for k in ('food','grams','units') if k in x} for x in items]))
    # weekly_model calls make_config for actual calendar offsets; use the date to select its snapshot.
    start=dt.date.fromisoformat(snap['start'])
    def configuration(_profile,index):return copy.deepcopy(configs[(start+dt.timedelta(days=index)).isoformat()])
    request=dict(week_start=snap['start'],day_index=0,locked=locks,_active_dates=list(by_date),_prior_frequencies=prior,solve_time_limit=30)
    foods=copy.deepcopy(foods)
    try:problem,blocks,choices,maximum=weekly_model(profile,request,configuration,foods)
    except (ValueError,KeyError) as e:return unavailable('Il modello dei pasti bloccati non è verificabile: '+str(e))
    size=len(problem['variables']);rows={date:[0.]*size for date in by_date}
    for choice in choices:rows[choice['date']][choice['q']]+=choice['nutrients'][0]
    total=[sum(row[i] for row in rows.values()) for i in range(size)];baseline={d:by_date[d]['totals']['planned']['kcal'] for d in by_date}
    problem['constraints'].append(dict(coefficients=total,relation='>=',rhs=sum(baseline.values())-surplus))
    dates=list(rows)
    for i,date in enumerate(dates):
        for other in dates[i+1:]:
            row=[a-b for a,b in zip(rows[date],rows[other])];delta=baseline[date]-baseline[other]
            for relation,rhs in (('<=',delta+25),('>=',delta-25)):problem['constraints'].append(dict(coefficients=row,relation=relation,rhs=rhs))
    problem.pop('preference_coefficients',None);problem['objective']=dict(sense='min',coefficients=total)
    from plan_diet_day import solve_problem
    result=await solve_problem(session,problem)
    if result.get('mathematical_status')!='optimal':return unavailable('Non è disponibile una soluzione ottima verificata entro i limiti e il tempo di calcolo.')
    values_verified(problem,result);plan=decode_week(problem,blocks,foods,result,maximum)
    correction=0
    for day in plan['days']:
        date=day['date'];before=baseline[date];after=day['nutrients']['kcal'];reduction=before-after
        if reduction<-1e-3 or reduction>200+1e-3:raise diary.DomainError('Limiti non verificati','unsafe_proposal',422)
        changes=[]
        for m in by_date[date]['meals']:
            selections=[s for s in day['selections'] if s['meal']==m['slot']]
            if m['state']=='unknown' and not m['planned']['locked']:changes.append(dict(slot=m['slot'],before=m['planned']['items'],after=selections))
        response['days'].append(dict(date=date,before_kcal=before,after_kcal=after,reduction_kcal=round(reduction,3),changes=changes,nutrients=day['nutrients'],constraint_report=day['constraint_report']))
        correction+=reduction
    response['budget'].update(correction_kcal=round(correction,3),remaining_excess_kcal={k:round(v-correction,3) for k,v in excess.items()})
    if reference_known:response['budget']['after_week_kcal']={k:round(reference[k]+excess[k]-correction,3) for k in reference}
    response.update(status='full' if excess['max']-correction<1 else 'partial' if correction>1e-3 else 'unchanged',explanation='Rientro completo entro i limiti.' if excess['max']-correction<1 else 'È possibile solo un rientro parziale entro i limiti. Puoi anche lasciare invariato il piano.',_plan=plan)
    return response


def decide(db,user,profile,token,proposal,action):
    if fingerprint(db,user,profile)!=proposal['state']:raise diary.DomainError('Diario o piano cambiati: ripeti l’anteprima','stale_preview',409)
    result=proposal['result'];meal=result['estimate']
    if action=='apply' and (result['status'] not in ('full','partial') or not result.get('_plan')):raise diary.DomainError('Nessuna correzione verificata da applicare')
    if diary.state(db,user,meal['date'],meal['slot'])!='unknown':raise diary.DomainError('Pasto già registrato','slot_already_logged',409)
    db.execute('INSERT INTO consumed_estimate VALUES(?,?,?,?,?)',(user,meal['date'],meal['slot'],json.dumps(meal),time.time()))
    diary.set_state(db,user,meal['date'],meal['slot'],'modified' if diary.planned(db,user,meal['date'],meal['slot']) else 'unplanned')
    changed=[]
    if action=='apply':
        for day in result['_plan']['days']:
            applied=diary.apply_plan(db,user,profile,dict(week_start=proposal['start']),dict(day,id=0),dict(plan_id=0,scope='day',date=day['date']))
            changed.extend(sorted({x['date'] for x in applied['applied_slots']}))
    from progress_analysis import invalidate_forecast
    invalidate_forecast(db,user,meal['date'],'consumed_interval_estimate')
    answer=dict(decision=action,recorded=dict(date=meal['date'],slot=meal['slot']),changed_days=changed,status='recorded')
    db.execute('INSERT INTO rebalance_decision(user_id,preview_id,decision,created,payload) VALUES(?,?,?,?,?)',(user,token,action,time.time(),json.dumps(answer)))
    return answer

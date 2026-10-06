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
LIMITS=dict(maximum_daily_reduction_kcal=200,maximum_energy_deficit_kcal=500,minimum_kcal=1400,minimum_protein_g=45,maximum_reduction_spread_kcal=25,maximum_daily_addition_kcal=200,minimum_weekly_deviation_kcal=100)
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


def diary_request(data,today):
    import rebalance_activity
    if isinstance(data,dict) and 'activity' in data:
        option=rebalance_activity.validate(data['activity']);plain={k:v for k,v in data.items() if k!='activity'}
        return dict(diary_request(plain,today),activity=option)
    if not isinstance(data,dict):raise diary.DomainError('Richiesta non valida')
    if 'from_diary' not in data:return estimate(data,today)
    if set(data)!={'date','from_diary'} or data['from_diary'] is not True:raise diary.DomainError('Richiesta dal diario non valida')
    date=diary.valid_date(data['date']);day=dt.date.fromisoformat(date)
    if not today-dt.timedelta(days=today.weekday())<=day<=today:raise diary.DomainError('Scegli una data nella settimana corrente non futura')
    return dict(date=date,from_diary=True)


def snapshot(db,user,profile,meal):
    view=diary.day_view(db,user,profile,meal['date']);original=0
    if not meal.get('from_diary'):
        slot=next(m for m in view['meals'] if m['slot']==meal['slot'])
        if slot['state']!='unknown' or db.execute('SELECT 1 FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,meal['date'],meal['slot'])).fetchone():raise diary.DomainError('Pasto già registrato','slot_already_logged',409)
        original=slot['planned']['kcal'] if slot['planned'] else 0
    start=(dt.date.fromisoformat(meal['date'])-dt.timedelta(days=dt.date.fromisoformat(meal['date']).weekday())).isoformat()
    views=[diary.day_view(db,user,profile,(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat()) for i in range(7)]
    week=db.execute("SELECT * FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,start)).fetchone()
    previous=0.;legacy=False;previous_daily={}
    for row in db.execute("SELECT payload FROM rebalance_decision WHERE user_id=? AND decision='apply' ORDER BY id",(user,)):
        answer=json.loads(row['payload'])
        if answer.get('week_start')==start and answer.get('week_plan_id')==(week['id'] if week else None):
            previous+=answer['correction_kcal']
            for day in answer.get('daily_corrections',[]):previous_daily[day['date']]=previous_daily.get(day['date'],0.)+day['reduction_kcal']
        elif answer.get('recorded') and start<=answer['recorded']['date']<=(dt.date.fromisoformat(start)+dt.timedelta(days=6)).isoformat() and 'correction_kcal' not in answer:legacy=True
    return dict(start=start,views=views,context=json.loads(week['day_context'] or '{}') if week else {},week_id=week['id'] if week else None,original_kcal=original,state=fingerprint(db,user,profile),previous_correction=previous,previous_daily_correction=previous_daily,legacy_correction=legacy)


def deviations(meal,snap):
    values=[];reason=None;excluded=[];pizza=False
    for view in snap['views']:
        if view['date']>diary.local_today().isoformat():continue
        for slot in view['meals']:
            if slot['state']=='unknown':continue
            planned=slot['planned'];baseline=planned['kcal'] if planned else 0
            actual=slot.get('consumed_estimate')
            if actual:
                nutrients=actual['nutrients'];provenance=actual['provenance']
                known=all(valid_interval(nutrients.get(k)) for k in diary.KEYS)
                pizza|=provenance.get('preset_id')=='pizzeria'
            else:
                eaten=slot['eaten'];known=eaten is not None and all(isinstance(eaten.get(k),(int,float)) and math.isfinite(eaten[k]) for k in diary.KEYS)
                nutrients={k:dict(min=eaten.get(k),max=eaten.get(k)) for k in diary.KEYS} if eaten else {}
                provenance=dict(source='diary',state=slot['state'],baseline='planned' if planned else 'unplanned_zero')
                if known and baseline is not None and nutrients['kcal']['min']>baseline:
                    for item in eaten['items']:
                        if item['food']['source']=='recipe':excluded.append((item['food']['source'],item['food']['id']))
                        if 'pizza' in item['name'].lower():pizza=True
            if planned and any(planned.get(k) is None for k in diary.KEYS):known=False
            if not known or baseline is None:
                reason='Nutrienti mancanti nel pasto registrato '+view['date']+' '+slot['slot']+'.';continue
            interval=nutrients['kcal'];difference={k:round(interval[k]-baseline,3) for k in ('min','max')}
            values.append(dict(date=view['date'],slot=slot['slot'],planned_kcal=baseline,consumed_kcal=interval,difference_kcal=difference,provenance=provenance))
        for activity in view.get('workouts',[]):
            if activity.get('kind')!='activity' or activity['status']!='skipped':continue
            estimate=activity.get('energy_estimate') or {};energy=estimate.get('energy_kcal',{})
            if estimate.get('status')!='available' or not all(isinstance(energy.get(k),(int,float)) and not isinstance(energy[k],bool) and math.isfinite(energy[k]) and energy[k]>=0 for k in ('low','high')):
                reason='Stima energetica mancante per l’attività saltata '+view['date']+'.';continue
            credit=estimate.get('rebalance_credit_kcal')
            if isinstance(credit,(int,float)) and math.isfinite(credit) and credit>=0:energy=dict(energy,low=credit,high=credit)
            values.append(dict(date=view['date'],slot='activity',kind='activity',planned_session_id=activity['planned_session_id'],planned_expenditure_kcal=dict(min=energy['low'],max=energy['high']),difference_kcal=dict(min=energy['low'],max=energy['high']),provenance=dict(source='skipped_planned_activity',energy_source=estimate['source'],net=True)))
    optional={k:0. for k in ('min','max')}
    if not meal.get('from_diary'):
        original=snap['original_kcal']
        if not isinstance(original,(int,float)):reason='Mancano le calorie del pasto previsto.'
        else:
            optional={k:round(meal['nutrients']['kcal'][k]-original,3) for k in ('min','max')}
            values.append(dict(date=meal['date'],slot=meal['slot'],planned_kcal=original,consumed_kcal=meal['nutrients']['kcal'],difference_kcal=optional,provenance=meal['provenance']))
        pizza|=meal['provenance'].get('preset_id')=='pizzeria'
    previous=snap.get('previous_correction',0.)
    excess={k:round(sum(v['difference_kcal'][k] for v in values)-previous,3) for k in ('min','max')}
    if reason:excess={k:None for k in ('min','max')}
    dish=dict(provenance=dict(preset_id='pizzeria' if pizza else None),excluded_foods=excluded)
    return values,excess,optional,reason,dish


async def preview(session,profile,meal,snap,make_config,foods,health=None):
    import rebalance_activity
    activity_option=rebalance_activity.validate(meal.get("activity"))
    recorded,excess,optional,missing,dish=deviations(meal,snap)
    known=missing is None
    totals=[v['totals']['planned']['kcal'] if v['totals']['planned'] else None for v in snap['views']]
    reference={k:0. for k in ('min','max')}
    reference_known=True
    for view in snap['views']:
        for slot in view['meals']:
            if slot['slot']=='afternoon_snack' and not profile.get('daily_meals',{}).get('afternoon_fruit',True) and slot['planned'] is None and slot['state']=='unknown':continue
            if slot.get('consumed_estimate'):
                for k in reference:reference[k]+=slot['consumed_estimate']['nutrients']['kcal'][k]
            else:
                value=(slot['eaten'] if slot['eaten'] is not None else slot['planned'])
                if value is None or value.get('kcal') is None:reference_known=False;continue
                for k in reference:reference[k]+=value['kcal']
    response=dict(status='unavailable',source='diary' if meal.get('from_diary') else 'meal',estimate=meal,deviations=recorded,budget=dict(planned_week_kcal=sum(totals) if all(isinstance(v,(int,float)) for v in totals) else None,excess_kcal=excess,correction_kcal=0,remaining_excess_kcal=excess.copy()),limits=LIMITS.copy(),days=[],workout=dict(required=False,status='optional',explanation='Nessun allenamento aggiunto automaticamente.'))
    response['budget'].update(correction_diet_kcal=0,correction_activity_kcal=0)
    response['limits']['activity']=rebalance_activity.LIMITS.copy()
    response['workout']['requested_mode']=activity_option['mode']
    response['budget'].update(reference_week_kcal=reference if reference_known else None,reference_scope='consumed_where_known_otherwise_planned',previous_correction_kcal=snap.get('previous_correction',0.))
    if reference_known and known:response['budget']['after_week_kcal']={k:round(reference[k]+optional[k],3) for k in reference}
    def unavailable(reason):
        response.update(reason=reason,explanation=reason+' Puoi lasciare invariato il piano.');return response
    if missing:return unavailable(missing)
    if snap.get('legacy_correction'):return unavailable('Un rientro precedente non conserva la quantità recuperata: manca una base verificabile.')
    if not known or response['budget']['planned_week_kcal'] is None:return unavailable('Manca un piano completo con calorie note.')
    if not profile.get('daily_meals',{}).get('enabled') or profile['daily_meals'].get('targets_demo',True):return unavailable('Servono target personali confermati per la giornata intera.')
    direction=1 if excess['min']>0 else -1 if excess['max']<0 else 0
    surplus=excess['min'] if direction==1 else -excess['max'] if direction==-1 else 0
    if surplus<=LIMITS['minimum_weekly_deviation_kcal']:
        response.update(status='unchanged',explanation='Lo scostamento settimanale garantito non supera 100 kcal: il piano resta invariato.');return response
    active=[v for v in snap['views'] if v['date']>diary.local_today().isoformat() and any(m['planned'] and m['state']=='unknown' and not m['planned']['locked'] for m in v['meals'])]
    if not active:return unavailable('Non restano giorni modificabili nella settimana.')
    by_date={v['date']:v for v in active};configs={};locks=[];prior={};low_by_date={}
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
        low_by_date[date]=low
        required=set(diary.SLOTS)-({'afternoon_snack'} if not profile['daily_meals']['afternoon_fruit'] else set())
        if not all(m['planned'] for m in view['meals'] if m['slot'] in required):return unavailable('Il piano di '+date+' non copre tutti i pasti previsti dal profilo.')
        index=next((m['planned']['day_index'] for m in view['meals'] if m['planned']),0)
        cfg=copy.deepcopy(make_config(profile,index));cfg.update(mode=view['mode'],day_index=index)
        targets={n:copy.deepcopy(view['targets'][n.replace('_100g','')]) for n in NUTRIENTS}
        for n,floor in FLOORS.items():targets[n]['min']=max(targets[n]['min'],floor)
        previous_daily=snap.get('previous_daily_correction',{}).get(date,0.)
        reduction_room=min(200,max(0,200-previous_daily));addition_room=min(200,max(0,200+previous_daily))
        targets['kcal_100g']['min']=max(targets['kcal_100g']['min'],low-500,view['totals']['planned']['kcal']-(reduction_room if direction==1 else 0))
        targets['kcal_100g']['max']=min(targets['kcal_100g']['max'],view['totals']['planned']['kcal']+(addition_room if direction==-1 else 0))
        if any(t['min']>t['max'] for t in targets.values()):return unavailable('I limiti protetti impediscono una correzione sicura per '+date+'.')
        for spec in targets.values():spec['target']=max(spec['min'],min(spec['target'],spec['max']))
        cfg['daily_meals']['targets']=targets;configs[date]=cfg
        for m in view['meals']:
            if m['state']!='unknown' or m['planned'] and m['planned']['locked']:
                if m.get('consumed_estimate'):return unavailable('Un pasto futuro stimato a intervallo richiede una verifica manuale.')
                items=m['eaten']['items'] if m['eaten'] is not None else m['planned']['items'] if m['planned'] else []
                locks.append(dict(date=date,slot=m['slot'],items=[{k:x[k] for k in ('food','grams','units') if k in x} for x in items]))
    # weekly_model calls make_config for actual calendar offsets; use the date to select its snapshot.
    start=dt.date.fromisoformat(snap['start'])
    def configuration(_profile,index):return copy.deepcopy(configs[(start+dt.timedelta(days=index)).isoformat()])
    request=dict(week_start=snap['start'],day_index=0,locked=locks,_active_dates=list(by_date),_prior_frequencies=prior,solve_time_limit=30)
    from rebalance_model import build,excluded_dishes,changed
    from plan_diet_day import solve_problem
    foods=copy.deepcopy(foods);forbidden=excluded_dishes(dish,foods)
    baseline={d:by_date[d]['totals']['planned']['kcal'] for d in by_date}
    plan=None;stage_used=None;activity_choices=[];activity_reasons=[];added_by_date={}
    for stage in ('grams','main_meals','all_meals'):
        try:problem,blocks,choices,maximum,costs=build(profile,request,configuration,foods,active,stage,forbidden)
        except (ValueError,KeyError):continue
        size=len(problem['variables']);rows={date:[0.]*size for date in by_date}
        for choice in choices:rows[choice['date']][choice['q']]+=choice['nutrients'][0]
        if direction==1:
            activity_choices,activity_reasons=rebalance_activity.add(problem,active,profile,activity_option,rows,baseline,surplus,low_by_date,health)
        size=len(problem['variables'])
        total=[sum(row[i] for row in rows.values()) for i in range(size)]
        problem['constraints'].append(dict(coefficients=total,relation='>=' if direction==1 else '<=',rhs=sum(baseline.values())-direction*surplus))
        dates=list(rows)
        for i,date in enumerate(dates):
            for other in dates[i+1:]:
                row=[a-b for a,b in zip(rows[date],rows[other])];delta=baseline[date]-baseline[other]+snap.get('previous_daily_correction',{}).get(date,0)-snap.get('previous_daily_correction',{}).get(other,0)
                for relation,rhs in (('<=',delta+25),('>=',delta-25)):problem['constraints'].append(dict(coefficients=row,relation=relation,rhs=rhs))
        result=None;phase='result'
        try:
            problem['objective']=dict(sense='min',coefficients=[direction*v for v in total])
            phase='solver'
            result=await solve_problem(session,problem)
            phase='result'
            if result.get('mathematical_status')!='optimal':continue
            values=values_verified(problem,result);intake=sum(a*b for a,b in zip(total,values))
            if direction*(sum(baseline.values())-intake)<=1e-3:continue
            # Within the first feasible level, attain its maximum safe correction,
            # then minimize actual food/portion changes, not calorie intake alone.
            problem['constraints'].append(dict(coefficients=total,relation='<=' if direction==1 else '>=',rhs=intake+direction*.001))
            activity_costs={c['y']:100 for c in activity_choices};activity_costs.update({c['q']:c['step'] for c in activity_choices})
            problem['objective']['coefficients']=[costs.get(i,0.)+activity_costs.get(i,0.) for i in range(size)]
            phase='solver'
            result=await solve_problem(session,problem)
            phase='result'
            if result.get('mathematical_status')!='optimal':continue
            final_values=values_verified(problem,result)
            added_by_date=rebalance_activity.decode(activity_choices,final_values,profile,health) if direction==1 else {}
            phase='days'
            plan=decode_week(problem,blocks,foods,result,maximum);stage_used=stage;break
        except Exception as error:
            from rebalance_verification import failure
            reason,details=failure(error,stage,phase,problem,result,choices)
            response['verification']=details
            return unavailable(reason)
    if plan is None:return unavailable('Non è disponibile una soluzione ottima verificata entro i limiti e il tempo di calcolo.')
    response['change_policy']=dict(version='portion-first-v1',stage=stage_used,portion_fraction=.2,step_g=5,substitution_cost=10000,snack_change_cost=100000,excluded_food_ids=sorted(forbidden))
    try:
        correction=0;activity_correction=0;activity_sessions=[]
        for day in plan['days']:
            date=day['date'];before=baseline[date];after=day['nutrients']['kcal'];reduction=before-after
            if direction*reduction<-1e-3 or direction*reduction>200+1e-3:raise diary.DomainError('Limiti non verificati','unsafe_proposal',422)
            changes=[]
            for m in by_date[date]['meals']:
                selections=[s for s in day['selections'] if s['meal']==m['slot']]
                if m['planned'] and m['state']=='unknown' and not m['planned']['locked'] and changed(m['planned']['items'],selections):changes.append(dict(slot=m['slot'],before=m['planned']['items'],after=selections))
            activities=added_by_date.get(date,[])
            added=sum(a['energy_kcal']['low'] for a in activities)
            if added and after-added<low_by_date[date]-500-1e-3:raise diary.DomainError('Deficit complessivo non verificato','unsafe_proposal',422)
            for item in activities:
                stored=copy.deepcopy(item['_session']);stored['energy_estimate']['rebalance_credit_kcal']=item['energy_kcal']['low']
                activity_sessions.append(dict(date=date,session=stored))
            activity_correction+=added
            response['days'].append(dict(activities=[{k:v for k,v in a.items() if not k.startswith('_')} for a in activities],date=date,before_kcal=before,after_kcal=after,reduction_kcal=round(reduction,3),changes=changes,nutrients=day['nutrients'],constraint_report=day['constraint_report']))
            correction+=reduction
        food_correction=correction
        if activity_correction>max(0,food_correction)+1e-3:raise diary.DomainError('Quota attività non verificata','unsafe_proposal',422)
        correction+=activity_correction
        response['_activity_sessions']=activity_sessions
        response['workout'].update(excluded_days=activity_reasons,explanation='Attività facoltative richieste, conteggiate nello scenario basso; confermale quando svolte.' if activity_sessions else 'Nessuna attività aggiunta: '+('scostamento negativo, restituiamo energia tramite il cibo.' if direction==-1 else 'non necessaria o nessuna candidata compatibile con i limiti.'))
        response['budget'].update(correction_diet_kcal=round(food_correction,3),correction_activity_kcal=round(activity_correction,3),correction_kcal=round(correction,3),remaining_excess_kcal={k:round(v-correction,3) for k,v in excess.items()})
        if reference_known:response['budget']['after_week_kcal']={k:round(reference[k]+optional[k]-food_correction,3) for k in reference}
        complete=max(abs(v-correction) for v in excess.values())<1
        response.update(status='full' if complete else 'partial' if abs(correction)>1e-3 else 'unchanged',explanation='Rientro completo entro i limiti.' if complete else 'È possibile solo un rientro parziale entro i limiti. Puoi anche lasciare invariato il piano.',_plan=plan)
        return response
    except Exception as error:
        from rebalance_verification import failure
        reason,details=failure(error,stage_used,'safety',problem,result,choices)
        response.update(status='unavailable',days=[],verification=details)
        response['budget'].update(correction_kcal=0,remaining_excess_kcal=excess.copy())
        response.pop('_plan',None);response.pop('_activity_sessions',None)
        if reference_known:response['budget']['after_week_kcal']={k:round(reference[k]+optional[k],3) for k in reference}
        return unavailable(reason)



def decide(db,user,profile,token,proposal,action):
    if db.execute('SELECT 1 FROM rebalance_decision WHERE user_id=? AND preview_id=?',(user,token)).fetchone():raise diary.DomainError('Anteprima già chiusa','stale_preview',409)
    if fingerprint(db,user,profile)!=proposal['state']:raise diary.DomainError('Diario o piano cambiati: ripeti l’anteprima','stale_preview',409)
    result=proposal['result'];meal=result['estimate']
    if action=='apply' and (result['status'] not in ('full','partial') or not result.get('_plan')):raise diary.DomainError('Nessuna correzione verificata da applicare')
    from_diary=meal.get('from_diary',False)
    if not from_diary:
        if diary.state(db,user,meal['date'],meal['slot'])!='unknown':raise diary.DomainError('Pasto già registrato','slot_already_logged',409)
        db.execute('INSERT INTO consumed_estimate VALUES(?,?,?,?,?)',(user,meal['date'],meal['slot'],json.dumps(meal),time.time()))
        diary.set_state(db,user,meal['date'],meal['slot'],'modified' if diary.planned(db,user,meal['date'],meal['slot']) else 'unplanned')
    changed=[];evaluation_revisions=[]
    if action=='apply':
        import contextual_bandit as bandit
        diffs={d['date']:d['changes'] for d in result['days']}
        applications=bandit.capture_rebalance_applications(db,user,{date for date,changes in diffs.items() if changes})
        applied_slots=[]
        for day in result['_plan']['days']:
            for change in diffs[day['date']]:
                original=diary.planned(db,user,day['date'],change['slot'])
                applied=diary.apply_plan(db,user,profile,dict(week_start=proposal['start']),dict(day,id=0,role=original['role']),dict(plan_id=0,scope='meal',date=day['date'],slot=change['slot']))
                applied_slots.extend(applied['applied_slots'])
                changed.extend(x['date'] for x in applied['applied_slots'])
        evaluation_revisions=bandit.revise_rebalance_applications(db,user,profile,applications,result['_plan']['days'],applied_slots,token)
        week_row=db.execute("SELECT id FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,proposal['start'])).fetchone()
        for item in result.get('_activity_sessions',[]):
            session=item['session']
            db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,minutes,start_time,status,snapshot) VALUES(?,?,?,?,NULL,'chosen',?)",(week_row['id'],item['date'],session['id'],session['duration_seconds']/60,json.dumps(session)))
            changed.append(item['date'])
        changed=sorted(set(changed))
    from progress_analysis import invalidate_forecast
    if not from_diary:invalidate_forecast(db,user,meal['date'],'consumed_interval_estimate')
    week=db.execute("SELECT id FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,proposal['start'])).fetchone()
    answer=dict(decision=action,recorded=None if from_diary else dict(date=meal['date'],slot=meal['slot']),changed_days=changed,status='closed' if from_diary else 'recorded',week_start=proposal['start'],week_plan_id=week['id'] if week else None,correction_kcal=result['budget']['correction_kcal'] if action=='apply' else 0,daily_corrections=[dict(date=d['date'],reduction_kcal=d['reduction_kcal']) for d in result['days']] if action=='apply' else [],evaluation_revisions=evaluation_revisions)
    db.execute('INSERT INTO rebalance_decision(user_id,preview_id,decision,created,payload) VALUES(?,?,?,?,?)',(user,token,action,time.time(),json.dumps(answer)))
    return answer

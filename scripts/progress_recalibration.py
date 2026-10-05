"""Explicitly approved, bounded calibration of future targets; no automatic writes."""
import copy
import datetime as dt
import hashlib
import json
import math
import statistics
import time
from diary_service import DomainError,integer
from daily_meals import validate as validate_daily
from target_validation import target_warnings
import progress_analysis as analysis

VERSION='recalibration-v1'
SAFETY=dict(max_weekly_change_kcal=100,max_weekly_change_fraction=.05,approval_cooldown_days=7,proposal_expiry_days=7,minimum_complete_days=14,minimum_weight_days=6,maximum_weight_gap_days=7,minimum_kcal=1400,minimum_protein_g=45,minimum_fat_g=25,minimum_carbs_g=90,maximum_absolute_weight_slope_kg_per_day=.15,minimum_estimated_expenditure_kcal=1000,maximum_estimated_expenditure_kcal=6000)
FLOORS=dict(kcal_100g=1400,protein_g_100g=45,fat_g_100g=25,carbs_available_g_100g=90)


def migrate(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS recalibration_proposal(id INTEGER PRIMARY KEY,user_id INTEGER,checkin_date TEXT,created REAL,state TEXT,fingerprint TEXT,payload TEXT,decided REAL,decision_reason TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS single_pending_recalibration ON recalibration_proposal(user_id) WHERE state='pending';
    CREATE INDEX IF NOT EXISTS recalibration_owner ON recalibration_proposal(user_id,created);
    INSERT OR IGNORE INTO schema_migration VALUES(4,strftime('%s','now'));''')


def safe_targets(targets):
    validate_daily(dict(enabled=True,allow_second_bar=False,afternoon_fruit=True,banana_min_g=100,banana_max_g=220,targets=targets,targets_demo=False,policy='personalized_habits'))
    if any(targets[key]['min']<floor for key,floor in FLOORS.items()):raise ValueError('Minimi del profilo inferiori ai limiti fissi della ricalibrazione.')
    if target_warnings(targets):raise ValueError('Target energetico e macro non coerenti: verificare prima il profilo.')


def target_changes(groups,desired_delta):
    for targets in groups.values():safe_targets(targets)
    lower=[];upper=[]
    for targets in groups.values():
        energy=targets['kcal_100g'];step=min(100,.05*energy['target'])
        lower.append(math.ceil((max(energy['min'],energy['target']-step)-energy['target'])/5)*5)
        upper.append(math.floor((min(energy['max'],energy['target']+step)-energy['target'])/5)*5)
    low=max(lower);high=min(upper);delta=max(low,min(high,round(desired_delta/5)*5))
    if not delta:return None
    result={}
    for group,before in groups.items():
        after=copy.deepcopy(before);after['kcal_100g']['target']+=delta
        safe_targets(after);result[group]=dict(before=copy.deepcopy(before),after=after,delta_kcal=delta)
    verify_changes(result)
    return dict(changes=result,requested_delta_kcal=desired_delta,applied_delta_kcal=delta,allowed_delta_kcal=dict(min=low,max=high),limits_applied=['weekly_change_cap','existing_profile_intervals','fixed_nutrient_floors','macro_targets_and_bounds_preserved','energy_macro_consistency'])


def verify_changes(changes):
    if not isinstance(changes,dict) or 'daily' not in changes or set(changes)-{'daily','rest','training'}:raise DomainError('Proposta di target non valida','unsafe_proposal',409)
    for change in changes.values():
        before=change['before'];after=change['after'];safe_targets(before);safe_targets(after)
        old=before['kcal_100g'];new=after['kcal_100g'];delta=new['target']-old['target']
        if abs(delta)>min(100,.05*old['target'])+1e-8 or abs(delta-change['delta_kcal'])>1e-8 or any(after[n]!=before[n] for n in FLOORS if n!='kcal_100g') or any(new[k]!=old[k] for k in ('min','max')):raise DomainError('Limiti fissi della proposta superati','unsafe_proposal',409)


def fingerprint(db,user,profile,report,measurements):
    tables={}
    tables['profile']=profile;tables['measurements']=measurements
    for table,query in {
        'estimates':'SELECT * FROM consumed_estimate WHERE user_id=? ORDER BY date,slot',
        'weeks':'SELECT * FROM week_plan WHERE user_id=? ORDER BY id',
        'meals':'SELECT p.* FROM planned_meal p JOIN week_plan w ON w.id=p.week_plan_id WHERE w.user_id=? ORDER BY p.id',
        'diary':'SELECT * FROM diary_entry WHERE user_id=? ORDER BY id',
        'meal_log':'SELECT * FROM meal_log WHERE user_id=? ORDER BY date,slot',
        'manual_measurement':'SELECT * FROM measurement WHERE user_id=? ORDER BY id',
        'workout_log':'SELECT * FROM workout_log WHERE user_id=? ORDER BY id',
        'planned_session':'SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? ORDER BY s.id',
        'set_log':'SELECT s.* FROM set_log s JOIN workout_log w ON w.id=s.workout_log_id WHERE w.user_id=? ORDER BY s.id',
    }.items():tables[table]=[dict(row) for row in db.execute(query,(user,))]
    # Full daily totals include observed sessions already. Never add workout calories.
    tables['health']=dict(scenario_status=(report or {}).get('scenarios',{}).get('status'),daily=(report or {}).get('daily'),import_fingerprint=(report or {}).get('import',{}).get('fingerprint'),analysis_version=(report or {}).get('analysis_version'))
    return hashlib.sha256(json.dumps(tables,sort_keys=True,allow_nan=False).encode()).hexdigest()


def cooldown(db,user):
    last=db.execute("SELECT decided FROM recalibration_proposal WHERE user_id=? AND state='approved' ORDER BY decided DESC LIMIT 1",(user,)).fetchone()
    recent=bool(last and time.time()-last['decided']<7*86400)
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='goal_energy_proposal'").fetchone():
        goal=db.execute("SELECT max(decided) FROM goal_energy_proposal WHERE user_id=? AND state='approved'",(user,)).fetchone()[0]
        recent=recent or goal is not None and time.time()-goal<7*86400
    return recent


def make_proposal(db,user,profile,report,measurements,checkin,today):
    age=(today-checkin).days
    if age<0 or age>=7:return analysis.unavailable('Il check-in è fuori dalla settimana corrente; nessuna proposta retroattiva.')
    settings=profile.get('daily_meals',{})
    if not settings.get('enabled') or settings.get('targets_demo',True):return analysis.unavailable('Servono target personali di giornata intera confermati, non demo.')
    if cooldown(db,user):return analysis.unavailable('Una ricalibrazione è stata approvata negli ultimi sette giorni.')
    start=checkin-dt.timedelta(days=14);weeks=[analysis.week_analysis(db,user,profile,(start+dt.timedelta(days=7*i)).isoformat(),checkin) for i in range(2)]
    if any(w['kcal_average']['status']!='available' or w['kcal_average']['days']!=7 or w['diet']['status']!='available' or w['diet']['value']<.8 for w in weeks):return analysis.unavailable('Servono quattordici giornate intere registrate con aderenza dieta almeno 80%.')
    if any(w['training']['planned'] and (w['training']['status']!='available' or w['training']['value']<.8) or w['training']['free_done'] for w in weeks):return analysis.unavailable('Allenamenti incompleti o diversi dal piano: prima chiarire l’esecuzione.')
    views=[v for w in weeks for v in w['days']]
    if any(abs(v['totals']['eaten']['kcal']-v['totals']['planned']['kcal'])>max(v['totals']['planned']['kcal'],1)*.1 for v in views):return analysis.unavailable('Scostamenti calorici dal piano oltre il 10%; prima verificare l’aderenza.')
    weight=analysis.weight_series(measurements,checkin);points=[p for p in weight['daily_points'] if start.isoformat()<=p['date']<=checkin.isoformat()]
    if len(points)<6 or points[0]['date']!=start.isoformat() or points[-1]['date']!=checkin.isoformat() or any((dt.date.fromisoformat(b['date'])-dt.date.fromisoformat(a['date'])).days>7 for a,b in zip(points,points[1:])):return analysis.unavailable('Servono almeno sei giorni distinti di peso, estremi dei quattordici giorni inclusi, senza buchi oltre sette giorni.')
    rates=[(b['value']-a['value'])/(dt.date.fromisoformat(b['date'])-dt.date.fromisoformat(a['date'])).days for i,a in enumerate(points) for b in points[i+1:] if (dt.date.fromisoformat(b['date'])-dt.date.fromisoformat(a['date'])).days>=7]
    slope=statistics.median(rates)
    if abs(slope)>.15:return analysis.unavailable('Variazione di peso troppo rapida per questa stima locale.')
    health_days={d['date']:d for d in (report or {}).get('daily',[]) if d.get('usable_for_baseline') and analysis.number(d.get('total_estimated_kcal'))}
    if (report or {}).get('scenarios',{}).get('status')!='available' or any(v['date'] not in health_days for v in views):return analysis.unavailable('Consumo Salute recente e completo richiesto sugli stessi quattordici giorni.')
    balance=profile.get('energy_balance_target_kcal')
    if balance is None:
        goals={w['contexts'].get(v['date'],{}).get('progress_forecast',{}).get('energy_balance_target_kcal') for w in weeks for v in w['days']}
        if len(goals)==1:balance=next(iter(goals))
    if not analysis.number(balance) or not -1000<=balance<=1000:return analysis.unavailable('Indica un bilancio energetico esplicito entro i limiti della ricalibrazione.')
    intake=statistics.mean(v['totals']['eaten']['kcal'] for v in views);baseline=statistics.mean(health_days[v['date']]['total_estimated_kcal'] for v in views)
    inferred=intake-7700*slope
    if not 1000<=inferred<=6000 or not 1000<=baseline<=6000:return analysis.unavailable('Stima di consumo fuori dall’intervallo ammesso: richiede revisione dei dati.')
    estimate=.75*baseline+.25*inferred
    mad=statistics.median(abs(r-slope) for r in rates)
    uncertainty=max(200,7700*1.4826*mad,7700*2*math.sqrt(.16)/14,abs(inferred-baseline)*.5)
    groups={k:copy.deepcopy(settings['targets']) for k in ('daily','rest','training')}
    sources=dict(rest='profile_daily_baseline',training='profile_daily_baseline')
    explicit=profile.get('day_type_targets',{})
    if explicit:
        if not isinstance(explicit,dict) or set(explicit)!= {'rest','training'}:return analysis.unavailable('Target per tipo di giornata non validi.')
        groups.update(copy.deepcopy(explicit));sources={k:'profile_day_type_targets' for k in explicit}
    else:
        for w in weeks:
            for date,c in sorted(w['contexts'].items()):
                if c.get('day_type') in ('rest','training') and c.get('targets'):
                    groups[c['day_type']]=copy.deepcopy(c['targets']);sources[c['day_type']]='latest_applied_plan_day_targets'
    # Preserve the day-type offsets; the same bounded change applies to each target.
    old_target=settings['targets']['kcal_100g']['target'];desired=estimate+balance-old_target
    try:adjustment=target_changes(groups,desired)
    except ValueError as exc:return analysis.unavailable(str(exc))
    if adjustment is None:return dict(status='no_adjustment',reason='I target sono già vicini alla stima oppure i limiti impediscono una variazione.',proposal=None)
    payload=dict(version=VERSION,status='pending',checkin_date=checkin.isoformat(),rationale='Due settimane complete e aderenti permettono una stima provvisoria; proponiamo una variazione piccola, da approvare.',data_used=dict(start=start.isoformat(),end=checkin.isoformat(),complete_intake_days=14,weight_days=len(points),weight_points=[{k:p[k] for k in ('date','value','raw_count','source')} for p in points],consumption_dates=[v['date'] for v in views],eaten_average_kcal=intake,health_average_kcal=baseline,weight_slope_kg_per_day=slope,day_type_target_sources=sources,adherence=[dict(week_start=w['week_start'],diet=w['diet']['value'],training=w['training']['value']) for w in weeks]),expenditure=dict(status='provisional',device_reference_kcal=baseline,correction_kcal=estimate-baseline,value_kcal=estimate,low_kcal=max(1000,estimate-uncertainty),high_kcal=min(6000,estimate+uncertainty),inferred_from_weight_kcal=inferred,source='75_percent_health_total_plus_25_percent_short_horizon_balance',no_workout_calories_added=True),uncertainty=dict(kind='sensitivity_range_not_confidence_interval',half_width_kcal=uncertainty,limitations=['Idratazione, diario e stima del dispositivo influenzano il risultato.','7700 kcal/kg è un’equivalenza contabile breve, non un modello di adattamento metabolico.']),energy_balance_target_kcal=balance,safety_limits=copy.deepcopy(SAFETY),**adjustment)
    token=fingerprint(db,user,profile,report,measurements)
    db.execute("UPDATE recalibration_proposal SET state='superseded',decided=? WHERE user_id=? AND state='pending'",(time.time(),user))
    identifier=db.execute("INSERT INTO recalibration_proposal(user_id,checkin_date,created,state,fingerprint,payload) VALUES(?,?,?,'pending',?,?)",(user,checkin.isoformat(),time.time(),token,json.dumps(payload))).lastrowid
    return dict(status='available',proposal=dict(payload,id=identifier,state_token=token))


def history(db,user):
    rows=db.execute('SELECT * FROM recalibration_proposal WHERE user_id=? ORDER BY id DESC LIMIT 100',(user,)).fetchall()
    return [dict(json.loads(r['payload']),id=r['id'],status=r['state'],state_token=r['fingerprint'],created=r['created'],decided=r['decided'],decision_reason=r['decision_reason']) for r in rows]


def decide(db,user,profile,report,measurements,identifier,data,decision,today):
    integer(identifier,1,2**63-1)
    row=db.execute('SELECT * FROM recalibration_proposal WHERE id=? AND user_id=?',(identifier,user)).fetchone()
    if row is None:raise DomainError('Proposta non trovata','not_found',404)
    if not isinstance(data,dict) or set(data)-{'state_token','reason'} or not isinstance(data.get('state_token'),str):raise DomainError('Decisione non valida')
    if not isinstance(data.get('reason',''),str) or len(data.get('reason',''))>2000:raise DomainError('Motivazione non valida')
    if row['state']!='pending':raise DomainError('Proposta già chiusa','proposal_closed',409)
    if data['state_token']!=row['fingerprint'] or fingerprint(db,user,profile,report,measurements)!=row['fingerprint']:raise DomainError('Dati, piano o profilo cambiati; ripeti il check-in','progress_state_changed',409)
    if not 0<=(today-dt.date.fromisoformat(row['checkin_date'])).days<7:raise DomainError('Proposta scaduta; ripeti il check-in','proposal_expired',409)
    payload=json.loads(row['payload'])
    if decision=='approve':
        if cooldown(db,user):raise DomainError('Limite settimanale già utilizzato','recalibration_cooldown',409)
        try:verify_changes(payload['changes'])
        except ValueError as exc:raise DomainError(str(exc),'unsafe_proposal',409)
        updated=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user,)).fetchone()['profile'])
        updated['daily_meals']=copy.deepcopy(profile['daily_meals']);updated['daily_meals']['targets']=payload['changes']['daily']['after']
        day_types={k:v['after'] for k,v in payload['changes'].items() if k!='daily'}
        if set(day_types)== {'rest','training'}:updated['day_type_targets']=day_types
        updated['energy_balance_target_kcal']=payload['energy_balance_target_kcal']
        updated['personal_expenditure_estimate']=dict(payload['expenditure'],calibrated_on=row['checkin_date'],proposal_id=identifier)
        db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(updated),user))
    db.execute('UPDATE recalibration_proposal SET state=?,decided=?,decision_reason=? WHERE id=? AND user_id=?',(decision+'d' if decision=='approve' else 'rejected',time.time(),data.get('reason',''),identifier,user))
    return dict(id=identifier,status='approved' if decision=='approve' else 'rejected',targets_changed=decision=='approve')

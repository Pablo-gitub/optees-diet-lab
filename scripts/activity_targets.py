"""Explicit, atomic proposals of day targets from planned net activity energy."""
import copy
import datetime as dt
import hashlib
import json
import math
import time
from pathlib import Path
from diary_service import DomainError,integer,valid_date
import progress_analysis as analysis
import progress_recalibration as calibration
import activity_service
from joint_energy import finite,SCENARIOS,ACTIVITIES
ROOT=Path(__file__).resolve().parents[1]
VERSION='activity-targets-v2-mifflin'


def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS activity_target_proposal(id INTEGER PRIMARY KEY,user_id INTEGER,created REAL,state TEXT,state_token TEXT,payload TEXT,request TEXT,decided REAL,reason TEXT)')


def dates(start):return [(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat() for i in range(7)]


def selection(db,user,data):
    if not isinstance(data,dict) or set(data)-{'week_start','plan_set_id','plan_id','estimated_non_workout_kcal'}:raise DomainError('Richiesta di target non valida')
    start=valid_date(data.get('week_start'));sessions=[];source='applied_diary_sessions'
    if 'plan_set_id' in data or 'plan_id' in data:
        integer(data.get('plan_set_id'),1,2**63-1);integer(data.get('plan_id'),1,2**63-1)
        row=db.execute('SELECT payload FROM plan_set WHERE id=? AND user_id=?',(data['plan_set_id'],user)).fetchone()
        if not row:raise DomainError('Piano non trovato','not_found',404)
        payload=json.loads(row['payload']);plan=next((p for p in payload.get('plans',[]) if p['id']==data['plan_id']),None)
        if not plan:raise DomainError('Alternativa non trovata','not_found',404)
        if payload.get('kind') not in ('workout','joint') or payload.get('week_start')!=start:raise DomainError('Serve un piano palestra/congiunto della stessa settimana')
        sessions=copy.deepcopy(plan['workout_sessions']);source='selected_plan'
    else:
        for row in db.execute("SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? AND w.status='active' AND s.date>=? AND s.date<=? AND s.status!='skipped' ORDER BY s.date,s.id",(user,start,dates(start)[-1])):
            sessions.append(dict(date=row['date'],session_id=row['session_id'],start_time=row['start_time'],session=json.loads(row['snapshot'])))
    if any(s.get('date') not in dates(start) for s in sessions):raise DomainError('Sessioni fuori dalla settimana')
    return start,sessions,source


def context_key(profile):
    value=dict(daily_targets=profile.get('daily_meals',{}).get('targets'),day_type_targets=profile.get('day_type_targets'),balance=profile.get('energy_balance_target_kcal'),goals=profile.get('goals'))
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def signature(sessions):
    return sorted(json.dumps(dict(session_id=s['session_id'],duration_seconds=s['session']['duration_seconds'],start_time=s.get('start_time')),sort_keys=True) for s in sessions)


def session_energy(session,weight,health=None):
    snapshot=session['session']
    from workout_sessions import validate_session
    try:validate_session(snapshot)
    except (KeyError,TypeError,ValueError):return analysis.unavailable('Sessione senza durata e timeline verificabili.')
    minutes=snapshot['duration_seconds']/60
    if snapshot.get('kind')=='activity':
        row=next((a for a in activity_service.catalog()['activities'] if a['id']==snapshot.get('activity_id')),None)
        if not row or not snapshot.get('additional_activity'):return analysis.unavailable('Attività aggiuntiva non verificabile.')
        return activity_service.energy(row,minutes,weight,health)
    definitions=json.loads((ROOT/'config/workout-energy-estimates.json').read_text())
    entry=definitions['sessions'].get(session['session_id']) or definitions['formats'].get(snapshot.get('format'))
    if not entry:return analysis.unavailable('Manca una stima di energia per '+session['session_id'])
    activity=ACTIVITIES.get(session['session_id'],'HKWorkoutActivityTypeTraditionalStrengthTraining' if snapshot.get('format')=='sets' else 'HKWorkoutActivityTypeFunctionalStrengthTraining')
    row=dict(met=entry['met'],compendium_url=entry['url'],healthkit_types=[activity])
    empirical=activity_service.energy(row,minutes,None,health)
    if empirical['status']=='available':return empirical
    work=sum(e['duration_seconds'] for e in snapshot['timeline'] if e['kind'] in ('work','hold'))/60
    estimate=activity_service.energy(row,work,weight)
    if estimate['status']=='available':estimate.update(source='compendium_workout_net_work_phase',compendium_code=entry['code'],mapping_evidence='heuristic',work_minutes=work,assumption='Proxy MET sulla sola fase di lavoro; recuperi, riscaldamento e transizioni non accreditati. '+entry['assumption'])
    return estimate


def approved_baseline(profile):
    """Only an explicit, current approval; never infer an unapproved base."""
    approved=profile.get('approved_activity_targets',{})
    value=approved.get('baseline',{})
    if approved.get('context_key')!=context_key(profile) or value.get('source') not in ('user_declared_non_workout_estimate','mifflin_st_jeor'):return None
    try:
        from diary_service import local_today
        age=(local_today()-dt.date.fromisoformat(approved['approved_on'])).days
    except (KeyError,TypeError,ValueError):return None
    if not 0<=age<=14 or value.get('status')!='available' or not all(finite(value.get(s+'_kcal')) for s in SCENARIOS):return None
    if not 1000<=value['central_kcal']<=6000 or not value['low_kcal']<=value['central_kcal']<=value['high_kcal']:return None
    if value.get('source')=='mifflin_st_jeor':
        current=formula_baseline(profile)
        if current.get('status')!='available' or current.get('inputs')!=value.get('inputs'):return None
    return copy.deepcopy(value)


def formula_baseline(profile):
    body=profile.get('goals',{}).get('body',{})
    kg=profile.get('_filtered_weight_kg');missing=[]
    if not finite(kg) or not 30<=kg<=300:missing.append('weight')
    for key,lo,hi in (('height_cm',100,250),('age_years',18,120),('activity_factor',1,2.5)):
        if not finite(body.get(key)) or not lo<=body[key]<=hi:missing.append('goals.body.'+key)
    if body.get('sex') not in ('male','female'):missing.append('goals.body.sex')
    if missing:return dict(status='unavailable',reason='Per stimare la base servono peso filtrato recente e dati personali dichiarati.',missing=missing)
    rest=10*kg+6.25*body['height_cm']-5*body['age_years']+(5 if body['sex']=='male' else -161)
    central=rest*body['activity_factor']
    if not 1000<=central<=6000:return dict(status='unavailable',reason='Stima da formula fuori dai limiti 1000–6000 kcal.',missing=[])
    return dict(status='available',source='mifflin_st_jeor',provenance='stima da formula',low_kcal=.9*central,central_kcal=central,high_kcal=1.1*central,
                resting_kcal=rest,inputs=dict(weight_kg=kg,weight_basis='filtered',**{k:body[k] for k in ('height_cm','age_years','sex','activity_factor')}),
                formula='(10 × kg + 6.25 × cm − 5 × anni + coefficiente sesso) × fattore attività',
                reference=dict(url='https://pubmed.ncbi.nlm.nih.gov/2305711/',title='Mifflin–St Jeor 1990',checked_on='2026-10-07'),
                uncertainty='±10% dichiarato come intervallo di sensibilità, non intervallo di confidenza.',
                assumption='Fattore dichiarato per attività abituale senza le sessioni aggiuntive pianificate; queste sono conteggiate separatamente al netto del riposo.')


def baseline(profile,health,override=None):
    value=(health or {}).get('non_workout_consumption_scenarios',{})
    if override is None and value.get('status')=='available' and all(finite(value.get(s+'_kcal')) for s in SCENARIOS) and 1000<=value['central_kcal']<=6000 and value['low_kcal']<=value['central_kcal']<=value['high_kcal']:
        return copy.deepcopy(value)
    approved=approved_baseline(profile) if override is None else None
    if approved is not None:return approved
    if override is None:return formula_baseline(profile)
    if override is not None:
        if not finite(override) or not 1000<=override<=6000:raise DomainError('Stima della base fuori dall’intervallo 1000–6000 kcal')
        central=override;source='user_declared_non_workout_estimate'
    if not finite(central) or not 1000<=central<=6000:return analysis.unavailable('Base stimata fuori dai limiti: occorre una stima esplicita o Salute valida.')
    return dict(status='available',source=source,low_kcal=max(1000,.8*central),central_kcal=central,high_kcal=min(6000,1.2*central),uncertainty='Base non misurata; ±20% è un intervallo di sensibilità euristico, non un intervallo di confidenza.')


def build(profile,measurements,health,start,sessions,override,today):
    weight=analysis.weight_series(measurements,today)
    profile=copy.deepcopy(profile)
    profile.pop('_filtered_weight_kg',None)
    if weight['status']=='available':profile['_filtered_weight_kg']=weight['daily_points'][-1]['filtered_kg']
    base=baseline(profile,health,override)
    if base['status']!='available':return base
    if not profile.get('daily_meals',{}).get('enabled'):return analysis.unavailable('Attiva il bilancio completo di colazione e spuntini.',missing=['daily_meals.enabled'])
    balance=profile.get('energy_balance_target_kcal')
    if not analysis.number(balance):return analysis.unavailable('Manca un bilancio calorico esplicitamente approvato.',missing=['energy_balance_target_kcal'])
    if not -1000<=balance<=1000:return analysis.unavailable('Bilancio approvato fuori dai limiti ±1000 kcal.')
    if weight['status']!='available':return analysis.unavailable('Serve una pesata recente per il peso filtrato.',missing=['weight'])
    kg=weight['daily_points'][-1]['filtered_kg']
    if not 30<=kg<=300:return analysis.unavailable('Peso filtrato fuori dai limiti 30–300 kg.')
    original=profile['daily_meals']['targets'];groups=copy.deepcopy(profile.get('day_type_targets',dict(rest=original,training=original)))
    if set(groups)!= {'rest','training'}:return analysis.unavailable('Target per tipo di giornata incompleti.')
    try:
        for targets in [original,*groups.values()]:calibration.safe_targets(targets)
    except ValueError as exc:return analysis.unavailable(str(exc))
    prior=profile.get('activity_target_parameters',{})
    ratio=prior.get('protein_g_per_kg',max([original['protein_g_100g']['target']]+[g['protein_g_100g']['target'] for g in groups.values()])/kg)
    protein=round(kg*ratio,3);fat=max(25,original['fat_g_100g']['target'],*[g['fat_g_100g']['min'] for g in groups.values()]);days=[]
    for date in dates(start):
        active=[s for s in sessions if s['date']==date];kind='training' if active else 'rest';before=groups[kind];estimates=[]
        for session in active:
            estimate=session_energy(session,kg,health)
            if estimate['status']!='available':return analysis.unavailable(estimate['reason'],missing=['energy:'+session['session_id']])
            estimates.append(dict(estimate,session_id=session['session_id']))
        net=sum(e['energy_kcal']['low'] for e in estimates);requested=base['central_kcal']+net+balance
        old=before['kcal_100g'];step=min(100,.05*old['target'])
        low=max(old['min'],old['target']-step,1400);high=min(old['max'],old['target']+step)
        proposed=max(low,min(high,round(requested/5)*5));carbs=round((proposed-4*protein-9*fat)/4,3)
        after=copy.deepcopy(before)
        for n,value in (('kcal_100g',proposed),('protein_g_100g',protein),('fat_g_100g',fat),('carbs_available_g_100g',carbs)):
            if not after[n]['min']<=value<=after[n]['max'] or value<calibration.FLOORS[n]:return analysis.unavailable('Proteine protette, grassi e carboidrati non entrano nei limiti dichiarati: rivedi i target, nessun vincolo rilassato.')
            after[n]['target']=value
        try:calibration.safe_targets(after)
        except ValueError as exc:return analysis.unavailable(str(exc))
        days.append(dict(date=date,day_type=kind,before=before,targets=after,requested_kcal=requested,proposed_kcal=proposed,delta_kcal=proposed-old['target'],net_activity_low_kcal=net,session_energy=estimates,session_signature=signature(active),limited=abs(proposed-requested)>2.5))
    type_targets={}
    for kind in ('rest','training'):
        selected=[d for d in days if d['day_type']==kind];target=copy.deepcopy(groups[kind])
        if selected:
            for n in calibration.FLOORS:target[n]['target']=sum(d['targets'][n]['target'] for d in selected)/len(selected)
        type_targets[kind]=target
    return dict(status='available',version=VERSION,week_start=start,days=days,day_type_targets=type_targets,baseline=base,energy_balance_target_kcal=balance,weight=dict(value_kg=kg,date=weight['daily_points'][-1]['date'],filter=weight['parameters']['version']),parameters=dict(protein_g_per_kg=ratio,protein_basis='existing_approved_protein_target_per_filtered_kg',fat_target_g=fat,energy_scenario='low',maximum_weekly_change_kcal=100,maximum_weekly_change_fraction=.05),limits_applied=['fixed_nutrient_floors','existing_nutrient_intervals','maximum_weekly_change_100_or_5pct','constant_protein_per_kg','no_automatic_target_changes'],reasoning=['Base senza allenamenti + energia netta prudente delle sessioni + bilancio già approvato.','Proteine costanti fra le giornate; grassi protetti; carboidrati come residuo energetico.','Le variazioni grandi procedono gradualmente entro i limiti settimanali.'],uncertainty=[base.get('uncertainty','Base Salute empirica, non misura esatta del consumo.'),'MET e intervalli sono stime; dose proteica mantenuta dal profilo, non una nuova prescrizione della matrice 8.2.'])


def state_token(db,user,profile,measurements,health,data):
    start,sessions,source=selection(db,user,data)
    value=dict(fingerprint=calibration.fingerprint(db,user,profile,health,measurements),request=data,session_selection=sessions,health_energy=dict(baseline=(health or {}).get('non_workout_consumption_scenarios'),models=(health or {}).get('workout_energy_models')))
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def cooldown(db,user):
    for table in ('activity_target_proposal','recalibration_proposal'):
        row=db.execute(f"SELECT max(decided) FROM {table} WHERE user_id=? AND state='approved'",(user,)).fetchone()[0]
        if row is not None and time.time()-row<7*86400:return True
    return False


def propose(db,user,profile,measurements,health,data,today):
    start,sessions,source=selection(db,user,data)
    if cooldown(db,user):return analysis.unavailable('Una modifica dei target è già stata approvata negli ultimi sette giorni.')
    result=build(profile,measurements,health,start,sessions,data.get('estimated_non_workout_kcal'),today)
    if result['status']!='available':return result
    token=state_token(db,user,profile,measurements,health,data);result['data_source']=source
    db.execute("UPDATE activity_target_proposal SET state='superseded' WHERE user_id=? AND state='pending'",(user,))
    identifier=db.execute("INSERT INTO activity_target_proposal(user_id,created,state,state_token,payload,request) VALUES(?,?,'pending',?,?,?)",(user,time.time(),token,json.dumps(result),json.dumps(data))).lastrowid
    return dict(status='available',proposal=dict(result,id=identifier,state_token=token,state='pending'))


def decide(db,user,profile,measurements,health,identifier,data,decision,today):
    integer(identifier,1,2**63-1)
    if not isinstance(data,dict) or set(data)-{'state_token','reason'} or not isinstance(data.get('state_token'),str) or not isinstance(data.get('reason',''),str) or len(data.get('reason',''))>2000:raise DomainError('Decisione di target non valida')
    row=db.execute('SELECT * FROM activity_target_proposal WHERE id=? AND user_id=?',(identifier,user)).fetchone()
    if not row:raise DomainError('Proposta non trovata','not_found',404)
    if row['state']!='pending' or time.time()-row['created']>=7*86400:raise DomainError('Proposta chiusa o scaduta','proposal_closed',409)
    request=json.loads(row['request'])
    if data['state_token']!=row['state_token'] or state_token(db,user,profile,measurements,health,request)!=row['state_token']:raise DomainError('Dati, programma o profilo cambiati: richiedi una nuova proposta','activity_targets_state_changed',409)
    payload=json.loads(row['payload'])
    if decision=='approve':
        if cooldown(db,user):raise DomainError('Limite settimanale già usato','recalibration_cooldown',409)
        start,sessions,_=selection(db,user,request);verified=build(profile,measurements,health,start,sessions,request.get('estimated_non_workout_kcal'),today)
        if verified['status']!='available' or verified['days']!=payload['days'] or verified['day_type_targets']!=payload['day_type_targets']:raise DomainError('Limiti della proposta non verificabili','unsafe_proposal',409)
        stored=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user,)).fetchone()['profile'])
        stored['day_type_targets']=payload['day_type_targets'];stored['activity_target_parameters']=payload['parameters']
        stored['approved_activity_targets']=dict(context_key=context_key(stored),proposal_id=identifier,approved_on=today.isoformat(),week_start=start,baseline=payload['baseline'],days={d['date']:dict(targets=d['targets'],session_signature=d['session_signature']) for d in payload['days']})
        db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(stored),user))
    state='approved' if decision=='approve' else 'rejected'
    db.execute('UPDATE activity_target_proposal SET state=?,decided=?,reason=? WHERE id=?',(state,time.time(),data.get('reason',''),identifier))
    return dict(id=identifier,status=state,targets_changed=decision=='approve',diary_changed=False)

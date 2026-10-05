"""Optional owner goals and explicitly approved energy balance, no load curve yet."""
import copy
import datetime as dt
import hashlib
import json
import math
import statistics
import time
from pathlib import Path
from diary_service import DomainError,integer,local_today
from build_workout_catalog import REVIEWED
import progress_analysis as analysis
import progress_recalibration as calibration

ROOT=Path(__file__).resolve().parents[1]
TRAINING=('strength','hypertrophy','muscular_endurance','power','cardio_fitness','fat_loss','health','mobility','agility')
CIRCUMFERENCES=('waist','hip','chest','arm','thigh')
BLOCKS=('body','activity','training_priorities','strength_anchors')


def numeric(value,low,high,label):
    if not analysis.number(value) or not low<=value<=high:raise DomainError(label+' non valido')
    return value


def strings(value,label,maximum=100):
    if not isinstance(value,list) or len(value)>maximum or any(not isinstance(x,str) or not x.strip() or len(x)>100 for x in value) or len(value)!=len(set(value)):raise DomainError(label+' non validi')
    return value


def anchors(value,today=None):
    today=today or local_today()
    if not isinstance(value,list) or len(value)>100:raise DomainError('Carichi di riferimento non validi')
    seen=set()
    for anchor in value:
        if not isinstance(anchor,dict) or set(anchor)-{'exercise_key','heavy','light'} or anchor.get('exercise_key') not in ('dumbbell-floor-press','dumbbell-deadlift','bodyweight-squat','push-up','inverted-row') or anchor['exercise_key'] in seen:raise DomainError('Esercizio di riferimento non valido o duplicato')
        seen.add(anchor['exercise_key'])
        if not any(anchor.get(k) for k in ('heavy','light')):raise DomainError('Indica almeno una serie di riferimento')
        for key,limits in (('heavy',(2,6)),('light',(10,15))):
            item=anchor.get(key)
            if item is None:continue
            if not isinstance(item,dict) or set(item)!={'kg','reps','date'}:raise DomainError('Serie di riferimento non valida')
            numeric(item['kg'],0,1000,'Carico');integer(item['reps'],*limits)
            try:day=dt.date.fromisoformat(item['date'])
            except (TypeError,ValueError):raise DomainError('Data della serie non valida')
            if day>today:raise DomainError('Serie di riferimento futura')
    return copy.deepcopy(value)


def validate_block(block,data,today=None):
    today=today or local_today()
    if block=='strength_anchors':return anchors(data,today)
    if not isinstance(data,dict):raise DomainError('Blocco obiettivi non valido')
    if block=='body':
        if set(data)-{'target_weight_kg','target_body_fat_pct','target_date','pace','pace_pct_per_week','circumferences'}:raise DomainError('Campi corpo non validi')
        for key,low,high in (('target_weight_kg',30,300),('target_body_fat_pct',3,60)):
            if data.get(key) is not None:numeric(data[key],low,high,key)
        if data.get('target_date') is not None:
            try:date=dt.date.fromisoformat(data['target_date'])
            except (ValueError,TypeError):raise DomainError('Data obiettivo non valida')
            if date<today+dt.timedelta(days=28):raise DomainError('La data obiettivo deve essere almeno fra quattro settimane')
        if data.get('pace') not in (None,'gentle','moderate','custom'):raise DomainError('Ritmo non valido')
        if data.get('pace')=='custom':numeric(data.get('pace_pct_per_week'),.001,1,'Ritmo personalizzato')
        elif data.get('pace_pct_per_week') is not None:raise DomainError('Ritmo numerico solo con custom')
        if 'circumferences' in data:
            if any(x not in CIRCUMFERENCES for x in strings(data['circumferences'],'Circonferenze')):raise DomainError('Circonferenza non supportata')
    elif block=='activity':
        if set(data)-{'gym','liked_activities','disliked_activities','max_session_minutes','max_sessions_per_day','min_gap_hours','preferred_stores'}:raise DomainError('Campi attività non validi')
        if data.get('gym') not in (None,'yes','no','maybe'):raise DomainError('Scelta palestra non valida')
        for key in ('liked_activities','disliked_activities','preferred_stores'):
            if key in data:strings(data[key],key)
        if set(data.get('liked_activities',[])) & set(data.get('disliked_activities',[])):raise DomainError('Attività sia gradita che esclusa')
        for key,low,high in (('max_session_minutes',20,240),('max_sessions_per_day',1,2),('min_gap_hours',1,24)):
            if data.get(key) is not None:integer(data[key],low,high)
        # Catalogue IDs cannot be invented before the reviewed 8.3 catalogue exists.
        catalog=ROOT/'config/activity-catalog.json'
        if catalog.exists():
            raw=json.loads(catalog.read_text());entries=raw.get('activities',[]) if isinstance(raw,dict) else raw
            allowed={a['id'] for a in entries}
            if any(x not in allowed for x in data.get('liked_activities',[])+data.get('disliked_activities',[])):raise DomainError('Attività non presente nel catalogo')
        elif data.get('liked_activities') or data.get('disliked_activities'):raise DomainError('Catalogo attività non ancora disponibile: puoi saltare questa domanda','activity_catalog_pending')
    elif block=='training_priorities':
        if set(data)-set(TRAINING) or len([v for v in data.values() if v==3])>3:raise DomainError('Al massimo tre priorità massime, su obiettivi noti')
        for value in data.values():integer(value,0,3)
    else:raise DomainError('Blocco non supportato')
    return copy.deepcopy(data)


def validate(value,today=None):
    if not isinstance(value,dict) or set(value)-set(BLOCKS):raise DomainError('Obiettivi non validi')
    return {key:validate_block(key,data,today) for key,data in value.items()}


def view(profile):
    goals=profile.get('goals',{});result={key:copy.deepcopy(goals.get(key,[] if key=='strength_anchors' else {})) for key in BLOCKS};missing=[]
    for field,prompt in [('body.target_weight_kg','Senza peso obiettivo o obiettivo di massa grassa il bilancio resta quello scelto da te.'),('body.pace','Senza ritmo o data obiettivo non si propone un bilancio.'),('activity.gym','Vuoi includere la palestra?'),('activity.preferred_stores','Senza supermercati preferiti i prodotti da comprare resteranno generici.'),('training_priorities','Quali obiettivi di allenamento ti interessano?')]:
        block,_,key=field.partition('.')
        answered=result[block].get(key) is not None if key else bool(result[block])
        if field=='body.target_weight_kg':answered=answered or result['body'].get('target_body_fat_pct') is not None
        if field=='body.pace':answered=answered or result['body'].get('target_date') is not None
        if not answered:missing.append(dict(field=field,prompt=prompt))
    if result['activity'].get('gym')!='no' and not result['strength_anchors']:missing.append(dict(field='strength_anchors',prompt='Senza serie di riferimento si conservano i carichi manuali; nessun carico viene inventato.'))
    result['missing']=missing
    result['warnings']=([dict(code='conflicting_priorities',message='Forza e resistenza muscolare entrambe massime: bilanciare gli obiettivi.')]
                        if result['training_priorities'].get('strength')==3 and result['training_priorities'].get('muscular_endurance')==3 else [])
    result['activity_defaults']=dict(max_session_minutes=90,max_sessions_per_day=1,min_gap_hours=4)
    return result


def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS goal_energy_proposal(id INTEGER PRIMARY KEY,user_id INTEGER,created REAL,state TEXT,state_token TEXT,payload TEXT,decided REAL)')


def token(db,user,profile,measurements,report):return calibration.fingerprint(db,user,profile,report,measurements)


def cooldown(db,user):
    row=db.execute("SELECT max(decided) FROM goal_energy_proposal WHERE user_id=? AND state='approved'",(user,)).fetchone()
    return calibration.cooldown(db,user) or row[0] is not None and time.time()-row[0]<7*86400


def propose(db,user,profile,measurements,report,today):
    body=profile.get('goals',{}).get('body',{});weight=analysis.weight_series(measurements,today)
    if weight['status']!='available' or len(weight['daily_points'])<2:return analysis.unavailable('Servono almeno due giornate di peso per un andamento filtrato recente.')
    point=weight['daily_points'][-1];current=point['filtered_kg'];target=body.get('target_weight_kg');reasoning=[];uncertainty=['7700 kcal/kg è un’approssimazione; la ricalibrazione del lunedì resta il correttore.','Soglie provvisorie della specifica, da verificare in 8.2.']
    if target is None and body.get('target_body_fat_pct') is not None:
        fat=sorted([m for m in measurements if m.get('kind')=='body_fat' and analysis.number(m.get('value')) and 3<=m['value']<=60 and 0<=(today-dt.date.fromisoformat(m['date'])).days<=14],key=lambda m:m['date'])
        grouped={}
        for m in fat:grouped.setdefault(m['date'],[]).append(m['value'])
        if len(grouped)<2:return analysis.unavailable('Servono almeno due giorni di massa grassa per un andamento filtrato, oppure un peso obiettivo.')
        filtered=None
        for values in grouped.values():
            median=statistics.median(values);filtered=median if filtered is None else .5*median+.5*filtered
        target=current*(1-filtered/100)/(1-body['target_body_fat_pct']/100)
        if not 30<=target<=300:return analysis.unavailable('Peso ricavato dalla massa magra fuori dai limiti: verifica l’obiettivo.')
        reasoning.append('Peso suggerito dalla massa magra con EMA delle mediane giornaliere di massa grassa (alpha 0,5, euristica); non viene salvato nel profilo.')
    if target is None:return analysis.unavailable('Manca un peso obiettivo o un obiettivo di massa grassa.')
    direction=-1 if target<current else 1 if target>current else 0;maximum=1 if direction<0 else .5
    pace=body.get('pace');date=body.get('target_date');limits=['absolute_balance_1000','weekly_cooldown_7_days'];pct=None
    if date:
        weeks=(dt.date.fromisoformat(date)-today).days/7
        if weeks<4:return analysis.unavailable('La data obiettivo non è più almeno fra quattro settimane.')
        pct=abs(target-current)/current/weeks*100
    elif pace=='custom':pct=body['pace_pct_per_week']
    elif pace in ('gentle','moderate'):pct={'gentle':(.25,.1),'moderate':(.5,.25)}[pace][0 if direction<0 else 1]
    elif direction:pct=None
    else:pct=0
    if pct is None:return analysis.unavailable('Indica un ritmo o una data obiettivo.')
    if pct>maximum:
        pct=maximum;limits.append('maximum_pace');reasoning.append('La data o il ritmo richiesti superano il massimo: proposta più graduale e data realistica.')
    desired=round(direction*current*pct/100*7700/7/50)*50;desired=max(-1000,min(1000,desired))
    old=profile.get('energy_balance_target_kcal');proposed=desired
    if old is not None:
        target_kcal=profile.get('daily_meals',{}).get('targets',{}).get('kcal_100g',{}).get('target',1800)
        step=math.floor(min(100,.05*target_kcal)/50)*50
        proposed=old+max(-step,min(step,desired-old));limits.append('weekly_change_cap_100_or_5pct_daily_target')
    if cooldown(db,user):return analysis.unavailable('È già stata approvata una variazione negli ultimi sette giorni.')
    effective_pct=abs(proposed)*7/7700/current*100
    expected=(today+dt.timedelta(days=math.ceil(abs(target-current)/abs(proposed)*7700))).isoformat() if direction*proposed>0 else today.isoformat() if not direction else None
    proposal=dict(current_kcal=old,proposed_kcal=proposed,requested_kcal=desired,pace_pct_per_week=pct,effective_pace_pct_per_week=effective_pct,expected_date=expected,reasoning=reasoning+['Bilancio da peso filtrato e ritmo, arrotondato a 50 kcal; i target nutrizionali non cambiano in questo passo.'],uncertainty=uncertainty,limits_applied=limits,weight=dict(value_kg=current,date=point['date'],filter='progress-v2 scalar Kalman',variance_kg2=point['filter_variance_kg2']),target_weight_kg=target)
    state=token(db,user,profile,measurements,report)
    db.execute("UPDATE goal_energy_proposal SET state='superseded' WHERE user_id=? AND state='pending'",(user,))
    identifier=db.execute('INSERT INTO goal_energy_proposal(user_id,created,state,state_token,payload) VALUES(?,?,\'pending\',?,?)',(user,time.time(),state,json.dumps(proposal))).lastrowid
    return dict(status='available',proposal=dict(proposal,id=identifier,state_token=state))


def decide(db,user,profile,measurements,report,identifier,data,action):
    if not isinstance(data,dict) or set(data)!={'state_token'} or not isinstance(data['state_token'],str):raise DomainError('Decisione non valida')
    row=db.execute('SELECT * FROM goal_energy_proposal WHERE id=? AND user_id=?',(identifier,user)).fetchone()
    if not row:raise DomainError('Proposta non trovata','not_found',404)
    if row['state']!='pending' or time.time()-row['created']>=7*86400:raise DomainError('Proposta chiusa o scaduta','proposal_closed',409)
    if data['state_token']!=row['state_token'] or token(db,user,profile,measurements,report)!=row['state_token']:raise DomainError('Stato cambiato: richiedi una nuova proposta','goals_state_changed',409)
    if action=='approve':
        if cooldown(db,user):raise DomainError('Limite settimanale già utilizzato','recalibration_cooldown',409)
        payload=json.loads(row['payload']);numeric(payload['proposed_kcal'],-1000,1000,'Bilancio proposto')
        old=profile.get('energy_balance_target_kcal')
        if old is not None:
            target=profile.get('daily_meals',{}).get('targets',{}).get('kcal_100g',{}).get('target',1800)
            if abs(payload['proposed_kcal']-old)>min(100,.05*target)+1e-8:raise DomainError('Limite di variazione superato','unsafe_proposal',409)
        stored=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user,)).fetchone()[0]);stored['energy_balance_target_kcal']=payload['proposed_kcal']
        db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(stored),user))
    state='approved' if action=='approve' else 'rejected';db.execute('UPDATE goal_energy_proposal SET state=?,decided=? WHERE id=?',(state,time.time(),identifier))
    return dict(id=identifier,status=state,balance_changed=action=='approve')

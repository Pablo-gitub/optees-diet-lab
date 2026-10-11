"""Missing-aware energy comparisons, ordered goals and observation-based estimates."""
import copy
import datetime as dt
import hashlib
import json
import math
import statistics
import time
import uuid
import diary_service as diary
import progress_analysis as analysis
import goal_milestones as contract


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS milestone_sequence(user_id INTEGER PRIMARY KEY,revision INTEGER,payload TEXT);
    CREATE TABLE IF NOT EXISTS milestone_event(id INTEGER PRIMARY KEY,user_id INTEGER,created REAL,payload TEXT);
    CREATE TABLE IF NOT EXISTS energy_snapshot(id INTEGER PRIMARY KEY,user_id INTEGER,week_start TEXT,created REAL,fingerprint TEXT,payload TEXT,UNIQUE(user_id,week_start,fingerprint));
    CREATE TABLE IF NOT EXISTS goal_projection(id INTEGER PRIMARY KEY,user_id INTEGER,created REAL,fingerprint TEXT,payload TEXT,UNIQUE(user_id,fingerprint));
    ''')
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():return
    for owner,raw in db.execute('SELECT id,profile FROM users').fetchall():
        if not db.execute('SELECT 1 FROM milestone_sequence WHERE user_id=?',(owner,)).fetchone():
            value=sequence(db,owner,json.loads(raw))
            if value['items']:db.execute('INSERT INTO milestone_sequence VALUES(?,0,?)',(owner,json.dumps({k:value[k] for k in ('version','items')})))


def sequence(db,user,profile):
    row=db.execute('SELECT * FROM milestone_sequence WHERE user_id=?',(user,)).fetchone()
    if row:return dict(revision=row['revision'],**json.loads(row['payload']))
    body=profile.get('goals',{}).get('body',{});items=[]
    measured=profile.get('_filtered_weight_kg')
    if measured is None and db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='measurement'").fetchone():
        latest=db.execute("SELECT value FROM measurement WHERE user_id=? AND kind='weight' AND unit='kg' ORDER BY date DESC,id DESC LIMIT 1",(user,)).fetchone()
        if latest:measured=latest['value']
    for metric,key in [('weight_kg','target_weight_kg'),('body_fat_pct','target_body_fat_pct')]:
        if body.get(key) is not None:
            current=measured if metric=='weight_kg' else None
            items.append(dict(id='legacy-'+metric,metric=metric,target=body[key],comparison='at_least' if current is not None and body[key]>current else 'at_most',state='pending',desired_date=body.get('target_date'),window_weeks=1))
    return dict(revision=0,version=1,items=items)


def save_sequence(db,user,profile,data):
    previous=sequence(db,user,profile)
    if type(data.get('revision')) is not int or data['revision']!=previous['revision']:raise diary.DomainError('La sequenza è cambiata. Ricaricala prima di salvare.','milestone_conflict',409)
    try:value=contract.validate(dict(version=1,items=data.get('items')))
    except ValueError as e:raise diary.DomainError(str(e))
    old={i['id']:i for i in previous['items']}
    for item in value['items']:
        if item['state']!=old.get(item['id'],{}).get('state','pending'):raise diary.DomainError('Conferma il raggiungimento con l’azione dedicata')
    if any(i['state']!='pending' and i not in value['items'] for i in previous['items']):raise diary.DomainError('Conserva i traguardi conclusi nello storico')
    for item in value['items']:
        if item['id'] in old and old[item['id']]['state']!='pending' and item!=old[item['id']]:raise diary.DomainError('I traguardi conclusi conservano i criteri originali')
    revision=previous['revision']+1
    db.execute('INSERT INTO milestone_sequence VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',(user,revision,json.dumps(value)))
    db.execute('INSERT INTO milestone_event(user_id,created,payload) VALUES(?,?,?)',(user,time.time(),json.dumps(dict(action='edit',before=previous,after=value))))
    return dict(revision=revision,**value)


def evidence(db,user,item,measurements,as_of):
    metric=item['metric'];points=[]
    if metric=='sessions_per_week':
        start=analysis.monday(as_of)-dt.timedelta(weeks=item['window_weeks'])
        counts=[]
        for offset in range(item['window_weeks']):
            begin=start+dt.timedelta(weeks=offset);end=begin+dt.timedelta(days=6)
            count=db.execute("SELECT COUNT(*) FROM workout_log WHERE user_id=? AND status='done' AND date BETWEEN ? AND ?",(user,begin.isoformat(),end.isoformat())).fetchone()[0]
            counts.append(count)
        value=min(counts);reached=value>=item['target'];points=[dict(week_start=(start+dt.timedelta(weeks=n)).isoformat(),sessions=count) for n,count in enumerate(counts)]
    else:
        kind='weight' if metric=='weight_kg' else 'body_fat';unit='kg' if kind=='weight' else '%'
        grouped={}
        for p in measurements:
            if p['kind']==kind and p.get('unit')==unit and analysis.number(p.get('value')) and (as_of-dt.timedelta(days=14)).isoformat()<=p['date']<=as_of.isoformat():grouped.setdefault(p['date'],[]).append(p)
        points=[dict(date=d,value=statistics.median(p['value'] for p in ([p for p in v if p.get('source')=='manual'] or v))) for d,v in sorted(grouped.items())][-3:]
        value=points[-1]['value'] if points else None
        test=lambda v:v<=item['target'] if item['comparison']=='at_most' else v>=item['target']
        reached=len(points)>=3 and all(test(p['value']) for p in points)
    return dict(reached=reached,value=value,points=points,rule='Tre giorni di misura entro 14 giorni' if metric!='sessions_per_week' else 'Ogni settimana completa della finestra deve raggiungere il minimo',token=digest(dict(id=item['id'],points=points,target=item['target'],comparison=item['comparison'])))


def decide(db,user,profile,measurements,as_of,data):
    seq=sequence(db,user,profile)
    if type(data.get('revision')) is not int or data.get('revision')!=seq['revision']:raise diary.DomainError('Sequenza modificata: rivedi il riepilogo','milestone_conflict',409)
    index=next((n for n,i in enumerate(seq['items']) if i['id']==data.get('id') and i['state']=='pending'),None)
    if index is None:raise diary.DomainError('Traguardo non disponibile','not_found',404)
    item=seq['items'][index];proof=evidence(db,user,item,measurements,as_of)
    if proof['token']!=data.get('evidence_token') or not proof['reached']:raise diary.DomainError('Evidenza cambiata o insufficiente: aggiorna i progressi','milestone_conflict',409)
    action=data.get('action')
    if action not in ('complete','skip_previous','keep','later'):raise diary.DomainError('Scelta non valida')
    preceding=[i for i in seq['items'][:index] if i['state']=='pending']
    if action=='complete' and preceding:raise diary.DomainError('Conferma esplicitamente il salto dei traguardi precedenti')
    if action in ('keep','later'):
        db.execute('INSERT INTO milestone_event(user_id,created,payload) VALUES(?,?,?)',(user,time.time(),json.dumps(dict(action=action,id=item['id'],evidence_token=proof['token']))));return seq
    items=copy.deepcopy(seq['items'])
    if action=='skip_previous':
        for prior in items[:index]:
            if prior['state']=='pending':prior['state']='skipped'
    items[index]['state']='achieved';value=dict(version=1,items=items)
    revision=seq['revision']+1
    db.execute('INSERT INTO milestone_sequence VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',(user,revision,json.dumps(value)))
    db.execute('INSERT INTO milestone_event(user_id,created,payload) VALUES(?,?,?)',(user,time.time(),json.dumps(dict(action=action,before=seq,after=value,evidence=proof))))
    return dict(revision=revision,**value)


def projection(item,measurements,as_of):
    if item['metric']!='weight_kg':return dict(status='unavailable',reason='Per questa metrica la data non è ancora stimabile.')
    weight=analysis.weight_series(measurements,as_of);points=weight['daily_points']
    recent=[p for p in points if p['date']>=(as_of-dt.timedelta(days=42)).isoformat()]
    if weight['status']!='available' or len(recent)<6 or (dt.date.fromisoformat(recent[-1]['date'])-dt.date.fromisoformat(recent[0]['date'])).days<21 or any(p['reset'] for p in recent[1:]):return dict(status='unavailable',reason='Servono almeno sei giorni di pesata, distribuiti su 21 giorni, senza lunghe interruzioni e con una misura recente.')
    anchor=dt.date.fromisoformat(recent[0]['date']);xs=[(dt.date.fromisoformat(p['date'])-anchor).days for p in recent];ys=[p['filtered_kg'] for p in recent];mx=statistics.mean(xs);my=statistics.mean(ys);ss=sum((x-mx)**2 for x in xs);slope=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/ss
    error=math.sqrt(sum((y-(my+slope*(x-mx)))**2 for x,y in zip(xs,ys))/(len(xs)-2)/ss)
    distance=item['target']-ys[-1]
    already=ys[-1]<=item['target'] if item['comparison']=='at_most' else ys[-1]>=item['target']
    if already or abs(distance)<.1:return dict(status='unavailable',reason='Valore vicino al traguardo: verifica le misure e conferma il raggiungimento.')
    if distance*slope<=0 or abs(slope)<.003 or abs(slope)<=2*error:return dict(status='unavailable',reason='Andamento piatto, incerto o in direzione opposta al traguardo.')
    delta=abs(distance);fast=abs(slope)+2*error;slow=abs(slope)-2*error
    lower=math.ceil(delta/fast);upper=math.ceil(delta/slow)
    if upper>365 or upper-lower>120:return dict(status='unavailable',reason='La distanza o l’incertezza non sostengono una finestra entro un anno.')
    latest=dt.date.fromisoformat(recent[-1]['date'])
    return dict(status='available',earliest=(latest+dt.timedelta(days=lower)).isoformat(),latest=(latest+dt.timedelta(days=upper)).isoformat(),updated_on=recent[-1]['date'],slope_kg_week=7*slope,days=len(recent),method='filtered-weight-linear-v1',note='Scenario condizionale su peso filtrato, non una previsione fisiologica. La finestra esprime la variabilità della retta osservata, non una garanzia.')


def milestones_view(db,user,profile,measurements,as_of):
    seq=sequence(db,user,profile);active=contract.active_definition({k:seq[k] for k in ('version','items')});rows=[]
    dismissed={}
    for row in db.execute('SELECT payload FROM milestone_event WHERE user_id=? ORDER BY id',(user,)):
        e=json.loads(row['payload'])
        if e.get('action') in ('keep','later'):dismissed[e.get('id')]=e.get('evidence_token')
    for item in seq['items']:
        proof=evidence(db,user,item,measurements,as_of);estimate=projection(item,measurements,as_of) if item['state']=='pending' else dict(status='unavailable',reason='Traguardo concluso.')
        if item['state']=='pending':
            fp=digest(dict(item=item,points=analysis.weight_series(measurements,as_of)['daily_points'],estimate=estimate))
            previous=db.execute('SELECT payload FROM goal_projection WHERE user_id=? AND json_extract(payload,\'$.id\')=? AND fingerprint!=? ORDER BY id DESC LIMIT 1',(user,item['id'],fp)).fetchone()
            db.execute('INSERT OR IGNORE INTO goal_projection(user_id,created,fingerprint,payload) VALUES(?,?,?,?)',(user,time.time(),fp,json.dumps(dict(id=item['id'],estimate=estimate))))
            if previous:estimate=dict(estimate,previous=json.loads(previous['payload'])['estimate'])
        rows.append(dict(**item,evidence=proof,projection=estimate,active=bool(active and item['id']==active['id']),prompt=bool(item['state']=='pending' and proof['reached'] and dismissed.get(item['id'])!=proof['token'])))
    pending=None
    for record in db.execute("SELECT id,state_token,payload FROM goal_energy_proposal WHERE user_id=? AND state='pending' AND created>? ORDER BY id DESC",(user,time.time()-7*86400)):
        candidate=json.loads(record['payload'])
        if candidate.get('milestone')==dict(revision=seq['revision'],definition=active):pending=dict(candidate,id=record['id'],state_token=record['state_token']);break
    return dict(**seq,rows=rows,active=active,balance_proposal=pending)


def solver_adapter(db,user,profile,data,kind):
    seq=sequence(db,user,profile);active=contract.active_definition({k:seq[k] for k in ('version','items')})
    profile['_active_milestone']=dict(revision=seq['revision'],definition=active)
    if active and active['metric']=='sessions_per_week' and kind in ('joint','workout'):
        request=data['workout'] if kind=='joint' else data
        request['sessions_min']=max(request.get('sessions_min',0),active['target'])
        if request.get('sessions_max',7)<request['sessions_min']:raise diary.DomainError('Il massimo di sessioni è inferiore alla milestone attiva. Aumentalo o modifica la sequenza.')
    # Body goals are monitoring criteria: approved nutrition must never be changed implicitly.
    return profile,data


def interval(meal,key):
    range0=meal.get('eaten_range') if key=='eaten' else (meal.get('planned') or {}).get('nutrient_ranges')
    if range0:return range0.get('kcal')
    value=(meal.get(key) or {}).get('kcal')
    return dict(min=value,max=value) if analysis.number(value) else None


def energy_days(db,user,profile,start,report,as_of):
    contexts=analysis.contexts(db,user,start);health={p['date']:p for p in (report or {}).get('daily',[])};result=[]
    for date in analysis.days(start):
        view=diary.day_view(db,user,profile,date);forecast=contexts.get(date,{}).get('progress_forecast',{});planned=[interval(m,'planned') for m in view['meals'] if m['planned']];logged=[m for m in view['meals'] if m['state']!='unknown'];actual=[interval(m,'eaten') for m in view['meals'] if m['state']!='unknown' or m.get('presumed')]
        def summed(values):return dict(min=sum(v['min'] for v in values),max=sum(v['max'] for v in values)) if values and all(v and analysis.number(v.get('min')) and analysis.number(v.get('max')) for v in values) else None
        h=health.get(date,{});full=view['target_scope']=='full_day_planned_meals';complete=full and all(m['state']!='unknown' or m.get('presumed') for m in view['meals']);consumption=forecast.get('energy_scenarios',{})
        expected=consumption.get('consumption_kcal') if forecast.get('valid') and consumption.get('status')=='available' else None
        if expected and any(not analysis.number(expected.get(key)) for key in ('low','central','high')):expected=None
        usable=bool(analysis.number(h.get('total_estimated_kcal')) and h.get('usable_for_baseline') and date<as_of.isoformat());intake=summed(actual) if date<=as_of.isoformat() else None;balance=None
        if complete and usable and intake:balance=dict(min=intake['min']-h['total_estimated_kcal'],max=intake['max']-h['total_estimated_kcal'])
        presumed_slots=view['totals']['coverage'].get('presumed_slots',0) if view.get('totals') and view['totals'].get('coverage') else sum(bool(m.get('presumed')) for m in view['meals'])
        result.append(dict(date=date,scope=view['target_scope'],planned_intake=summed(planned),planned_expenditure=expected,forecast_recorded_at=forecast.get('recorded_at'),forecast_basis=consumption,registered_intake=intake,health_expenditure=h.get('total_estimated_kcal') if h and date<=as_of.isoformat() else None,health_complete=usable,health_coverage=h.get('resting_coverage_fraction'),logged_slots=len(logged),presumed_slots=presumed_slots,diary_complete=complete,balance=balance))
    return result


def capture(db,user,profile,start,reason):
    start=analysis.monday(dt.date.fromisoformat(start)).isoformat()
    values=energy_days(db,user,profile,start,None,diary.local_today())
    if not any(r['planned_intake'] for r in values):return
    payload=dict(days=[{k:r[k] for k in ('date','scope','planned_intake','planned_expenditure','forecast_recorded_at','forecast_basis')} for r in values],milestone=profile.get('_active_milestone'),reason=reason)
    fp=digest({k:v for k,v in payload.items() if k!='reason'})
    db.execute('INSERT OR IGNORE INTO energy_snapshot(user_id,week_start,created,fingerprint,payload) VALUES(?,?,?,?,?)',(user,start,time.time(),fp,json.dumps(payload)))


def energy_view(db,user,profile,start,report,as_of):
    diary.valid_date(start)
    rows=[dict(r) for r in db.execute('SELECT id,created,payload FROM energy_snapshot WHERE user_id=? AND week_start=? ORDER BY id DESC',(user,start))]
    for r in rows:r['payload']=json.loads(r['payload'])
    return dict(week_start=start,as_of=as_of.isoformat(),days=energy_days(db,user,profile,start,report,as_of),versions=rows,health_imported=report is not None,synthetic=bool(report and report.get('version')=='synthetic-demo'))


def goal_profile(profile):
    """Use the first outstanding criterion only when explicitly proposing a balance."""
    personal=copy.deepcopy(profile);active=personal.get('_active_milestone',{}).get('definition')
    if active:
        body=personal.setdefault('goals',{}).setdefault('body',{})
        body.pop('target_weight_kg',None);body.pop('target_body_fat_pct',None);body.pop('target_date',None)
        if active['metric']=='weight_kg':body['target_weight_kg']=active['target']
        elif active['metric']=='body_fat_pct':body['target_body_fat_pct']=active['target']
        if active.get('desired_date'):body['target_date']=active['desired_date']
    return personal

"""Private workout plans and actual logs; public demo templates are never prescriptions."""
import copy
import hashlib
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
from build_workout_catalog import REVIEWED
from workout_sessions import build_sessions
from diary_service import DomainError, integer, valid_date, day_view

ROOT=Path(__file__).resolve().parents[1]


def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS planned_session(id INTEGER PRIMARY KEY,week_plan_id INTEGER,date TEXT,session_id TEXT,minutes REAL,start_time TEXT,status TEXT,snapshot TEXT,UNIQUE(week_plan_id,date));
    CREATE TABLE IF NOT EXISTS workout_log(id INTEGER PRIMARY KEY,user_id INTEGER,date TEXT,planned_session_id INTEGER,session_id TEXT,started TEXT,ended TEXT,rpe REAL,notes TEXT,snapshot TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS workout_planned_once ON workout_log(planned_session_id) WHERE planned_session_id IS NOT NULL;
    CREATE TABLE IF NOT EXISTS set_log(id INTEGER PRIMARY KEY,workout_log_id INTEGER,exercise_id TEXT,set_no INTEGER,reps INTEGER,kg REAL,seconds REAL,rir REAL,UNIQUE(workout_log_id,exercise_id,set_no));
    CREATE INDEX IF NOT EXISTS workout_owner_day ON workout_log(user_id,date);
    CREATE TABLE IF NOT EXISTS workout_configuration(user_id INTEGER PRIMARY KEY,settings TEXT,updated TEXT);
    INSERT OR IGNORE INTO schema_migration VALUES(3,strftime('%s','now'));
    INSERT OR IGNORE INTO schema_migration VALUES(2,strftime('%s','now'));
    ''')


def catalog(profile):
    rows=json.loads((ROOT/'dataset/repdb/raw/exercises.json').read_text())['exercises']
    media=json.loads((ROOT/'config/exercise-media.json').read_text())['exercises']
    index={r['id']:dict(source_id=r['id'],name=r['name_en'],equipment_feasible=True,requirements=REVIEWED[r['id']],primary_muscles=r.get('primary_muscles',[]),secondary_muscles=r.get('secondary_muscles',[]),media=media.get(r['id'])) for r in rows if r['id'] in REVIEWED}
    sessions,unavailable=build_sessions(index)
    for session in sessions:
        session['title']=session['name']
        for exercise in session['exercises']:
            exercise.update(name=index[exercise['source_id']]['name'],exercise_id=exercise['source_id'],media=index[exercise['source_id']]['media'],load_kg=None)
    from workout_configuration import personalize
    public=personalize(dict(model_version='workout-sessions-v2',demo=True,templates=sessions,exercises=list(index.values()),unavailable_sessions=unavailable,protocols=json.loads((ROOT/'config/workout-protocols.json').read_text())['protocols']),profile.get('_workout_settings',{}))
    for template in public['templates']:template['minutes']=display_minutes(template['duration_seconds'])
    return public


def session_by_id(profile,identifier):
    if not isinstance(identifier,str):raise DomainError('Sessione non valida')
    session=next((s for s in catalog(profile)['templates'] if s['id']==identifier),None)
    if session is None:raise DomainError('Sessione non trovata','not_found',404)
    return session


def finite(value,name,low,high,optional=False):
    if value is None and optional:return None
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:raise DomainError(name+' non valido')
    return value


def week_config(data):
    if not isinstance(data,dict):raise DomainError('Corpo della richiesta non valido')
    start=valid_date(data.get('week_start'));dates=[(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat() for i in range(7)]
    availability=data.get('days')
    if not isinstance(availability,dict) or set(availability)!=set(dates):raise DomainError('Indica i minuti disponibili per ciascuno dei sette giorni')
    excluded=data.get('excluded_days',[])
    if not isinstance(excluded,list) or any(not isinstance(d,str) or d not in dates for d in excluded):raise DomainError('Giorni esclusi non validi')
    cfg=json.loads((ROOT/'config/demo-week.json').read_text())
    allowed=set(cfg)-{'days'}|{'goal','allowed_protocols','allow_high_intensity_demo'}
    unknown=set(data)-allowed-{'week_start','days','excluded_days','start_times'}
    if unknown:raise DomainError('Parametri della settimana non riconosciuti')
    cfg.update({k:v for k,v in data.items() if k in allowed})
    cfg['days']={d:0 if d in excluded else finite(availability[d],'Minuti',0,1440) for d in dates}
    # Validate even excluded values, so malformed input is never silently ignored.
    for v in availability.values():finite(v,'Minuti',0,1440)
    for key in ('demo','allow_high_intensity_demo'):
        if key in cfg and not isinstance(cfg[key],bool):raise DomainError('Opzione non valida')
    goals={g for p in json.loads((ROOT/'config/workout-protocols.json').read_text())['protocols'] for g in p['compatible_goals']}
    if cfg.get('goal') is not None and (not isinstance(cfg['goal'],str) or cfg['goal'] not in goals):raise DomainError('Obiettivo non valido')
    protocols={p['id'] for p in json.loads((ROOT/'config/workout-protocols.json').read_text())['protocols']}
    if 'allowed_protocols' in cfg and (not isinstance(cfg['allowed_protocols'],list) or any(not isinstance(p,str) or p not in protocols for p in cfg['allowed_protocols'])):raise DomainError('Protocolli non validi')
    for key in ('sessions_min','sessions_max','strength_sessions_min','strength_sessions_max','strength_gap_days'):integer(cfg[key],0,7)
    finite(cfg['weekly_minutes_max'],'Minuti settimanali',0,10080);finite(cfg['cardio_minutes_min'],'Minuti cardio',0,10080)
    if cfg['sessions_min']>cfg['sessions_max'] or cfg['strength_sessions_min']>cfg['strength_sessions_max']:raise DomainError('Limiti delle sessioni incoerenti')
    targets=cfg['muscle_targets_proxy']
    if not isinstance(targets,dict) or len(targets)>50:raise DomainError('Obiettivi muscolari non validi')
    for key,value in targets.items():
        if not isinstance(key,str):raise DomainError('Obiettivo muscolare non valido')
        finite(value,'Obiettivo muscolare',.01,1000)
    times=data.get('start_times',{})
    if not isinstance(times,dict) or set(times)-set(dates):raise DomainError('Orari non validi')
    for value in times.values():
        try:
            parsed=dt.time.fromisoformat(value)
            if parsed.strftime('%H:%M')!=value:raise ValueError()
        except (ValueError,TypeError):raise DomainError('Orario non valido; usa HH:MM')
    return cfg,times


async def generate_week(session,profile,data,locked_by_date=None):
    from plan_workout_week import formulate
    from plan_diet_day import solve_problem
    from plan_recipe import values_verified
    cfg,times=week_config(data);public=catalog(profile)
    if locked_by_date is not None:cfg['locked_by_date']=locked_by_date
    result=dict(kind='workout',mode=profile['mode'],week_start=data['week_start'],horizon=dict(days=7),demo=True,require_personal_configuration=not cfg['demo'],configuration_hash=configuration_hash(profile),status='ok',plans=[],warnings=[dict(code='workout_demo',message='Tempi e volume dei protocolli sono bozze dimostrative; i carichi sono personali solo se dichiarati.')])
    signatures=set()
    for mode in ('time','coverage'):
        try:problem,slots=formulate(cfg,public,mode)
        except ValueError as exc:
            if str(exc)=='No available slots':
                result.update(status='infeasible',infeasibility=dict(reason='Nessuna sessione compatibile con disponibilità e configurazione.'));return result
            raise DomainError(str(exc))
        solved=await solve_problem(session,problem)
        if solved['mathematical_status'] not in ('optimal','feasible'):continue
        values_verified(problem,solved)
        values={v['name']:v['value'] for v in solved['result']['variables']}
        chosen=[dict(date=d,session_id=t['id'],minutes=display_minutes(t['duration_seconds']),duration_seconds=t['duration_seconds'],start_time=times.get(d),session=copy.deepcopy(t)) for i,(d,t) in enumerate(slots) if values[f's{i}']>.5]
        chosen=[dict(member,date=item['date'],minutes=display_minutes(member['session']['duration_seconds']),duration_seconds=member['session']['duration_seconds'],locked=True) if item['session'].get('locked_observation') else member for item in chosen for member in item['session'].get('locked_members',[item])]
        signature=tuple((s['date'],s['session_id']) for s in chosen)
        if signature in signatures:continue
        signatures.add(signature)
        result['plans'].append(dict(role='best' if not result['plans'] else 'varied',workout_sessions=chosen,weekly_minutes=display_minutes(sum(s['duration_seconds'] for s in chosen)),weekly_duration_seconds=sum(s['duration_seconds'] for s in chosen),constraint_report=dict(verified=True,all_respected=True),explanation=dict(headline='Meno tempo' if mode=='time' else 'Maggiore copertura muscolare stimata',reasons=['Vincoli di disponibilità e recupero verificati'],tradeoffs=[])))
        if solved['mathematical_status']=='feasible':result['status']='partial'
    if not result['plans']:result.update(status='infeasible',infeasibility=dict(reason='Limiti settimanali non soddisfatti; nessun vincolo rilassato.'))
    return result


def planned(db,user,identifier):
    integer(identifier,1,2**63-1)
    row=db.execute("SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE s.id=? AND w.user_id=? AND w.status='active'",(identifier,user)).fetchone()
    if row is None:raise DomainError('Sessione pianificata non trovata','not_found',404)
    return row


def display_minutes(seconds):return int(math.floor(seconds/60+.5))


def configuration_at_start(log,snapshot):
    if log is None:return None
    return dict(source='workout_log_snapshot',recorded_at=log['started'],personal_level=snapshot.get('personal_level'),personal_configuration_complete=snapshot.get('personal_configuration_complete',False),pending_configuration=copy.deepcopy(snapshot.get('pending_configuration',[])))


def day_workouts(db,user,date):
    rows=db.execute("SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? AND s.date=? AND w.status='active' ORDER BY s.id",(user,date)).fetchall()
    logs=db.execute('SELECT * FROM workout_log WHERE user_id=? AND date=? ORDER BY id',(user,date)).fetchall()
    linked={log['planned_session_id']:log for log in logs if log['planned_session_id'] is not None}
    def descriptor(row,log):
        snapshot=json.loads(log['snapshot'] if log else row['snapshot']);first=snapshot['exercises'][0].get('media') or {};image=first.get('illustrative_image') or {}
        seconds=snapshot['duration_seconds']
        return dict(planned_session_id=row['id'] if row else None,session_id=snapshot['id'],title=snapshot['name'],minutes=display_minutes(seconds),duration_seconds=seconds,start_time=row['start_time'] if row else None,status=row['status'] if row else 'done' if log['ended'] else 'in_progress',media=dict(thumbnail=image.get('thumbnail_url')),workout_log_id=log['id'] if log else None,demo=snapshot['demo'],pending_configuration=snapshot['pending_configuration'],configuration_at_start=configuration_at_start(log,snapshot))
    results=[descriptor(row,linked.get(row['id'])) for row in rows]
    included={row['id'] for row in rows}
    results.extend(descriptor(None,log) for log in logs if log['planned_session_id'] not in included)
    return results


def day_workout(db,user,date):
    results=day_workouts(db,user,date)
    return max(results,key=lambda x:(x['workout_log_id'] or 0,x['planned_session_id'] or 0)) if results else None


def apply_week(db,user,profile,plan_set,plan,data):
    import time
    integer(data.get('plan_id'),1,2**63-1)
    if plan_set.get('configuration_hash') and plan_set['configuration_hash']!=configuration_hash(profile):raise DomainError('Configurazione palestra cambiata; rigenera la settimana prima di applicarla','configuration_changed',409)
    if data.get('scope')!='week':raise DomainError('La settimana palestra richiede scope week')
    start=valid_date(plan_set['week_start'])
    row=db.execute("SELECT id FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,start)).fetchone()
    week=row['id'] if row else db.execute("INSERT INTO week_plan(user_id,week_start,mode,status,plan_set_run_id,created,targets) VALUES(?,?,?,'active',?,?,?)",(user,start,profile['mode'],int(plan_set['run_id']),time.time(),json.dumps(profile['targets']))).lastrowid
    skipped=[];applied=[];protected={}
    for offset in range(7):
        date=(dt.date.fromisoformat(start)+dt.timedelta(days=offset)).isoformat()
        rows=db.execute("SELECT s.id,s.status FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? AND s.date=? AND w.status='active'",(user,date)).fetchall()
        if db.execute('SELECT 1 FROM workout_log WHERE user_id=? AND date=?',(user,date)).fetchone() or any(r['status'] in ('in_progress','done','skipped') for r in rows):protected[date]=True;skipped.append(dict(date=date,reason='session_already_logged'));continue
        for r in rows:db.execute('DELETE FROM planned_session WHERE id=?',(r['id'],))
    for item in plan['workout_sessions']:
        date=item['date']
        if date in protected:continue
        db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,minutes,start_time,status,snapshot) VALUES(?,?,?,?,?,'chosen',?)",(week,date,item['session_id'],item['session']['duration_seconds']/60,item['start_time'],json.dumps(item['session'])));applied.append(dict(date=date,session_id=item['session_id']))
    view=day_view(db,user,profile,start);view.update(applied_slots=applied,skipped_slots=skipped);return view


def now():return dt.datetime.now(ZoneInfo('Europe/Rome')).isoformat()


def configuration_hash(profile):
    from workout_configuration import defaults
    return hashlib.sha256(json.dumps(dict(defaults(),**profile.get('_workout_settings',{})),sort_keys=True).encode()).hexdigest()


def own_log(db,user,identifier):
    row=db.execute('SELECT * FROM workout_log WHERE id=? AND user_id=?',(identifier,user)).fetchone()
    if row is None:raise DomainError('Allenamento non trovato','not_found',404)
    return row


def mutation(db,user,profile,action,data,log_id=None):
    if not isinstance(data,dict):raise DomainError('Corpo della richiesta non valido')
    log=own_log(db,user,log_id) if log_id is not None else None
    if action=='start':
        date=valid_date(data.get('date'),True);identifier=data.get('session_id');p=planned(db,user,data['planned_session_id']) if data.get('planned_session_id') is not None else None
        if p and (p['date']!=date or p['session_id']!=identifier):raise DomainError('Sessione e data non corrispondono al piano')
        if p and p['status'] in ('done','skipped'):raise DomainError('Sessione già conclusa','conflict',409)
        snapshot=json.loads(p['snapshot']) if p else session_by_id(profile,identifier)
        if not p and not snapshot['equipment_feasible']:raise DomainError('Attrezzatura o variante non compatibile con la configurazione personale')
        existing=db.execute('SELECT id FROM workout_log WHERE user_id=? AND planned_session_id=?',(user,p['id'])).fetchone() if p else db.execute('SELECT id FROM workout_log WHERE user_id=? AND date=? AND session_id=? AND ended IS NULL AND planned_session_id IS NULL',(user,date,identifier)).fetchone()
        log_id=existing['id'] if existing else db.execute('INSERT INTO workout_log(user_id,date,planned_session_id,session_id,started,snapshot) VALUES(?,?,?,?,?,?)',(user,date,p['id'] if p else None,identifier,now(),json.dumps(snapshot))).lastrowid
        if p:db.execute("UPDATE planned_session SET status='in_progress' WHERE id=?",(p['id'],))
    elif action=='skip':
        p=planned(db,user,data.get('planned_session_id'));date=p['date']
        if p['status'] in ('in_progress','done'):raise DomainError('Allenamento già avviato','conflict',409)
        db.execute("UPDATE planned_session SET status='skipped' WHERE id=?",(p['id'],))
    else:
        date=log['date']
        if action=='sets':
            if log['ended']:raise DomainError('Allenamento già concluso','conflict',409)
            exercise=data.get('exercise_id')
            if not isinstance(exercise,str) or exercise not in {e['source_id'] for e in json.loads(log['snapshot'])['exercises']}:raise DomainError('Esercizio non presente nella sessione')
            series=integer(data.get('set_no'),1,100)
            reps=integer(data['reps'],0,1000) if data.get('reps') is not None else None
            kg=finite(data.get('kg'),'Carico kg',0,1000,True);seconds=finite(data.get('seconds'),'Secondi',0,86400,True);rir=finite(data.get('rir'),'RIR',0,10,True)
            if reps is None and seconds is None:raise DomainError('Indica ripetizioni o secondi eseguiti')
            db.execute('INSERT INTO set_log(workout_log_id,exercise_id,set_no,reps,kg,seconds,rir) VALUES(?,?,?,?,?,?,?) ON CONFLICT(workout_log_id,exercise_id,set_no) DO UPDATE SET reps=excluded.reps,kg=excluded.kg,seconds=excluded.seconds,rir=excluded.rir',(log_id,exercise,series,reps,kg,seconds,rir))
        elif action=='finish':
            rpe=finite(data.get('rpe'),'RPE',0,10,True);notes=data.get('notes')
            if notes is not None and (not isinstance(notes,str) or len(notes)>2000):raise DomainError('Note non valide')
            if not log['ended']:
                db.execute('UPDATE workout_log SET ended=?,rpe=?,notes=? WHERE id=?',(now(),rpe,notes,log_id))
                if log['planned_session_id']:db.execute("UPDATE planned_session SET status='done' WHERE id=?",(log['planned_session_id'],))
    view=day_view(db,user,profile,date)
    if log_id is not None:view['workout_log_id']=log_id
    return view


def read_log(db,user,identifier):
    row=own_log(db,user,identifier);result=dict(row);result['session']=json.loads(result.pop('snapshot'))
    result['configuration_at_start']=configuration_at_start(row,result['session'])
    result['sets']=[dict(r) for r in db.execute('SELECT * FROM set_log WHERE workout_log_id=? ORDER BY exercise_id,set_no',(identifier,))]
    return result


def counts(db,user,start):
    end=(dt.date.fromisoformat(start)+dt.timedelta(days=6)).isoformat()
    planned_count=db.execute("SELECT count(*) FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? AND w.status='active' AND s.date BETWEEN ? AND ?",(user,start,end)).fetchone()[0]
    done=db.execute('SELECT count(*) FROM workout_log WHERE user_id=? AND date BETWEEN ? AND ? AND ended IS NOT NULL',(user,start,end)).fetchone()[0]
    return dict(planned=planned_count,done=done)

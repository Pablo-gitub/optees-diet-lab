"""Feature UCB rewards from declared trials with observable, owner-scoped adherence."""
import hashlib
import json
import math
import time
import diary_service as diary

VERSION='contextual-bandit-v2'
PARAMETERS=dict(version=VERSION,rating_weight=.5,adherence_weight=.5,adherence_components='mean_of_observed_diet_and_planned_training',policy='UCB1',minimum_attempted_components=1)


def context(mode,day_type,targets,scope='full_day_planned_meals'):
    if day_type not in ('rest','training'):raise ValueError('Tipo di giornata non valido')
    return hashlib.sha256(json.dumps(dict(version=VERSION,mode=mode,day_type=day_type,targets=targets,scope=scope),sort_keys=True).encode()).hexdigest()


def migrate(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS plan_feedback(user_id INTEGER,plan_id INTEGER,rating INTEGER,tried_at REAL,PRIMARY KEY(user_id,plan_id));
    CREATE TABLE IF NOT EXISTS bandit_exposure(user_id INTEGER,plan_id INTEGER,date TEXT,context TEXT,arms TEXT,snapshot TEXT,created REAL,PRIMARY KEY(user_id,plan_id,date));
    INSERT OR IGNORE INTO schema_migration VALUES(6,strftime('%s','now'));''')


def record_application(db,user,profile,plan,result):
    """Applying creates provenance, never reward. Only actually applied components count."""
    from day_orchestration import arms
    applied=result.get('applied_slots',[])
    for date in sorted({x['date'] for x in applied}):
        day=next((d for d in plan.get('days',[]) if d['date']==date),plan)
        slots=sorted({x['slot'] for x in applied if x['date']==date and x.get('slot') in diary.SLOTS})
        meals=[]
        for slot in slots:
            row=diary.planned(db,user,date,slot)
            if row:meals.append(dict(slot=slot,id=row['id'],items=json.loads(row['items']),nutrients=diary.totals(diary.enriched(json.loads(row['items']),profile))))
        workout_ids=[]
        for x in applied:
            if x['date']!=date or x.get('slot') in diary.SLOTS:continue
            identifier=x.get('planned_session_id')
            if identifier:workout_ids.append(identifier)
        candidate_sessions=[dict(session=json.loads(r['snapshot']),session_id=r['session_id']) for identifier in workout_ids for r in db.execute('SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE s.id=? AND w.user_id=?',(identifier,user))]
        kind='training' if day.get('day_type')=='training' or candidate_sessions else 'rest'
        targets=day.get('targets') or (profile['daily_meals']['targets'] if profile.get('daily_meals',{}).get('enabled') else profile['targets'])
        scope=day.get('scope') or ('full_day_planned_meals' if profile.get('daily_meals',{}).get('enabled') else 'lunch_and_dinner_only')
        key=day.get('bandit_context') or context(day.get('mode',profile['mode']),kind,targets,scope)
        main=[s for s in day.get('selections',[]) if s['meal'] in slots and s['meal'] in ('lunch','dinner')]
        features=arms(dict(selections=main)) if main else []
        features+=['protocol:'+s['session']['protocol_id'] for s in candidate_sessions if workout_ids]
        snapshot=dict(meals=meals,workout_ids=sorted(set(workout_ids)),day_type=kind,scope=scope,targets=targets,version=VERSION)
        if not features:continue
        db.execute('INSERT INTO bandit_exposure VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,plan_id,date) DO UPDATE SET context=excluded.context,arms=excluded.arms,snapshot=excluded.snapshot,created=excluded.created',(user,plan['id'],date,key,json.dumps(sorted(set(features))),json.dumps(snapshot),time.time()))


def adherence(db,user,profile,row):
    snapshot=json.loads(row['snapshot']);diet=[];training=[];attempted=False
    if row['date']>diary.local_today().isoformat():return None,'Giornata futura: nessuna prova osservabile.'
    for meal in snapshot['meals']:
        current=diary.planned(db,user,row['date'],meal['slot'])
        if not current or current['id']!=meal['id'] or json.loads(current['items'])!=meal['items']:return None,'Piano sostituito dopo l’applicazione.'
        state=diary.state(db,user,row['date'],meal['slot'])
        if state=='unknown':return None,'Diario ancora incompleto.'
        if state=='skipped':diet.append(0.);continue
        if db.execute('SELECT 1 FROM consumed_estimate WHERE user_id=? AND date=? AND slot=?',(user,row['date'],meal['slot'])).fetchone():return None,'Consumati stimati a intervallo: aderenza esatta non disponibile.'
        entries=[dict(r,food=json.loads(r['food'])) for r in db.execute('SELECT * FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,row['date'],meal['slot']))]
        if not entries:return None,'Mancano alimenti consumati.'
        actual=diary.totals(diary.enriched(entries,profile));expected=meal['nutrients']
        if any(actual[k] is None or expected[k] is None for k in diary.KEYS):return None,'Nutrienti mancanti.'
        attempted=True;distance=sum(abs(actual[k]-expected[k])/max(expected[k],1) for k in diary.KEYS)/len(diary.KEYS)
        diet.append(max(0.,1-distance))
    for identifier in snapshot['workout_ids']:
        session=db.execute('SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE s.id=? AND w.user_id=?',(identifier,user)).fetchone()
        if not session or session['date']!=row['date']:return None,'Allenamento sostituito.'
        if session['status']=='skipped':training.append(0.);continue
        done=db.execute("SELECT 1 FROM workout_log WHERE user_id=? AND planned_session_id=? AND date=? AND ended IS NOT NULL",(user,identifier,row['date'])).fetchone()
        if not done or session['status']!='done':return None,'Allenamento non ancora concluso né dichiarato saltato.'
        attempted=True;training.append(1.)
    if not attempted:return None,'Piano non effettivamente provato: tutti i componenti sono saltati.'
    components=[sum(values)/len(values) for values in (diet,training) if values]
    return (sum(components)/len(components),None) if components else (None,'Nessun componente osservabile.')


def trials(db,user,profile,plan_id=None):
    where=' AND e.plan_id=?' if plan_id is not None else ''
    rows=db.execute('SELECT e.*,f.rating,f.tried_at FROM bandit_exposure e JOIN plan_feedback f ON f.user_id=e.user_id AND f.plan_id=e.plan_id WHERE e.user_id=?'+where+' ORDER BY e.date,e.plan_id',(user,plan_id) if plan_id is not None else (user,)).fetchall()
    result=[]
    for row in rows:
        value,reason=adherence(db,user,profile,row)
        rating=(row['rating']-1)/4
        # A pre-application declaration cannot establish a trial of the new application.
        import datetime as dt
        from zoneinfo import ZoneInfo
        if row['tried_at']<row['created'] or dt.datetime.fromtimestamp(row['tried_at'],ZoneInfo('Europe/Rome')).date().isoformat()<row['date']:value=None;reason='Conferma la prova dopo l’applicazione del piano.'
        reward=.5*rating+.5*value if value is not None else None
        result.append(dict(plan_id=row['plan_id'],date=row['date'],context=row['context'],arms=json.loads(row['arms']),rating_normalized=rating,adherence=value,reward=reward,status='eligible' if reward is not None else 'insufficient_data',reason=reason))
    return result


def observations(db,user,profile):
    result={}
    for trial in trials(db,user,profile):
        if trial['reward'] is not None:result.setdefault(trial['context'],[]).extend((a,trial['reward']) for a in trial['arms'])
    return result


def features(plan):
    if plan.get('bandit_features'):return plan['bandit_features']
    return [dict(context=plan.get('bandit_context') or plan.get('optimization',{}).get('context'),arms=plan.get('arms',[]))]


def matched(plan,observed):
    if not isinstance(observed,dict):return list(observed)
    result=[];by_context={}
    for feature in features(plan):by_context.setdefault(feature['context'],set()).update(feature['arms'])
    for key,arms in by_context.items():
        if not key:continue
        for arm,reward in observed.get(key,[]):
            if arm in arms:result.append((key+':'+arm,reward))
    return result


def rewards(plan,observed):
    if isinstance(observed,dict):return [r for _,r in matched(plan,observed)]
    return [r for arm,r in observed if arm in plan.get('arms',[])]


def ucb(plan,observed):
    arms=sorted({(f['context'] or 'unavailable')+':'+a for f in features(plan) for a in f['arms']})
    counts={a:[] for a in arms};total=sum(len(observed.get(key,[])) for key in {f['context'] for f in features(plan)})
    for arm,reward in matched(plan,observed):
        if arm in counts:counts[arm].append(reward)
    score=sum(sum(v)/len(v)+math.sqrt(2*math.log(max(total,1))/len(v)) if v else 0 for v in counts.values())/max(len(counts),1)
    return (sum(not v for v in counts.values()),score,-sum(map(len,counts.values())))


def day_evaluation(db,user,date):
    """Expose current applied provenance and existing votes; reading never learns."""
    refs=[];stale=False
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='plans'").fetchone():
        return dict(status='unavailable',reason='Nessun piano applicato con riferimento valutabile.',plans=[])
    rows=db.execute('''SELECT e.*,p.payload AS plan_payload,f.rating,f.tried_at
        FROM bandit_exposure e JOIN plans p ON p.id=e.plan_id AND p.user_id=e.user_id
        LEFT JOIN plan_feedback f ON f.user_id=e.user_id AND f.plan_id=e.plan_id
        WHERE e.user_id=? AND e.date=? ORDER BY e.created DESC,e.plan_id DESC''',(user,date)).fetchall()
    for row in rows:
        snapshot=json.loads(row['snapshot'])
        if json.loads(row['plan_payload']).get('status') not in ('optimal','feasible'):continue
        current=True
        for meal in snapshot['meals']:
            planned=diary.planned(db,user,date,meal['slot'])
            if not planned or planned['id']!=meal['id'] or json.loads(planned['items'])!=meal['items']:
                current=False;break
        for identifier in snapshot['workout_ids']:
            if not db.execute('SELECT 1 FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE s.id=? AND w.user_id=? AND s.date=? AND w.status=?',(identifier,user,date,'active')).fetchone():current=False;break
        if not current:stale=True;continue
        future=date>diary.local_today().isoformat()
        refs.append(dict(plan_id=row['plan_id'],rating=row['rating'],rated_at=row['tried_at'],
                         slots=[m['slot'] for m in snapshot['meals']],workout_ids=snapshot['workout_ids'],scope=snapshot['scope'],
                         feedback_endpoint='/api/plans/'+str(row['plan_id'])+'/feedback',feedback_available=not future,
                         reason='Giornata futura: chiedi il voto dopo la prova.' if future else None,
                         rating_scope='plan',applied_at=row['created']))
    status='available' if len(refs)==1 else 'multiple' if refs else 'unavailable'
    reason='Più piani applicati: valuta il riferimento dei componenti provati.' if len(refs)>1 else None if refs else 'Piano sostituito dopo l’applicazione.' if stale else 'Nessun piano applicato con riferimento valutabile.'
    return dict(status=status,reason=reason,plans=refs)

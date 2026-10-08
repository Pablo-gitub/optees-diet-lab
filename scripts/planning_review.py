"""Owner-scoped review of a candidate and atomic application receipts."""
import datetime as dt
import hashlib
import json
from diary_service import DomainError, valid_date, day_view, SLOTS


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS plan_application(user_id INTEGER,set_id INTEGER,review_token TEXT,result TEXT,PRIMARY KEY(user_id,set_id,review_token))')


def state(db,user,start):
    end=(dt.date.fromisoformat(valid_date(start))+dt.timedelta(days=6)).isoformat()
    queries={
        'milestones':('SELECT * FROM milestone_sequence WHERE user_id=?',(user,)),
        'profile':('SELECT profile FROM users WHERE id=?',(user,)),
        'configuration':('SELECT * FROM workout_configuration WHERE user_id=?',(user,)),
        'weeks':("SELECT * FROM week_plan WHERE user_id=? AND status='active' AND week_start BETWEEN ? AND ? ORDER BY id",(user,(dt.date.fromisoformat(start)-dt.timedelta(days=6)).isoformat(),end)),
        'meals':("SELECT m.* FROM planned_meal m JOIN week_plan w ON w.id=m.week_plan_id WHERE w.user_id=? AND w.status='active' AND m.date BETWEEN ? AND ? ORDER BY m.id",(user,start,end)),
        'entries':('SELECT * FROM diary_entry WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY id',(user,start,end)),
        'logs':('SELECT * FROM meal_log WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date,slot',(user,start,end)),
        'estimates':('SELECT * FROM consumed_estimate WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date,slot',(user,start,end)),
        'sessions':("SELECT s.* FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? AND w.status='active' AND s.date BETWEEN ? AND ? ORDER BY s.id",(user,start,end)),
        'workouts':('SELECT * FROM workout_log WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY id',(user,start,end)),
        'sets':('SELECT s.* FROM set_log s JOIN workout_log l ON l.id=s.workout_log_id WHERE l.user_id=? AND l.date BETWEEN ? AND ? ORDER BY s.workout_log_id,s.exercise_id,s.set_no',(user,start,end)),
        'dishes':('SELECT * FROM locked_dish WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date,slot',(user,start,end)),
        'measurements':('SELECT * FROM measurement WHERE user_id=? ORDER BY id',(user,)),
        'votes':('SELECT * FROM meal_match_vote WHERE user_id=? ORDER BY match_id',(user,)),
        'preferences':('SELECT * FROM recipe_preference WHERE user_id=? ORDER BY recipe_id',(user,)),
    }
    return digest({key:[dict(r) for r in db.execute(sql,args)] for key,(sql,args) in queries.items()})


def review(db,user,profile,plan_set,plan,data):
    scope=data.get('scope');start=plan_set.get('week_start') or data.get('date')
    valid_date(start)
    if scope not in ('week','day','meal'):raise DomainError('Ambito non valido')
    if plan_set.get('kind') in ('joint','workout') and scope!='week':raise DomainError('Questo piano richiede l’intera settimana')
    dates=[(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat() for i in range(7)] if scope=='week' else [valid_date(data.get('date'))]
    if scope=='meal' and data.get('slot') not in SLOTS:raise DomainError('Pasto non valido')
    if plan_set.get('slot') and (scope!='meal' or data.get('date')!=plan_set.get('date') or data.get('slot')!=plan_set['slot']):raise DomainError('Alternativa riferita a un altro pasto')
    if scope=='week' and plan_set.get('kind')!='workout' and len(plan.get('days',[]))!=7:raise DomainError('Piano non settimanale')
    current=state(db,user,start)
    if plan_set.get('review_state') and current!=plan_set['review_state']:
        raise DomainError('Piano, registrazioni o impostazioni sono cambiati dopo il calcolo. Genera una nuova bozza.','planning_state_changed',409)
    meals=[];protected=[];sessions=[];protected_sessions=[]
    for date in dates:
        view=day_view(db,user,profile,date)
        day=next((d for d in plan.get('days',[]) if d.get('date')==date),None) if 'days' in plan else plan
        if plan_set.get('kind')!='workout':
            if day is None:raise DomainError('Giornata non trovata nel piano')
            for meal in view['meals']:
                slot=meal['slot']
                if scope=='meal' and slot!=data['slot']:continue
                locked=meal['planned'] and meal['planned']['locked']
                logged=meal['state']!='unknown' or meal['eaten'] is not None
                if locked or logged:
                    protected.append(dict(date=date,slot=slot,reason='slot_locked' if locked else 'slot_already_logged'));continue
                selections=[s for s in day.get('selections',[]) if s['meal']==slot]
                if selections:meals.append(dict(date=date,slot=slot,action='replace' if meal['planned'] else 'add',foods=[s.get('food',s.get('food_id','')) for s in selections]))
        if plan_set.get('kind') in ('joint','workout'):
            existing=view['workouts']
            has_log=db.execute('SELECT 1 FROM workout_log WHERE user_id=? AND date=?',(user,date)).fetchone()
            if has_log or any(w['status'] in ('done','in_progress','skipped') for w in existing):
                protected_sessions.append(dict(date=date,reason='session_already_logged'));continue
            new=[s for s in plan.get('workout_sessions',[]) if s['date']==date]
            if existing or new:sessions.append(dict(date=date,action='replace' if existing else 'add',before=len(existing),after=len(new),titles=[s.get('session',{}).get('title') or s.get('session',{}).get('name') or s['session_id'] for s in new]))
    token=digest(dict(state=current,plan=plan,set_id=plan_set['run_id'],scope=scope,dates=dates,slot=data.get('slot')))
    return dict(review_token=token,kind=plan_set.get('kind','week' if scope=='week' else 'day'),scope=scope,week_start=start,meals=meals,protected_meals=protected,sessions=sessions,protected_sessions=protected_sessions,profile_changed=False)

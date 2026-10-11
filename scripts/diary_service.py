import copy
"""Owner-scoped planned meals, consumed meals and manual measurements."""
import datetime as dt
import json
import math
import re
import sqlite3
import time
import unicodedata
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
from plan_diet_day import load_foods,NUTRIENTS
from daily_meals import products

ROOT=Path(__file__).resolve().parents[1]
SLOTS=('breakfast','morning_snack','lunch','afternoon_snack','dinner')
KEYS=[n.replace('_100g','') for n in NUTRIENTS]

class DomainError(ValueError):
    def __init__(self,message,code='invalid_input',status=400):super().__init__(message);self.code=code;self.status=status

def migrate(db):
    import meal_drafts
    meal_drafts.migrate(db)
    import planning_review
    planning_review.migrate(db)
    import progress_dashboard
    progress_dashboard.migrate(db)
    import personal_goals
    personal_goals.migrate(db)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS schema_migration(version INTEGER PRIMARY KEY,applied REAL);
    CREATE TABLE IF NOT EXISTS week_plan(id INTEGER PRIMARY KEY,user_id INTEGER,week_start TEXT,mode TEXT,status TEXT,plan_set_run_id INTEGER,created REAL,targets TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS active_week_owner ON week_plan(user_id,week_start) WHERE status='active';
    CREATE TABLE IF NOT EXISTS planned_meal(id INTEGER PRIMARY KEY,week_plan_id INTEGER,date TEXT,slot TEXT,items TEXT,role TEXT,status TEXT,locked INTEGER DEFAULT 0,UNIQUE(week_plan_id,date,slot));
    CREATE TABLE IF NOT EXISTS food_usage(user_id INTEGER,source TEXT,food_id TEXT,PRIMARY KEY(user_id,source,food_id));
    CREATE TABLE IF NOT EXISTS diary_entry(id INTEGER PRIMARY KEY,user_id INTEGER,date TEXT,slot TEXT,food TEXT,grams INTEGER,units INTEGER,origin TEXT,planned_meal_id INTEGER,created REAL,updated REAL);
    CREATE TABLE IF NOT EXISTS meal_log(user_id INTEGER,date TEXT,slot TEXT,state TEXT,updated REAL,PRIMARY KEY(user_id,date,slot));
    CREATE TABLE IF NOT EXISTS measurement(id INTEGER PRIMARY KEY,user_id INTEGER,date TEXT,kind TEXT,value REAL,unit TEXT,source TEXT);
    CREATE TABLE IF NOT EXISTS job(id TEXT PRIMARY KEY,user_id INTEGER,kind TEXT,state TEXT,progress REAL,result_ref INTEGER,error TEXT,created REAL);
    CREATE INDEX IF NOT EXISTS diary_owner_day ON diary_entry(user_id,date,slot);
    INSERT OR IGNORE INTO schema_migration VALUES(1,strftime('%s','now'));
    ''')

    for owner,raw in db.execute('SELECT user_id,food FROM diary_entry'):
        ref=json.loads(raw);db.execute('INSERT OR IGNORE INTO food_usage VALUES(?,?,?)',(owner,ref['source'],ref['id']))
    columns={r[1] for r in db.execute('PRAGMA table_info(planned_meal)')}
    if 'day_index' not in columns:db.execute('ALTER TABLE planned_meal ADD COLUMN day_index INTEGER DEFAULT 0')
    if 'day_context' not in {r[1] for r in db.execute('PRAGMA table_info(week_plan)')}:db.execute("ALTER TABLE week_plan ADD COLUMN day_context TEXT DEFAULT '{}'")
    from contextual_bandit import migrate as bandit_migrate
    bandit_migrate(db)
    from meal_rebalance import migrate as rebalance_migrate
    rebalance_migrate(db)
    from workout_service import migrate as workout_migrate
    workout_migrate(db)
    from recipe_intents import migrate as intent_migrate
    intent_migrate(db)

def local_today():
    return dt.datetime.now(ZoneInfo('Europe/Rome')).date()


def valid_date(value,consumed=False):
    try:
        day=dt.date.fromisoformat(value)
        if value!=day.isoformat():raise ValueError()
    except (ValueError,TypeError):raise DomainError('Data non valida')
    if consumed and day>local_today()+dt.timedelta(days=1):raise DomainError('Non puoi registrare oltre domani')
    return value

def valid_slot(slot):
    if slot not in SLOTS:raise DomainError('Pasto non valido')
    return slot

def integer(value,low,high):
    if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:raise DomainError('Quantità non valida')
    return value

def fold(value):return ''.join(c for c in unicodedata.normalize('NFKD',str(value)).casefold() if not unicodedata.combining(c))

@lru_cache(maxsize=1)
def crea():return load_foods()

def numeric(value):
    try:
        value=float(value)
        return value if math.isfinite(value) and value>=0 else None
    except (ValueError,TypeError):return None

def resolve_food(ref,profile):
    if not isinstance(ref,dict) or set(ref)!= {'source','id'} or not isinstance(ref['id'],str):raise DomainError('Riferimento alimento non valido')
    source,identifier=ref['source'],ref['id'];unit=None;brand=None;recipe=None
    if source=='CREA':
        row=crea().get(identifier)
        if not row or identifier.startswith('recipe:'):raise DomainError('Alimento non trovato')
    elif source=='OFF':
        with sqlite3.connect(ROOT/'dataset/open_food_facts/catalog.sqlite') as db:
            found=db.execute('SELECT payload FROM products WHERE barcode=?',(identifier,)).fetchone()
        if not found:raise DomainError('Alimento non trovato')
        row=json.loads(found[0]);brand=row.get('brands')
        # Volume-only or unresolved labels cannot be multiplied by grams.
        if row.get('nutrient_basis')!='per_100_g':row=dict(row,**{n:None for n in NUTRIENTS})
    elif source=='user_label':
        row=products(profile.get('food_preferences',{})).get(identifier)
        if not row:raise DomainError('Etichetta personale non trovata')
        unit=row['serving_g'];brand=row.get('brand')
    elif source=='dish_estimate':
        dish=profile.get('_dish_estimates',{}).get(identifier)
        if not dish:raise DomainError('Piatto stimato non trovato')
        from recipe_intents import display_title
        row=dict(name=display_title(dish),**{n:sum(dish['nutrients'][n.replace('_100g','')].values())/2 for n in NUTRIENTS})
        return dict(food=ref,name=row['name'],brand=None,source_label='stima a intervallo',unit_g=None,composition_provenance=None,nutrient_ranges=copy.deepcopy(dish['nutrients']),per_100g={n.replace('_100g',''):row[n] for n in NUTRIENTS})
    elif source=='recipe':
        if identifier=='vegetable_puree':row=crea()['recipe:vegetable_puree']
        else:
            recipe=profile.get('_recipe_runs',{}).get(identifier)
            if not recipe or recipe.get('status') not in ('optimal','feasible'):raise DomainError('Porzione di ricetta non trovata')
            unit=recipe.get('unit_g')
            mass=sum(s['grams'] for s in recipe['selections'])
            if mass<=0:raise DomainError('Porzione di ricetta non valida')
            row=dict(name=recipe['title'],**{n:numeric(recipe['nutrients'].get('carbs_g' if n=='carbs_available_g_100g' else n.replace('_100g','')))*100/mass if numeric(recipe['nutrients'].get('carbs_g' if n=='carbs_available_g_100g' else n.replace('_100g',''))) is not None else None for n in NUTRIENTS})
    else:raise DomainError('Alimento non trovato')
    return dict(food=ref,name=row['name'],brand=brand,source_label='database italiano generico' if source=='CREA' else 'marca' if source=='OFF' else 'etichetta personale' if source=='user_label' else 'ricetta',per_100g={n.replace('_100g',''):numeric(row.get(n)) for n in NUTRIENTS},fiber_g_100g=numeric(row.get('fiber_g_100g')),unit_g=unit,recipe_id=recipe.get('recipe_id') if recipe else None,principal_food_id=recipe.get('principal_food_id') if recipe else None,composition_provenance=row.get('composition_provenance'))

def quantity(data,food):
    grams=data.get('grams');units=data.get('units')
    if units is not None:
        integer(units,1,20)
        if not food['unit_g']:raise DomainError('Peso della porzione non disponibile')
        computed=units*food['unit_g']
        if computed!=int(computed):raise DomainError('Porzione non esprimibile in grammi interi')
        if grams is not None and grams!=computed:raise DomainError('Grammi e unità non corrispondono')
        grams=int(computed)
    integer(grams,1,3000)
    return grams,units

def enriched(items,profile):
    result=[]
    for item in items:
        food=resolve_food(item['food'],profile);grams=item['grams']
        result.append(dict(item,name=food['name'],source_label=food['source_label'],**{key:None if value is None else round(value*grams/100,3) for key,value in food['per_100g'].items()}))
    return result

def totals(items):return {key:None if any(item.get(key) is None for item in items) else round(sum(item[key] for item in items),3) for key in KEYS}

def planned(db,user,date,slot):return db.execute("SELECT p.* FROM planned_meal p JOIN week_plan w ON w.id=p.week_plan_id WHERE w.user_id=? AND w.status='active' AND p.date=? AND p.slot=?",(user,date,slot)).fetchone()

def state(db,user,date,slot):
    row=db.execute('SELECT state FROM meal_log WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone();return row['state'] if row else 'unknown'

def set_state(db,user,date,slot,new):
    db.execute('INSERT INTO meal_log VALUES(?,?,?,?,?) ON CONFLICT(user_id,date,slot) DO UPDATE SET state=excluded.state,updated=excluded.updated',(user,date,slot,new,time.time()))
    p=planned(db,user,date,slot)
    if p:db.execute('UPDATE planned_meal SET status=? WHERE id=?',('chosen' if new=='unknown' else 'skipped' if new=='skipped' else 'done',p['id']))

def is_presumed(db,user,date,slot,p=None,as_of=None):
    ref=as_of.isoformat() if isinstance(as_of,dt.date) else as_of if isinstance(as_of,str) else local_today().isoformat()
    if date>=ref:return False
    if state(db,user,date,slot)!='unknown':return False
    if p is None:p=planned(db,user,date,slot)
    if not p:return False
    if db.execute('SELECT 1 FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone():return False
    if db.execute('SELECT 1 FROM consumed_estimate WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone():return False
    if db.execute("SELECT 1 FROM meal_draft WHERE user_id=? AND date=? AND slot=? AND status='draft'",(user,date,slot)).fetchone():return False
    return True

def day_view(db,user,profile,date,include_presumed=True,as_of=None):
    valid_date(date);meals=[];all_planned=[];all_eaten=[];logged=0;planned_count=0
    week=db.execute("SELECT * FROM week_plan WHERE user_id=? AND status='active' AND week_start<=? AND date(week_start,'+6 days')>=?",(user,date,date)).fetchone()
    for slot in SLOTS:
        p=planned(db,user,date,slot);st=state(db,user,date,slot);entries=db.execute('SELECT id,food,grams,units,origin FROM diary_entry WHERE user_id=? AND date=? AND slot=? ORDER BY id',(user,date,slot)).fetchall()
        planned_items=enriched(json.loads(p['items']),profile) if p else [];eaten_items=enriched([dict(r,food=json.loads(r['food'])) for r in entries],profile)
        if p:planned_count+=1;all_planned.extend(planned_items)
        has_draft=bool(db.execute("SELECT 1 FROM meal_draft WHERE user_id=? AND date=? AND slot=? AND status='draft'",(user,date,slot)).fetchone())
        estimated=db.execute('SELECT payload FROM consumed_estimate WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone()
        consumed=json.loads(estimated['payload']) if estimated else None
        ref=as_of.isoformat() if isinstance(as_of,dt.date) else as_of if isinstance(as_of,str) else local_today().isoformat()
        presumed=bool(date<ref and p and st=='unknown' and not entries and not has_draft and not consumed)
        if st!='unknown':logged+=bool(p);all_eaten.extend(eaten_items)
        elif presumed and include_presumed:all_eaten.extend(planned_items)
        actions=['edit','reset'] if st!='unknown' else ['edit','skip']+(['confirm','alternatives'] if p and not p['locked'] else ['confirm'] if p else [])
        eaten_val=(dict(items=planned_items,**totals(planned_items)) if include_presumed else None) if presumed else (dict(items=eaten_items,**totals(eaten_items)) if st!='unknown' else None)
        meals.append(dict(consumed_estimate=consumed,eaten_range=consumed['nutrients'] if consumed else None,slot=slot,state=st,presumed=presumed,planned=dict(planned_meal_id=p['id'],role=p['role'],day_index=p['day_index'],status=p['status'],locked=bool(p['locked']),items=planned_items,**totals(planned_items)) if p else None,eaten=eaten_val,actions=actions))
    import meal_drafts
    for meal in meals:
        meal['revision']=meal_drafts.fingerprint(db,user,date,meal['slot'],profile)
        if meal['planned']:
            ranges={k:dict(min=0.,max=0.) for k in KEYS};uncertain=False
            for item in meal['planned']['items']:
                food=resolve_food(item['food'],profile);estimate=food.get('nutrient_ranges');uncertain|=bool(estimate)
                for k in KEYS:
                    for side in ('min','max'):
                        value=estimate[k][side]*item['grams']/100 if estimate else item.get(k)
                        ranges[k][side]=None if value is None or ranges[k][side] is None else ranges[k][side]+value
            meal['planned']['nutrient_ranges']=ranges if uncertain else None
            meal['planned']['nutrition_basis']='interval_midpoint' if uncertain else 'verified_food_values'
        if meal['consumed_estimate'] and meal['eaten'] is not None:meal['eaten'].update({key:None for key in KEYS})
    targets=json.loads(week['targets']) if week else (profile.get('daily_meals',{}).get('targets') if profile.get('daily_meals',{}).get('enabled') else profile['targets'])
    context=json.loads(week['day_context'] or '{}').get(date,{}) if week else {}
    targets=context.get('targets',targets)
    any_logged=any(m['state']!='unknown' or (include_presumed and m['presumed']) for m in meals)
    from workout_service import day_workouts
    workouts=day_workouts(db,user,date)
    workout=max(workouts,key=lambda x:(x["workout_log_id"] or 0,x["planned_session_id"] or 0)) if workouts else None
    eaten_totals=totals(all_eaten) if any_logged else None
    if eaten_totals is not None and any(m['consumed_estimate'] for m in meals):eaten_totals.update({key:None for key in KEYS})
    from contextual_bandit import day_evaluation
    evaluation=day_evaluation(db,user,date)
    single=evaluation['plans'][0] if len(evaluation['plans'])==1 else None
    presumed_slots=sum(bool(m['presumed']) for m in meals)
    return dict(target_scope=context.get('scope') or ('full_day_planned_meals' if not week and profile.get('daily_meals',{}).get('enabled') else 'main_meals' if not week else 'unspecified_plan'),meal_timing=context.get('meal_timing'),plan_id=single['plan_id'] if single else None,rating=single['rating'] if single else None,plan_evaluation=evaluation,date=date,day_type='training' if any(w['status']!='skipped' for w in workouts) else context.get('day_type','unknown'),mode=context.get('mode',week['mode']) if week else profile['mode'],week_plan_id=week['id'] if week else None,targets={k.replace('_100g',''):v for k,v in targets.items()},totals=dict(planned=totals(all_planned) if planned_count else None,eaten=eaten_totals,coverage=dict(logged_slots=logged,presumed_slots=presumed_slots,planned_slots=planned_count)),meals=meals,workout=workout,workouts=workouts,warnings=[])

def diary_mutation(db,user,profile,action,data,entry_id=None):
    entry=None
    if entry_id is not None:
        entry=db.execute('SELECT * FROM diary_entry WHERE id=? AND user_id=?',(entry_id,user)).fetchone()
        if not entry:raise DomainError('Voce non trovata','not_found',404)
        date,slot=entry['date'],entry['slot']
    else:date,slot=data.get('date'),data.get('slot')
    valid_date(date,True);valid_slot(slot);p=planned(db,user,date,slot);st=state(db,user,date,slot)
    interval_row=db.execute('SELECT payload FROM consumed_estimate WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone()
    if action in ('confirm','skip','reset') and 'revision' in data:
        import meal_drafts
        unchanged_action=(action=='confirm' and st=='as_planned') or (action=='skip' and st=='skipped') or (action=='reset' and st=='unknown')
        if not unchanged_action and data['revision']!=meal_drafts.fingerprint(db,user,date,slot,profile):raise DomainError('Il pasto è cambiato: ricarica la giornata prima di riprovare.','meal_conflict',409)
    if action=='confirm' and st=='as_planned' and interval_row and json.loads(interval_row['payload']).get('provenance',{}).get('registration')=='planned_dish_estimate':return day_view(db,user,profile,date)
    if db.execute('SELECT 1 FROM consumed_estimate WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone() and action not in ('skip','reset'):raise DomainError('Questo pasto ha una stima a intervallo: azzera prima di modificarlo','estimated_slot',409)
    if action=='confirm':
        if not p:raise DomainError('Pasto pianificato non trovato','not_found',404)
        if st=='as_planned':return day_view(db,user,profile,date)
        if st!='unknown':raise DomainError('Pasto già registrato','slot_already_logged',409)
        estimates=[profile.get('_dish_estimates',{}).get(item['food']['id']) for item in json.loads(p['items']) if item['food']['source']=='dish_estimate']
        if estimates:
            meal=next(m for m in day_view(db,user,profile,date)['meals'] if m['slot']==slot)
            if not meal['planned'].get('nutrient_ranges'):raise DomainError('Intervallo del piatto non disponibile')
            payload=dict(date=date,slot=slot,nutrients=meal['planned']['nutrient_ranges'],provenance=dict(estimates[0]['provenance'],registration='planned_dish_estimate'))
            db.execute('INSERT INTO consumed_estimate VALUES(?,?,?,?,?)',(user,date,slot,json.dumps(payload),time.time()));set_state(db,user,date,slot,'as_planned')
            from progress_analysis import invalidate_forecast
            invalidate_forecast(db,user,date,'consumed_interval_estimate')
            return day_view(db,user,profile,date)
        for item in json.loads(p['items']):
            food=resolve_food(item['food'],profile);grams,units=quantity(item,food)
            db.execute('INSERT INTO diary_entry(user_id,date,slot,food,grams,units,origin,planned_meal_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(user,date,slot,json.dumps(item['food']),grams,units,'planned',p['id'],time.time(),time.time()))
        set_state(db,user,date,slot,'as_planned')
    elif action in ('skip','reset'):
        db.execute('DELETE FROM consumed_estimate WHERE user_id=? AND date=? AND slot=?',(user,date,slot))
        db.execute('DELETE FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,date,slot));set_state(db,user,date,slot,'skipped' if action=='skip' else 'unknown')
    elif action=='add':
        ref=data.get('food');food=resolve_food(ref,profile)
        if food.get('nutrient_ranges'):raise DomainError('Una stima a intervallo si registra confermando il piatto pianificato, non aggiungendo grammi fittizi','interval_food_unsupported')
        grams,units=quantity(data,food)
        db.execute('INSERT INTO diary_entry(user_id,date,slot,food,grams,units,origin,planned_meal_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(user,date,slot,json.dumps(ref),grams,units,'added',p['id'] if p else None,time.time(),time.time()));set_state(db,user,date,slot,'modified' if p else 'unplanned')
    elif action=='edit':
        food=resolve_food(json.loads(entry['food']),profile);values=dict(data)
        if food.get('nutrient_ranges'):raise DomainError('Una stima a intervallo non si modifica come alimento pesato','interval_food_unsupported')
        if 'grams' not in values and 'units' not in values:raise DomainError('Quantità mancante')
        grams,units=quantity(values,food)
        db.execute('UPDATE diary_entry SET grams=?,units=?,updated=? WHERE id=? AND user_id=?',(grams,units,time.time(),entry_id,user));set_state(db,user,date,slot,'modified' if p else 'unplanned')
    elif action=='delete':
        db.execute('DELETE FROM diary_entry WHERE id=? AND user_id=?',(entry_id,user));set_state(db,user,date,slot,'modified' if p else 'unplanned')
    if action in ('confirm','add'):
        for row in db.execute('SELECT food FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,date,slot)):
            ref=json.loads(row['food']);db.execute('INSERT OR IGNORE INTO food_usage VALUES(?,?,?)',(user,ref['source'],ref['id']))
    return day_view(db,user,profile,date)

def week_view(db,user,profile,start):
    valid_date(start);views=[day_view(db,user,profile,(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat()) for i in range(7)]
    def sum_known(values):return None if any(x is None for x in values) else round(sum(values),3)
    planned_values=[v['totals']['planned']['kcal'] if v['totals']['planned'] else None for v in views]
    eaten_values=[v['totals']['eaten']['kcal'] for v in views if v['totals']['eaten'] is not None]
    remaining=[m['planned']['kcal'] for v in views for m in v['meals'] if m['planned'] and m['state']=='unknown' and not m.get('presumed')]
    days=[dict(date=v['date'],day_type=v['day_type'],meals=[dict(slot=m['slot'],state=m['state']) for m in v['meals']],workout=v['workout']['status'] if v['workout'] else None,kcal_planned=planned_values[i],kcal_eaten=v['totals']['eaten']['kcal'] if v['totals']['eaten'] else None,coverage=v['totals']['coverage']['logged_slots']/v['totals']['coverage']['planned_slots'] if v['totals']['coverage']['planned_slots'] else None) for i,v in enumerate(views)]
    week=db.execute("SELECT * FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,start)).fetchone()
    from workout_service import counts as workout_counts
    return dict(week_start=start,plan_status=week['status'] if week else None,plan_set_run_id=week['plan_set_run_id'] if week else None,calendar=[dict(date=v['date'],target_scope=v['target_scope'],meals=[dict(slot=m['slot'],state=m['state'],locked=bool(m['planned'] and m['planned']['locked']),foods=[i['name'] for i in (m['planned'] or {}).get('items',[])],kcal=(m['planned'] or {}).get('kcal'),estimate=bool(m.get('consumed_estimate'))) for m in v['meals']],workouts=v['workouts']) for v in views],days=days,budget=dict(kcal_target=sum(v['targets']['kcal']['target'] for v in views),kcal_planned=sum_known(planned_values),kcal_eaten=sum_known(eaten_values) if eaten_values else None,kcal_remaining_planned=sum_known(remaining) if week else None,complete_days=sum(v['totals']['coverage']['planned_slots']>0 and v['totals']['coverage']['logged_slots']==v['totals']['coverage']['planned_slots'] for v in views)),workouts=workout_counts(db,user,start))

def apply_plan(db,user,profile,plan_set,plan,data):
    from recipe_intents import persist_snapshots
    scope=data.get('scope')
    if isinstance(data.get('plan_id'),bool) or not isinstance(data.get('plan_id'),int):raise DomainError('Identificativo piano non valido')
    if plan_set.get('slot') and (scope!='meal' or data.get('date')!=plan_set.get('date') or data.get('slot')!=plan_set['slot']):raise DomainError('Alternativa riferita a un altro pasto')
    start=plan_set.get('week_start',data.get('date'));valid_date(start)
    if scope not in ('week','day','meal'):raise DomainError('Ambito non valido')
    persist_snapshots(db,user,profile,plan)
    dates=[(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat() for i in range(7)] if scope=='week' else [valid_date(data.get('date'))]
    if scope=='meal':valid_slot(data.get('slot'))
    if scope=='week' and len(plan.get('days',[]))!=7:raise DomainError('Piano non settimanale')
    if plan_set.get('week_start') and any(not plan_set['week_start']<=d<=(dt.date.fromisoformat(plan_set['week_start'])+dt.timedelta(days=6)).isoformat() for d in dates):raise DomainError('Data esterna al piano')
    week_start=plan_set.get('week_start') or (dt.date.fromisoformat(dates[0])-dt.timedelta(days=dt.date.fromisoformat(dates[0]).weekday())).isoformat()
    week=db.execute("SELECT * FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,week_start)).fetchone()
    if not week:
        targets=plan.get('targets') or (profile.get('daily_meals',{}).get('targets') if profile.get('daily_meals',{}).get('enabled') else profile['targets'])
        id=db.execute('INSERT INTO week_plan(user_id,week_start,mode,status,plan_set_run_id,created,targets) VALUES(?,?,?,?,?,?,?)',(user,week_start,plan_set['mode'],'active',int(plan_set['run_id']),time.time(),json.dumps(targets))).lastrowid
    else:id=week['id']
    skipped=[];applied=[]
    for date in dates:
        day=next((d for d in plan.get('days',[]) if d['date']==date),None) if 'days' in plan else plan
        if day is None:raise DomainError('Giornata non trovata nel piano')
        for slot in SLOTS:
            if scope=='meal' and slot!=data['slot']:continue
            p=planned(db,user,date,slot)
            if state(db,user,date,slot)!='unknown' or db.execute('SELECT 1 FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone() or (p and p['locked']) or (scope!='meal' and is_presumed(db,user,date,slot,p)):
                skipped.append(dict(date=date,slot=slot,reason='slot_locked' if p and p['locked'] else 'slot_already_logged'));continue
            selections=[s for s in day['selections'] if s['meal']==slot]
            if not selections:continue
            items=[]
            for s in selections:
                source=s.get('source','CREA');identifier=s.get('reference_id') or s['food_id']
                if identifier.startswith('personal:'):source='user_label';identifier=identifier.split(':',1)[1]
                elif identifier.startswith('recipe:'):source='recipe';identifier=identifier.split(':',1)[1]
                item=dict(food=dict(source=source,id=identifier),grams=s['grams'],units=s.get('units'))
                quantity(item,resolve_food(item['food'],profile));items.append(item)
            db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status,locked,day_index) VALUES(?,?,?,?,?,'chosen',?,?) ON CONFLICT(week_plan_id,date,slot) DO UPDATE SET items=excluded.items,role=excluded.role,status='chosen',day_index=excluded.day_index,locked=excluded.locked",(id,date,slot,json.dumps(items),plan.get('role','best'),int(slot in day.get('locked_slots',[])),day.get('day_index',0)));applied.append(dict(date=date,slot=slot))
    if plan_set.get('kind')!='joint':
        from progress_analysis import invalidate_forecast
        for date in {item['date'] for item in applied}:invalidate_forecast(db,user,date)
    if scope=='week' and 'targets_by_date' in plan:
        context=json.loads(week['day_context'] or '{}') if week else {}
        for day in plan['days']:
            date=day['date']
            if any(item['date']==date for item in skipped):
                context.setdefault(date,dict(targets=json.loads(week['targets']) if week else targets,mode=week['mode'] if week else plan_set['mode'],scope='unspecified_plan'))
                context[date]['partial_application']=True
                if context[date].get('progress_forecast'):context[date]['progress_forecast'].update(valid=False,reason='partial_plan_application')
                if context[date].get('meal_timing'):context[date]['meal_timing'].update(status='unavailable',reason='Piano applicato solo in parte: distribuzione da ricalcolare.')
                continue
            context[date]=dict(targets=day['targets'],mode=day['mode'],day_type=day.get('day_type','unknown'),scope=day.get('scope'),meal_timing=copy.deepcopy(day.get('meal_timing')))
            if context[date]['meal_timing'] and any(item['date']==date for item in skipped):context[date]['meal_timing'].update(status='unavailable',reason='Alcuni pasti erano già registrati: distribuzione applicata solo in parte.')
            if plan_set.get('kind')=='joint' and not any(item['date']==date for item in skipped):
                context[date]['progress_forecast']=dict(valid=True,scope=day.get('scope'),energy_scenarios=day.get('energy_scenarios',{}),planned_kcal=day['nutrients']['kcal'],plan_id=plan.get('id'),energy_balance_target_kcal=plan_set.get('energy_balance_target_kcal'),recorded_at=time.time())
        db.execute('UPDATE week_plan SET day_context=? WHERE id=?',(json.dumps(context),id))
    if scope=='day' and plan.get('meal_timing') and not skipped:
        row=db.execute('SELECT day_context FROM week_plan WHERE id=?',(id,)).fetchone();context=json.loads(row['day_context'] or '{}')
        context.setdefault(dates[0],{})['meal_timing']=copy.deepcopy(plan['meal_timing'])
        db.execute('UPDATE week_plan SET day_context=? WHERE id=?',(json.dumps(context),id))
    if scope=='week' and applied:
        db.execute('UPDATE week_plan SET mode=?,plan_set_run_id=? WHERE id=?',(plan_set.get('mode',week['mode'] if week else profile['mode']),int(plan_set['run_id']) if plan_set.get('run_id') is not None else (week['plan_set_run_id'] if week else None),id))
    result=day_view(db,user,profile,dates[0]);result.update(skipped_slots=skipped,applied_slots=applied);return result

def search_foods(db,user,profile,q,limit):
    if not isinstance(q,str) or not 1<=len(q.strip())<=100:raise DomainError('Ricerca non valida')
    integer(limit,1,50);needle=fold(q.strip());found=[]
    aliases={'mela':'mele','uovo':'uova','patata':'patate','pomodoro':'pomodori','pera':'pere','banana':'banane','zucchina':'zucchine','carota':'carote'}
    aliases.update({v:k for k,v in list(aliases.items())})
    needles=[needle]+([aliases[needle]] if needle in aliases else [])
    def matches(name):return any(term in fold(name) for term in needles)
    for identifier,row in products(profile.get('food_preferences',{})).items():
        if matches(row['name']):found.append(resolve_food(dict(source='user_label',id=identifier),profile))
    used=db.execute('SELECT DISTINCT food FROM diary_entry WHERE user_id=? ORDER BY updated DESC LIMIT 100',(user,)).fetchall()
    for row in used:
        try:food=resolve_food(json.loads(row['food']),profile)
        except DomainError:continue
        if matches(food['name']):found.append(food)
    with sqlite3.connect(ROOT/'dataset/open_food_facts/catalog.sqlite') as off:
        off.create_function('fold',1,fold)
        conditions=" OR ".join("fold(name || ' ' || brands) LIKE ? ESCAPE '\\'" for _ in needles)
        patterns=['%'+term.replace('%','\\%').replace('_','\\_')+'%' for term in needles]
        rows=off.execute('SELECT barcode FROM products WHERE '+conditions+' ORDER BY barcode LIMIT 500',patterns).fetchall()
    for row in rows:found.append(resolve_food(dict(source='OFF',id=row[0]),profile))
    for identifier,row in crea().items():
        if not identifier.startswith('recipe:') and matches(row['name']):found.append(resolve_food(dict(source='CREA',id=identifier),profile))
    seen=set();result=[]
    for item in found:
        key=(item['food']['source'],item['food']['id'])
        if key not in seen:seen.add(key);result.append(item)
    def ranking(item):
        name=fold(item['name']);tokens=re.findall(r'\w+',name);words=needle.split()
        generic_exact=item['food']['source']=='CREA' and len(words)==1 and name.split(',')[0].strip() in needles
        relevance=0 if name in needles or generic_exact else 1 if any(all(w in tokens for w in term.split()) for term in needles) else 2 if any(name.startswith(term) for term in needles) else 3
        complete=all(v is not None for v in item['per_100g'].values())
        source_priority={'user_label':0,'CREA':1,'OFF':2,'recipe':3}
        fresh_priority=0 if generic_exact and any(word in tokens for word in ('fresche','crude','fresco','crudo')) else 1
        return relevance,not complete,source_priority[item['food']['source']],fresh_priority,name,item['food']['id']
    return sorted(result,key=ranking)[:limit]

def validate_measurement(data):
    date=valid_date(data.get('date'),True);kind=data.get('kind');unit=data.get('unit');value=data.get('value')
    definitions={'weight':('kg',1,500),'waist':('cm',10,300),**{k:('cm',10,300) for k in ('hip','chest','arm','thigh')},'height':('cm',30,250),'body_fat':('%',0,100)}
    if kind not in definitions:raise DomainError('Misura non supportata')
    expected,low,high=definitions[kind]
    if unit!=expected or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:raise DomainError('Valore o unità della misura non validi')
    return date,kind,unit,value

def add_measurement(db,user,data):
    date,kind,unit,value=validate_measurement(data)
    db.execute('INSERT INTO measurement(user_id,date,kind,value,unit,source) VALUES(?,?,?,?,?,?)',(user,date,kind,value,unit,'manual'))
    return date

def pending_presumed(db,user,profile,as_of=None):
    ref_date=as_of if isinstance(as_of,dt.date) else dt.date.fromisoformat(as_of) if isinstance(as_of,str) else local_today()
    from_date=ref_date-dt.timedelta(days=7);to_date=ref_date-dt.timedelta(days=1)
    days=[];total_count=0;current=to_date
    while current>=from_date:
        d_str=current.isoformat();v=day_view(db,user,profile,d_str,as_of=ref_date)
        presumed_meals=[m for m in v['meals'] if m.get('presumed')]
        if presumed_meals:
            meals_data=[]
            for m in presumed_meals:
                total_count+=1
                meals_data.append(dict(slot=m['slot'],kcal=m['planned']['kcal'],items=[dict(name=i['name'],grams=i['grams']) for i in m['planned']['items']]))
            days.append(dict(date=d_str,meals=meals_data))
        current-=dt.timedelta(days=1)
    return dict(**{'from':from_date.isoformat(),'to':to_date.isoformat()},count=total_count,days=days)

def confirm_all_presumed(db,user,profile,data):
    if not isinstance(data,dict) or 'meals' not in data or not isinstance(data['meals'],list):
        raise DomainError('Formato richiesta non valido',status=422)
    today=local_today();from_date=today-dt.timedelta(days=7);to_date=today-dt.timedelta(days=1)
    unique_meals=[];seen=set()
    for item in data['meals']:
        if not isinstance(item,dict) or 'date' not in item or 'slot' not in item:
            raise DomainError('Pasto non valido',status=422)
        d_str,slot=item['date'],item['slot']
        if not isinstance(d_str,str) or not isinstance(slot,str):
            raise DomainError('Pasto non valido',status=422)
        try:
            d_val=dt.date.fromisoformat(d_str)
            if d_str!=d_val.isoformat():raise ValueError()
        except (ValueError,TypeError):
            raise DomainError('Data non valida',status=422)
        if slot not in SLOTS:
            raise DomainError('Slot non valido',status=422)
        if d_val<from_date or d_val>to_date:
            raise DomainError('Data fuori finestra consentita',status=422)
        key=(d_str,slot)
        if key not in seen:
            seen.add(key)
            unique_meals.append((d_str,slot))
    confirmed=[];skipped=[]
    for d_str,slot in unique_meals:
        if is_presumed(db,user,d_str,slot):
            diary_mutation(db,user,profile,'confirm',dict(date=d_str,slot=slot))
            confirmed.append(dict(date=d_str,slot=slot))
        else:
            if state(db,user,d_str,slot)!='unknown':
                reason='already_logged'
            else:
                reason='not_presumed'
            skipped.append(dict(date=d_str,slot=slot,reason=reason))
    return dict(confirmed=confirmed,skipped=skipped,pending=pending_presumed(db,user,profile))

"""Owner-scoped planned meals, consumed meals and manual measurements."""
import datetime as dt
import json
import math
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
    db.executescript('''
    CREATE TABLE IF NOT EXISTS schema_migration(version INTEGER PRIMARY KEY,applied REAL);
    CREATE TABLE IF NOT EXISTS week_plan(id INTEGER PRIMARY KEY,user_id INTEGER,week_start TEXT,mode TEXT,status TEXT,plan_set_run_id INTEGER,created REAL,targets TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS active_week_owner ON week_plan(user_id,week_start) WHERE status='active';
    CREATE TABLE IF NOT EXISTS planned_meal(id INTEGER PRIMARY KEY,week_plan_id INTEGER,date TEXT,slot TEXT,items TEXT,role TEXT,status TEXT,locked INTEGER DEFAULT 0,UNIQUE(week_plan_id,date,slot));
    CREATE TABLE IF NOT EXISTS diary_entry(id INTEGER PRIMARY KEY,user_id INTEGER,date TEXT,slot TEXT,food TEXT,grams INTEGER,units INTEGER,origin TEXT,planned_meal_id INTEGER,created REAL,updated REAL);
    CREATE TABLE IF NOT EXISTS meal_log(user_id INTEGER,date TEXT,slot TEXT,state TEXT,updated REAL,PRIMARY KEY(user_id,date,slot));
    CREATE TABLE IF NOT EXISTS measurement(id INTEGER PRIMARY KEY,user_id INTEGER,date TEXT,kind TEXT,value REAL,unit TEXT,source TEXT);
    CREATE TABLE IF NOT EXISTS job(id TEXT PRIMARY KEY,user_id INTEGER,kind TEXT,state TEXT,progress REAL,result_ref INTEGER,error TEXT,created REAL);
    CREATE INDEX IF NOT EXISTS diary_owner_day ON diary_entry(user_id,date,slot);
    INSERT OR IGNORE INTO schema_migration VALUES(1,strftime('%s','now'));
    ''')

    columns={r[1] for r in db.execute('PRAGMA table_info(planned_meal)')}
    if 'day_index' not in columns:db.execute('ALTER TABLE planned_meal ADD COLUMN day_index INTEGER DEFAULT 0')

def local_today():return dt.datetime.now(ZoneInfo('Europe/Rome')).date()

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
    source,identifier=ref['source'],ref['id'];unit=None;brand=None
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
        unit=row['serving_g']
    elif source=='recipe':
        if identifier=='vegetable_puree':row=crea()['recipe:vegetable_puree']
        else:
            recipe=profile.get('_recipe_runs',{}).get(identifier)
            if not recipe or recipe.get('status') not in ('optimal','feasible'):raise DomainError('Porzione di ricetta non trovata')
            mass=sum(s['grams'] for s in recipe['selections'])
            if mass<=0:raise DomainError('Porzione di ricetta non valida')
            row=dict(name=recipe['title'],**{n:numeric(recipe['nutrients'].get('carbs_g' if n=='carbs_available_g_100g' else n.replace('_100g','')))*100/mass if numeric(recipe['nutrients'].get('carbs_g' if n=='carbs_available_g_100g' else n.replace('_100g',''))) is not None else None for n in NUTRIENTS})
    else:raise DomainError('Alimento non trovato')
    return dict(food=ref,name=row['name'],brand=brand,source_label='database italiano generico' if source=='CREA' else 'marca' if source=='OFF' else 'etichetta personale' if source=='user_label' else 'ricetta',per_100g={n.replace('_100g',''):numeric(row.get(n)) for n in NUTRIENTS},unit_g=unit,composition_provenance=row.get('composition_provenance'))

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

def day_view(db,user,profile,date):
    valid_date(date);meals=[];all_planned=[];all_eaten=[];logged=0;planned_count=0
    week=db.execute("SELECT * FROM week_plan WHERE user_id=? AND status='active' AND week_start<=? AND date(week_start,'+6 days')>=?",(user,date,date)).fetchone()
    for slot in SLOTS:
        p=planned(db,user,date,slot);st=state(db,user,date,slot);entries=db.execute('SELECT id,food,grams,units,origin FROM diary_entry WHERE user_id=? AND date=? AND slot=? ORDER BY id',(user,date,slot)).fetchall()
        planned_items=enriched(json.loads(p['items']),profile) if p else [];eaten_items=enriched([dict(r,food=json.loads(r['food'])) for r in entries],profile)
        if p:planned_count+=1;all_planned.extend(planned_items)
        if st!='unknown':logged+=bool(p);all_eaten.extend(eaten_items)
        actions=['edit','reset'] if st!='unknown' else ['edit','skip']+(['confirm','alternatives'] if p and not p['locked'] else ['confirm'] if p else [])
        meals.append(dict(slot=slot,state=st,planned=dict(planned_meal_id=p['id'],role=p['role'],day_index=p['day_index'],status=p['status'],locked=bool(p['locked']),items=planned_items,**totals(planned_items)) if p else None,eaten=dict(items=eaten_items,**totals(eaten_items)) if st!='unknown' else None,actions=actions))
    targets=json.loads(week['targets']) if week else (profile.get('daily_meals',{}).get('targets') if profile.get('daily_meals',{}).get('enabled') else profile['targets'])
    any_logged=any(m['state']!='unknown' for m in meals)
    return dict(date=date,day_type='unknown',mode=week['mode'] if week else profile['mode'],week_plan_id=week['id'] if week else None,targets={k.replace('_100g',''):v for k,v in targets.items()},totals=dict(planned=totals(all_planned) if planned_count else None,eaten=totals(all_eaten) if any_logged else None,coverage=dict(logged_slots=logged,planned_slots=planned_count)),meals=meals,workout=None,warnings=[])

def diary_mutation(db,user,profile,action,data,entry_id=None):
    entry=None
    if entry_id is not None:
        entry=db.execute('SELECT * FROM diary_entry WHERE id=? AND user_id=?',(entry_id,user)).fetchone()
        if not entry:raise DomainError('Voce non trovata','not_found',404)
        date,slot=entry['date'],entry['slot']
    else:date,slot=data.get('date'),data.get('slot')
    valid_date(date,True);valid_slot(slot);p=planned(db,user,date,slot);st=state(db,user,date,slot)
    if action=='confirm':
        if not p:raise DomainError('Pasto pianificato non trovato','not_found',404)
        if st=='as_planned':return day_view(db,user,profile,date)
        if st!='unknown':raise DomainError('Pasto già registrato','slot_already_logged',409)
        for item in json.loads(p['items']):
            food=resolve_food(item['food'],profile);grams,units=quantity(item,food)
            db.execute('INSERT INTO diary_entry(user_id,date,slot,food,grams,units,origin,planned_meal_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(user,date,slot,json.dumps(item['food']),grams,units,'planned',p['id'],time.time(),time.time()))
        set_state(db,user,date,slot,'as_planned')
    elif action in ('skip','reset'):
        db.execute('DELETE FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,date,slot));set_state(db,user,date,slot,'skipped' if action=='skip' else 'unknown')
    elif action=='add':
        ref=data.get('food');food=resolve_food(ref,profile);grams,units=quantity(data,food)
        db.execute('INSERT INTO diary_entry(user_id,date,slot,food,grams,units,origin,planned_meal_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(user,date,slot,json.dumps(ref),grams,units,'added',p['id'] if p else None,time.time(),time.time()));set_state(db,user,date,slot,'modified' if p else 'unplanned')
    elif action=='edit':
        food=resolve_food(json.loads(entry['food']),profile);values=dict(data)
        if 'grams' not in values and 'units' not in values:raise DomainError('Quantità mancante')
        grams,units=quantity(values,food)
        db.execute('UPDATE diary_entry SET grams=?,units=?,updated=? WHERE id=? AND user_id=?',(grams,units,time.time(),entry_id,user));set_state(db,user,date,slot,'modified' if p else 'unplanned')
    elif action=='delete':
        db.execute('DELETE FROM diary_entry WHERE id=? AND user_id=?',(entry_id,user));set_state(db,user,date,slot,'modified' if p else 'unplanned')
    return day_view(db,user,profile,date)

def week_view(db,user,profile,start):
    valid_date(start);views=[day_view(db,user,profile,(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat()) for i in range(7)]
    def sum_known(values):return None if any(x is None for x in values) else round(sum(values),3)
    planned_values=[v['totals']['planned']['kcal'] if v['totals']['planned'] else None for v in views]
    eaten_values=[v['totals']['eaten']['kcal'] for v in views if v['totals']['eaten'] is not None]
    remaining=[m['planned']['kcal'] for v in views for m in v['meals'] if m['planned'] and m['state']=='unknown']
    days=[dict(date=v['date'],day_type=v['day_type'],meals=[dict(slot=m['slot'],state=m['state']) for m in v['meals']],workout=None,kcal_planned=planned_values[i],kcal_eaten=v['totals']['eaten']['kcal'] if v['totals']['eaten'] else None,coverage=v['totals']['coverage']['logged_slots']/v['totals']['coverage']['planned_slots'] if v['totals']['coverage']['planned_slots'] else None) for i,v in enumerate(views)]
    week=db.execute("SELECT * FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,start)).fetchone()
    return dict(week_start=start,plan_status=week['status'] if week else None,days=days,budget=dict(kcal_target=sum(v['targets']['kcal']['target'] for v in views),kcal_planned=sum_known(planned_values),kcal_eaten=sum_known(eaten_values) if eaten_values else None,kcal_remaining_planned=sum_known(remaining) if week else None,complete_days=sum(v['totals']['coverage']['planned_slots']>0 and v['totals']['coverage']['logged_slots']==v['totals']['coverage']['planned_slots'] for v in views)),workouts=dict(planned=0,done=0))

def apply_plan(db,user,profile,plan_set,plan,data):
    scope=data.get('scope')
    if isinstance(data.get('plan_id'),bool) or not isinstance(data.get('plan_id'),int):raise DomainError('Identificativo piano non valido')
    if plan_set.get('slot') and (scope!='meal' or data.get('date')!=plan_set.get('date') or data.get('slot')!=plan_set['slot']):raise DomainError('Alternativa riferita a un altro pasto')
    start=plan_set.get('week_start',data.get('date'));valid_date(start)
    if scope not in ('week','day','meal'):raise DomainError('Ambito non valido')
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
            if state(db,user,date,slot)!='unknown' or db.execute('SELECT 1 FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone() or p and p['locked']:
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
            db.execute("INSERT INTO planned_meal(week_plan_id,date,slot,items,role,status,locked,day_index) VALUES(?,?,?,?,?,'chosen',?,?) ON CONFLICT(week_plan_id,date,slot) DO UPDATE SET items=excluded.items,role=excluded.role,status='chosen',day_index=excluded.day_index",(id,date,slot,json.dumps(items),plan.get('role','best'),int(slot in day.get('locked_slots',[])),day.get('day_index',0)));applied.append(dict(date=date,slot=slot))
    result=day_view(db,user,profile,dates[0]);result.update(skipped_slots=skipped,applied_slots=applied);return result

def search_foods(db,user,profile,q,limit):
    if not isinstance(q,str) or not 1<=len(q)<=100:raise DomainError('Ricerca non valida')
    integer(limit,1,50);needle=fold(q);found=[]
    for identifier,row in products(profile.get('food_preferences',{})).items():
        if needle in fold(row['name']):found.append(resolve_food(dict(source='user_label',id=identifier),profile))
    used=db.execute('SELECT DISTINCT food FROM diary_entry WHERE user_id=? ORDER BY updated DESC LIMIT 100',(user,)).fetchall()
    for row in used:
        try:food=resolve_food(json.loads(row['food']),profile)
        except DomainError:continue
        if needle in fold(food['name']):found.append(food)
    with sqlite3.connect(ROOT/'dataset/open_food_facts/catalog.sqlite') as off:
        off.create_function('fold',1,fold)
        rows=off.execute("SELECT barcode FROM products WHERE fold(name || ' ' || brands) LIKE ? ESCAPE '\\' ORDER BY barcode LIMIT ?",('%'+needle.replace('%','\\%').replace('_','\\_')+'%',500)).fetchall()
    for row in rows:found.append(resolve_food(dict(source='OFF',id=row[0]),profile))
    for identifier,row in crea().items():
        if not identifier.startswith('recipe:') and needle in fold(row['name']):found.append(resolve_food(dict(source='CREA',id=identifier),profile))
    seen=set();result=[]
    for item in found:
        key=(item['food']['source'],item['food']['id'])
        if key not in seen:seen.add(key);result.append(item)
    def ranking(item):
        name=fold(item['name']);tokens=name.split();words=needle.split()
        relevance=0 if name==needle else 1 if all(w in tokens for w in words) else 2 if name.startswith(needle) else 3
        complete=all(v is not None for v in item['per_100g'].values())
        source_priority={'user_label':0,'CREA':1,'OFF':2,'recipe':3}
        return relevance,not complete,source_priority[item['food']['source']],name,item['food']['id']
    return sorted(result,key=ranking)[:limit]

def add_measurement(db,user,data):
    date=valid_date(data.get('date'),True);kind=data.get('kind');unit=data.get('unit');value=data.get('value')
    definitions={'weight':('kg',1,500),'waist':('cm',10,300),'height':('cm',30,250),'body_fat':('%',0,100)}
    if kind not in definitions:raise DomainError('Misura non supportata')
    expected,low,high=definitions[kind]
    if unit!=expected or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:raise DomainError('Valore o unità della misura non validi')
    db.execute('INSERT INTO measurement(user_id,date,kind,value,unit,source) VALUES(?,?,?,?,?,?)',(user,date,kind,value,unit,'manual'))
    return date

"""Account-owned meal drafts with an atomic, optimistic diary replacement."""
import hashlib
import json
import time
import diary_service as diary


def migrate(db):
    db.execute('''CREATE TABLE IF NOT EXISTS meal_draft(user_id INTEGER,date TEXT,slot TEXT,revision INTEGER,
        baseline TEXT,items TEXT,status TEXT,updated REAL,PRIMARY KEY(user_id,date,slot))''')


def fingerprint(db,user,date,slot,profile):
    planned=diary.planned(db,user,date,slot)
    entries=[dict(r) for r in db.execute('SELECT * FROM diary_entry WHERE user_id=? AND date=? AND slot=? ORDER BY id',(user,date,slot))]
    estimate=db.execute('SELECT payload FROM consumed_estimate WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone()
    refs=[json.loads(r['food']) for r in entries]+[i['food'] for i in json.loads(planned['items'])] if planned else [json.loads(r['food']) for r in entries]
    values=dict(planned=dict(planned) if planned else None,entries=entries,state=diary.state(db,user,date,slot),estimate=estimate['payload'] if estimate else None,
                foods=[diary.resolve_food(ref,profile) for ref in refs])
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def validate_items(items,profile,allow_empty=True):
    if not isinstance(items,list) or len(items)>100 or (not allow_empty and not items):
        raise diary.DomainError('Aggiungi almeno un alimento; per saltare il pasto usa “Salta”.')
    result=[]
    for item in items:
        if not isinstance(item,dict) or set(item)-{'food','grams','units'}:raise diary.DomainError('Alimento della bozza non valido')
        food=diary.resolve_food(item.get('food'),profile)
        if food.get('nutrient_ranges'):raise diary.DomainError('Una stima a intervallo non si modifica come alimento pesato','interval_food_unsupported')
        grams,units=diary.quantity(item,food)
        result.append(dict(food=item['food'],grams=grams,units=units))
    return result


def view(db,user,profile,row):
    return dict(date=row['date'],slot=row['slot'],revision=row['revision'],status=row['status'],
                stale=row['baseline']!=fingerprint(db,user,row['date'],row['slot'],profile),
                items=diary.enriched(json.loads(row['items']),profile))


def get(db,user,profile,date,slot):
    diary.valid_date(date,True);diary.valid_slot(slot)
    row=db.execute('SELECT * FROM meal_draft WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone()
    if row and row['status']=='draft':return view(db,user,profile,row)
    meal=next(m for m in diary.day_view(db,user,profile,date)['meals'] if m['slot']==slot)
    if meal['consumed_estimate']:raise diary.DomainError('Annulla prima la registrazione a intervallo per inserire alimenti pesati','estimated_slot',409)
    source=meal['eaten'] or meal['planned'] or dict(items=[])
    items=validate_items([{k:i[k] for k in ('food','grams','units') if k in i} for i in source['items']],profile)
    revision=row['revision']+1 if row else 0
    db.execute('INSERT OR REPLACE INTO meal_draft VALUES(?,?,?,?,?,?,?,?)',(user,date,slot,revision,fingerprint(db,user,date,slot,profile),json.dumps(items),'draft',time.time()))
    return view(db,user,profile,db.execute('SELECT * FROM meal_draft WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone())


def change(db,user,profile,data,action):
    if action not in ('save','commit','discard'):raise diary.DomainError('Azione bozza non valida')
    if not isinstance(data,dict) or set(data)-{'date','slot','revision','items'}:raise diary.DomainError('Bozza non valida')
    date,slot=data.get('date'),data.get('slot');diary.valid_date(date,True);diary.valid_slot(slot)
    row=db.execute('SELECT * FROM meal_draft WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone()
    if not row or type(data.get('revision')) is not int or data['revision']!=row['revision']:
        raise diary.DomainError('La bozza è cambiata in un’altra sessione. Le modifiche restano visibili.','draft_conflict',409)
    if action=='commit' and row['status']=='saved':
        if validate_items(data.get('items'),profile,allow_empty=False)!=json.loads(row['items']):raise diary.DomainError('La bozza risulta già salvata con quantità diverse. Apri una nuova bozza per correggere il pasto.','draft_conflict',409)
        return diary.day_view(db,user,profile,date)
    if action=='discard' and row['status']=='discarded':return diary.day_view(db,user,profile,date)
    if row['status']!='draft':raise diary.DomainError('Bozza già chiusa','draft_conflict',409)
    if action=='discard':
        db.execute("UPDATE meal_draft SET status='discarded' WHERE user_id=? AND date=? AND slot=?",(user,date,slot))
        return diary.day_view(db,user,profile,date)
    items=validate_items(data.get('items'),profile,allow_empty=action=='save')
    if action=='save':
        db.execute('UPDATE meal_draft SET items=?,revision=revision+1,updated=? WHERE user_id=? AND date=? AND slot=?',(json.dumps(items),time.time(),user,date,slot))
        return view(db,user,profile,db.execute('SELECT * FROM meal_draft WHERE user_id=? AND date=? AND slot=?',(user,date,slot)).fetchone())
    if row['baseline']!=fingerprint(db,user,date,slot,profile):raise diary.DomainError('Pasto o piano cambiati: la bozza è conservata. Rivedi il diario prima di sostituirlo.','meal_conflict',409)
    # Validate everything before deleting; the surrounding transaction rolls back every write on error.
    planned=diary.planned(db,user,date,slot)
    db.execute('DELETE FROM diary_entry WHERE user_id=? AND date=? AND slot=?',(user,date,slot))
    db.execute('DELETE FROM consumed_estimate WHERE user_id=? AND date=? AND slot=?',(user,date,slot))
    for item in items:
        db.execute('INSERT INTO diary_entry(user_id,date,slot,food,grams,units,origin,planned_meal_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',
          (user,date,slot,json.dumps(item['food']),item['grams'],item['units'],'edited',planned['id'] if planned else None,time.time(),time.time()))
        db.execute('INSERT OR IGNORE INTO food_usage VALUES(?,?,?)',(user,item['food']['source'],item['food']['id']))
    diary.set_state(db,user,date,slot,'modified' if planned else 'unplanned')
    db.execute("UPDATE meal_draft SET items=?,status='saved',updated=? WHERE user_id=? AND date=? AND slot=?",(json.dumps(items),time.time(),user,date,slot))
    return diary.day_view(db,user,profile,date)

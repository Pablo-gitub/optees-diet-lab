"""Owner-scoped Optees meal cards and explicit preference context, not trial rewards."""
import copy
import datetime as dt
import hashlib
import itertools
import json
import math
import sqlite3
import time
from pathlib import Path
from diary_service import DomainError,valid_slot,resolve_food,local_today
from plan_diet_day import NUTRIENTS,STARCH,PROTEIN,LEGUMES,VEG,OIL,bounds,load_rules
from plan_recipe import values_verified
ROOT=Path(__file__).resolve().parents[1]
POLICY=json.loads((ROOT/'config/meal-matches.json').read_text())


def migrate(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS meal_match(user_id INTEGER,id TEXT,slot TEXT,day_type TEXT,context TEXT,combination TEXT,payload TEXT,created REAL,PRIMARY KEY(user_id,id));
    CREATE TABLE IF NOT EXISTS meal_match_vote(id INTEGER PRIMARY KEY,user_id INTEGER,match_id TEXT,vote TEXT,created REAL,undone INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS match_vote_owner ON meal_match_vote(user_id,match_id,id);
    CREATE TABLE IF NOT EXISTS meal_match_question(user_id INTEGER,generic_id TEXT,answer TEXT,silent_until TEXT,PRIMARY KEY(user_id,generic_id));''')


def current_votes(db,user):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meal_match'").fetchone():return {}
    rows=db.execute('SELECT v.*,m.payload,m.context FROM meal_match_vote v JOIN meal_match m ON m.user_id=v.user_id AND m.id=v.match_id WHERE v.user_id=? AND v.undone=0 ORDER BY v.id',(user,)).fetchall()
    return {r['match_id']:dict(r) for r in rows if r['vote']!='skip'}


def attach(db,user,profile):
    profile['_match_cards']=[dict(json.loads(r['payload']),vote=r['vote']) for r in current_votes(db,user).values() if r['vote']!='skip']
    return profile


def owned(db,user,identifier):
    row=db.execute('SELECT * FROM meal_match WHERE user_id=? AND id=?',(user,identifier)).fetchone()
    if not row:raise DomainError('Scheda non trovata','not_found',404)
    return dict(row)


def vote(db,user,identifier,data):
    owned(db,user,identifier)
    if not isinstance(data,dict) or set(data)!={'vote'} or data['vote'] not in ('like','dislike','love','skip'):raise DomainError('Voto non valido')
    db.execute('INSERT INTO meal_match_vote(user_id,match_id,vote,created) VALUES(?,?,?,?)',(user,identifier,data['vote'],time.time()))
    return dict(id=identifier,vote=data['vote'],undo_available=True)


def undo(db,user,identifier):
    owned(db,user,identifier)
    last=db.execute('SELECT * FROM meal_match_vote WHERE user_id=? AND undone=0 ORDER BY id DESC LIMIT 1',(user,)).fetchone()
    if not last or last['match_id']!=identifier:raise DomainError('Puoi annullare soltanto l’ultima scelta','not_last_vote',409)
    db.execute('UPDATE meal_match_vote SET undone=1 WHERE id=?',(last['id'],))
    previous=current_votes(db,user).get(identifier)
    return dict(id=identifier,vote=previous['vote'] if previous else None,undo_available=bool(db.execute('SELECT 1 FROM meal_match_vote WHERE user_id=? AND undone=0',(user,)).fetchone()))


def questions(db,user,profile):
    rejected={};liked=set();names={}
    for identifier,r in current_votes(db,user).items():
        card=json.loads(r['payload'])
        for food in card['foods']:
            generic=food.get('generic_id')
            if not generic:continue
            names[generic]=food.get('generic_name',food['name'])
            if r['vote'] in ('like','love'):liked.add(generic)
            if r['vote']=='dislike':rejected.setdefault(generic,set()).add(identifier)
    silenced={r['generic_id']:r['silent_until'] for r in db.execute('SELECT * FROM meal_match_question WHERE user_id=?',(user,))}
    excluded=set(profile.get('excluded_crea_ids',[]));today=local_today().isoformat()
    return dict(questions=[dict(food=dict(source='CREA',id=g),name=names[g],question=names[g]+' non ti piace?',discarded_cards=len(ids)) for g,ids in sorted(rejected.items()) if len(ids)>=POLICY['question_dislikes'] and g not in liked|excluded and (silenced.get(g) or '')<=today])


def answer(db,user,profile,generic,data):
    if not isinstance(data,dict) or set(data)!={'answer'} or data['answer'] not in ('yes','no'):raise DomainError('Rispondi yes oppure no')
    if not any(q['food']['id']==generic for q in questions(db,user,profile)['questions']):raise DomainError('Domanda cambiata o non disponibile','question_changed',409)
    silent=None
    if data['answer']=='yes':
        stored=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user,)).fetchone()[0])
        stored['excluded_crea_ids']=sorted(set(stored.get('excluded_crea_ids',[]))|{generic})
        db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(stored),user))
    else:silent=(local_today()+dt.timedelta(days=POLICY['question_silence_days'])).isoformat()
    db.execute('INSERT OR REPLACE INTO meal_match_question VALUES(?,?,?,?)',(user,generic,data['answer'],silent))
    return dict(food=dict(source='CREA',id=generic),answer=data['answer'],excluded=data['answer']=='yes',silent_until=silent)


def targets(profile,slot,kind):
    from daily_meals import defaults
    full=profile.get('daily_meals',{}).get('enabled')
    daily=profile.get('day_type_targets',{}).get(kind) or (profile.get('daily_meals',defaults())['targets'] if full else profile['targets'])
    share=POLICY['meal_shares'][slot] if full else .5
    local=profile.get('meal_targets',{}).get(slot,{})
    result={}
    for n in NUTRIENTS:
        spec=copy.deepcopy(local.get(n) or {k:v*share for k,v in daily[n].items()})
        spec.setdefault('target',(spec['min']+spec['max'])/2)
        if not 0<=spec['min']<=spec['target']<=spec['max'] or spec['target']<=0:raise DomainError('Target locali incompleti o non validi')
        result[n]=spec
    return result


def structures(config,slot,foods):
    if slot in ('lunch','dinner'):
        if config['mode']=='free':return [[STARCH,PROTEIN+LEGUMES,VEG,OIL]]
        path=Path(config.get('schedule_path',ROOT/f"data/personal/ocr/{config['mode']}/schedule_visual_checked.json"))
        schedule=json.loads(path.read_text());rules=load_rules(config)
        days=range(14) if config.get('_match_deck') else [config['day_index']]
        return [groups+([OIL] if groups!=[['000720']] else []) for day in days for letter in schedule['weeks'][day//7][day%7][slot].split(' oppure ') for groups in rules[config['mode']].get(letter,[]) if 2<=len(groups)+1<=4]
    from daily_meals import add_choices
    if not config.get('daily_meals',{}).get('enabled') or slot=='afternoon_snack' and not config['daily_meals']['afternoon_fruit']:return []
    variables=[];choices=[]
    def var(*args):variables.append(args);return len(variables)-1
    plain=copy.deepcopy(config);plain.pop('_match_cards',None)
    add_choices(plain,foods,var,lambda *args:None,choices)
    return [[[c['food_id']]] for c in choices if c['meal']==slot]


def image_for(label):
    license=label.get('image_license');url=label.get('image_url');author=label.get('image_attribution')
    if not isinstance(license,str) or not license.upper().startswith('CC BY-SA') or not isinstance(url,str) or not url.startswith('https://') or not author:return None
    return dict(url=url,license=license,attribution=author)


def food_record(identifier,profile,foods):
    generic=identifier if not identifier.startswith('personal:') else None
    ref=dict(source='CREA',id=identifier) if generic else dict(source='user_label',id=identifier.split(':',1)[1])
    # Explicit equivalence chosen by the owner; no automatic brand substitution.
    stores=profile.get('goals',{}).get('activity',{}).get('preferred_stores',[])
    preferred=profile.get('food_preferences',{}).get('preferred_products',{}).get(generic) if stores else None
    disabled=profile.get('food_preferences',{}).get('disabled_products',[])
    if preferred and preferred.get('id') not in disabled and preferred.get('source','')+':'+preferred.get('id','') not in disabled:
        try:
            product=resolve_food(preferred,profile)
            if any(v is None or not math.isfinite(v) for v in product['per_100g'].values()):raise ValueError()
            # OFF quality checks use the same source vector as the approved equivalence.
            if preferred['source']=='OFF':
                with sqlite3.connect('file:'+str(ROOT/'dataset/open_food_facts/catalog.sqlite')+'?mode=ro',uri=True) as db:
                    raw=json.loads(db.execute('SELECT payload FROM products WHERE barcode=?',(preferred['id'],)).fetchone()[0])
                expected=4*product['per_100g']['protein_g']+4*product['per_100g']['carbs_available_g']+9*product['per_100g']['fat_g']+2*float(raw.get('fiber_g_100g') or 0)
                if raw.get('source_quality_errors') or abs(product['per_100g']['kcal']-expected)/max(expected,1)>.15:raise ValueError()
            else:raw={}
            ref=preferred
        except (DomainError,ValueError,KeyError,TypeError,sqlite3.Error):raw={};ref=dict(source='CREA',id=generic)
    else:raw={}
    food=resolve_food(ref,profile)
    if any(v is None or not math.isfinite(v) or v<0 for v in food['per_100g'].values()):raise ValueError('Alimento senza macro completi')
    return dict(food=ref,generic_id=generic,generic_name=foods[identifier]['name'],name=food['name'],brand=food.get('brand'),source_label=food['source_label'],per_100g=food['per_100g'],fiber_g_100g=raw.get('fiber_g_100g') if ref['source']=='OFF' else foods[identifier].get('fiber_g_100g'),image=image_for(raw),bounds=list(bounds(identifier)) if generic else [food['unit_g'],food['unit_g']])


def combination(items):return tuple(sorted(i.get('generic_id') or i['food']['source']+':'+i['food']['id'] for i in items if i.get('generic_id') not in OIL))


def model(items,target):
    variables=[];constraints=[];objective=[]
    def row(values,relation,rhs):constraints.append(dict(coefficients=values,relation=relation,rhs=rhs))
    for i,item in enumerate(items):
        lo,hi=item['bounds'];step=5 if item['food']['source']=='CREA' or item['food']['source']=='OFF' else 1
        variables.append(dict(name='grams_'+str(i),lb=max(step,math.ceil(lo/step)*step)/step,ub=math.floor(hi/step),integrality='I'));objective.append(0)
        item['_step']=step
    count=len(variables)
    for n in NUTRIENTS:
        key=n.replace('_100g','');coeff=[i['per_100g'][key]*i['_step']/100 for i in items];spec=target[n]
        variables.append(dict(name='dev_'+key,lb=0,ub=max(spec['max']-spec['target'],spec['target']-spec['min']),integrality='C'));objective.append(1/spec['target'])
        row(coeff,'>=',spec['min']);row(coeff,'<=',spec['max'])
        row(coeff+[0]*(len(variables)-count-1)+[-1],'<=' ,spec['target'])
        row([-v for v in coeff]+[0]*(len(variables)-count-1)+[-1],'<=' ,-spec['target'])
    for r in constraints:r['coefficients'] += [0]*(len(variables)-len(r['coefficients']))
    return dict(version='1',variables=variables,constraints=constraints,objective=dict(sense='min',coefficients=objective),solver=dict(time_limit=POLICY['solve_seconds']))


async def deck(session,db,user,profile,slot,kind,make_config):
    from plan_diet_day import load_foods,solve_problem
    valid_slot(slot)
    if kind not in ('rest','training'):raise DomainError('Tipo di giornata non valido')
    target=targets(profile,slot,kind);personal=copy.deepcopy(profile)
    if personal.get('personal_diets') and personal['mode']!='free':personal['mode']='training' if kind=='training' else 'sedentary'
    config=make_config(personal,0);config['_match_deck']=True;foods=load_foods();groups=structures(config,slot,foods)
    excluded=set(profile.get('excluded_crea_ids',[]));candidates={}
    for structure in groups:
        filtered=[[i for i in group if i not in excluded] for group in structure]
        if any(not g for g in filtered):continue
        for ids in itertools.product(*filtered):
            try:items=[food_record(i,profile,foods) for i in ids]
            except (ValueError,DomainError):continue
            for i,item in zip(ids,items):
                if i in config.get('portion_bounds_g',{}):item['bounds']=config['portion_bounds_g'][i]
                if i=='007510' and slot not in ('lunch','dinner'):item['bounds']=[config['daily_meals']['banana_min_g'],config['daily_meals']['banana_max_g']]
            candidates.setdefault(combination(items),items)
    context=hashlib.sha256(json.dumps(dict(slot=slot,day_type=kind,mode=personal['mode'],targets=target),sort_keys=True).encode()).hexdigest()
    seen={tuple(json.loads(r[0])) for r in db.execute('SELECT combination FROM meal_match WHERE user_id=? AND context=?',(user,context))}
    votes=current_votes(db,user);liked={tuple(json.loads(r['payload'])['combination']) for r in votes.values() if r['vote'] in ('like','love')}
    ordered=list(candidates)
    cards=[];novel=[];familiar=[];tested=0;started=time.monotonic();certified=True
    while ordered:
        selected=novel+familiar
        def priority(key):
            phase=(key in seen) if len(novel)<3 else (0 if key in liked else 1)
            overlap=max((len(set(key)&set(c['combination'])) for c in selected),default=0)
            typical=any(p.get('reviewed') is True and set(p.get('foods',[]))<=set(key) for p in POLICY['reviewed_typical_pairings'])
            return (phase,overlap,not typical,key)
        key=min(ordered,key=priority);ordered.remove(key)
        if time.monotonic()-started>POLICY['deck_seconds']:certified=False;break
        items=copy.deepcopy(candidates[key]);p=model(items,target);tested+=1
        if any(v['lb']>v['ub'] for v in p['variables']):continue
        result=await solve_problem(session,p)
        if result['mathematical_status'] not in ('optimal','feasible'):
            if result['mathematical_status']!='infeasible':certified=False
            continue
        values=values_verified(p,result)
        for i,item in enumerate(items):item['grams']=int(round(values[i]*item.pop('_step')))
        public=dict(slot=slot,day_type=kind,mode=personal['mode'],targets=target,foods=items,combination=list(key),nutrients={n.replace('_100g',''):round(sum(i['grams']*i['per_100g'][n.replace('_100g','')]/100 for i in items),3) for n in NUTRIENTS})
        public['id']=hashlib.sha256(json.dumps(public,sort_keys=True).encode()).hexdigest()[:32];public['exploration']=key not in seen
        public['optimization']=dict(engine='optees.milp.linear',status=result['mathematical_status'],validation='verified')
        (novel if public['exploration'] else familiar).append(public)
        if len(novel)>=3 and len(novel)+len(familiar)>=POLICY['deck_size']:certified=False;break
    need=math.ceil(POLICY['deck_size']*POLICY['minimum_exploration_fraction'])
    if len(novel)>=need:cards=(novel[:need]+sorted(familiar,key=lambda c:c['combination'] not in [list(x) for x in liked])+novel[need:])[:POLICY['deck_size']]
    else:cards=novel[:]
    for card in cards:
        db.execute('INSERT OR IGNORE INTO meal_match VALUES(?,?,?,?,?,?,?,?)',(user,card['id'],slot,kind,context,json.dumps(card['combination']),json.dumps(card),time.time()))
        card['vote']=votes.get(card['id'],{}).get('vote')
    status='ok' if len(cards)==10 else 'partial' if cards else 'unavailable'
    return dict(status=status,slot=slot,day_type=kind,cards=cards,reason=None if status=='ok' else 'Schemi, target o proposte nuove insufficienti per dieci schede; nessun vincolo rilassato.',pool=dict(requested=10,returned=len(cards),exploration_fraction=sum(c['exploration'] for c in cards)/len(cards) if cards else None,candidates=len(candidates),tested=tested,certified=certified),parameters=POLICY)


def allowed(card,config,foods,meal):
    if card['slot']!=meal or card['day_type']!=config.get('day_type','rest'):return False
    ids=[i['generic_id'] or 'personal:'+i['food']['id'] for i in card['foods']]
    if set(ids)&set(config.get('excluded_crea_ids',[])):return False
    groups=structures(config,meal,foods)
    return any(len(g)==len(ids) and any(all(i in group for i,group in zip(ordered,g)) for ordered in itertools.permutations(ids)) for g in groups)


def branches(config,foods,meal,var,add,choices):
    added=[]
    for card in config.get('_match_cards',[]):
        if card['vote'] not in ('like','love') or not allowed(card,config,foods,meal):continue
        y=var('match_'+meal+'_'+card['id'],0,1,'B');added.append(y);mass=[];total=sum(i['grams'] for i in card['foods'])
        for group,item in enumerate(card['foods']):
            ref=item['food'];identifier=item['generic_id'] if ref['source']=='CREA' else 'match:'+ref['source']+':'+ref['id'];generic=item.get('generic_id')
            # Revalidate labels against the CURRENT profile, not the stale deck vector.
            try:current=resolve_food(ref,config.get('_match_profile',{}))
            except DomainError:continue
            if any(v is None for v in current['per_100g'].values()):continue
            disabled=config.get('food_preferences',{}).get('disabled_products',[])
            if ref['id'] in disabled or ref['source']+':'+ref['id'] in disabled:continue
            foods[identifier]=dict(name=current['name'],source=ref['source'],source_id=ref['id'],principal_food_id=generic,fiber_g_100g=item.get('fiber_g_100g'),**{n:str(current['per_100g'][n.replace('_100g','')]) for n in NUTRIENTS})
            lo,hi=config.get('portion_bounds_g',{}).get(generic,item['bounds']);q=var('match_q'+str(len(choices)),0,hi);steps=var('match_steps'+str(len(choices)),0,math.floor(hi/5),'I')
            add({q:1,steps:-5},'=',0);add({q:1,y:-hi},'<=',0);add({q:1,y:-lo},'>=',0)
            mass.append((q,item['grams']/total))
            choices.append(dict(meal=meal,combination='match',branch_index=len(added),group=group,food_id=identifier,principal_food_id=generic,y=y,q=q,nutrients=[float(foods[identifier][n])/100 for n in NUTRIENTS],source=ref['source'],reference_id=ref['id'],match_id=card['id'],match_vote=card['vote']))
        if len(mass)!=len(card['foods']):add({y:1},'=',0);continue
        flexibility=POLICY['ratio_flexibility']
        for q,fraction in mass:
            add({**{j:-(1-flexibility)*fraction for j,_ in mass},q:1-(1-flexibility)*fraction},'>=',0)
            add({**{j:-(1+flexibility)*fraction for j,_ in mass},q:1-(1+flexibility)*fraction},'<=',0)
    return added


def penalties(config,choices,var,add,objective):
    seen=set()
    for c in choices:
        if c.get('match_id') and (c['meal'],c['y']) not in seen:
            seen.add((c['meal'],c['y']));objective[c['y']]=objective.get(c['y'],0)-POLICY['preference_bonus']*(2 if c['match_vote']=='love' else 1)
    rejected={(c['slot'],tuple(c['combination'])) for c in config.get('_match_cards',[]) if c['vote']=='dislike'}
    for meal,ids in sorted(rejected):
        groups=[{c['y'] for c in choices if c['meal']==meal and (c.get('principal_food_id') or c['food_id'])==identifier} for identifier in ids]
        if not groups or any(not g for g in groups):continue
        p=var('match_dislike_'+str(len(objective)),0,1,'B');objective[p]=POLICY['dislike_penalty']
        for group in groups:add({**{y:1 for y in group},p:-1},'>=',0)
        counts={}
        for group in groups:
            for y in group:counts[y]=counts.get(y,0)+1
        add({**counts,p:-1},'<=',len(groups)-1)

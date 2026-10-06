"""Owner meal intentions and soft recipe preferences, with approved composition."""
import copy
import datetime as dt
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path
from diary_service import DomainError
ROOT=Path(__file__).resolve().parents[1]
POLICY=json.loads((ROOT/'config/recipe-week-policy.json').read_text())
MAX_OCCURRENCES=POLICY['max_occurrences_per_week']
PREFERENCE_BONUS=POLICY['objective_bonus']
MAX_PORTIONS=POLICY['max_portions']
if any(isinstance(v,bool) or not isinstance(v,int) or not 1<=v<=14 for v in (MAX_OCCURRENCES,MAX_PORTIONS)) or isinstance(PREFERENCE_BONUS,bool) or not isinstance(PREFERENCE_BONUS,(int,float)) or not math.isfinite(PREFERENCE_BONUS) or not 0<=PREFERENCE_BONUS<=1:raise ValueError('Parametri settimanali ricette non validi')


def migrate(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS recipe_preference(user_id INTEGER,recipe_id TEXT,preferred INTEGER,updated REAL,PRIMARY KEY(user_id,recipe_id));
    CREATE TABLE IF NOT EXISTS planned_food_snapshot(user_id INTEGER,source TEXT,id TEXT,payload TEXT,PRIMARY KEY(user_id,source,id));
    CREATE TABLE IF NOT EXISTS locked_dish(user_id INTEGER,week_start TEXT,date TEXT,slot TEXT,payload TEXT,updated REAL,PRIMARY KEY(user_id,date,slot));''')


def display_title(value):
    provenance=value.get('provenance',{})
    if provenance.get('source')=='preset':
        from meal_rebalance import catalog
        preset=catalog()['presets'].get(provenance.get('preset_id'),{})
        size=preset.get('sizes',{}).get(provenance.get('size'),{})
        if preset.get('name') and size.get('label'):return preset['name']+' · '+size['label'].lower()
    return value.get('title','Piatto stimato')


def attach(db,user,profile):
    profile['_preferred_recipe_ids']=[r[0] for r in db.execute('SELECT recipe_id FROM recipe_preference WHERE user_id=? AND preferred=1 ORDER BY recipe_id',(user,))]
    profile['_locked_dishes']=[dict(json.loads(r['payload']),week_start=r['week_start']) for r in db.execute('SELECT week_start,payload FROM locked_dish WHERE user_id=? ORDER BY date,slot',(user,))]
    for dish in profile['_locked_dishes']:
        if dish.get('kind')=='estimate':dish['title']=display_title(dish)
    profile['_dish_estimates']={r['food_id']:r for r in profile['_locked_dishes'] if r.get('food_id')}
    for r in db.execute('SELECT source,id,payload FROM planned_food_snapshot WHERE user_id=?',(user,)):
        profile.setdefault('_recipe_runs' if r['source']=='recipe' else '_dish_estimates',{})[r['id']]=json.loads(r['payload'])
    return profile


def template(identifier):
    from plan_recipe import templates
    row=next((r for r in templates() if r['id']==identifier),None)
    if not row:raise DomainError('Ricetta non ancora pronta per il solver','recipe_unavailable')
    return row


def materialize(identifier,profile):
    """Fixed reviewed proportions; all nutrient vectors recalculated locally."""
    from calculate_recipe_nutrients import food_lookup
    from recipe_special_sources import special_food
    from plan_diet_day import NUTRIENTS
    recipe=template(identifier);parts=[];totals={n:0. for n in NUTRIENTS}
    for ingredient in recipe['ingredients']:
        grams=ingredient['grams_per_reference_portion']
        if isinstance(grams,bool) or not isinstance(grams,(int,float)) or not math.isfinite(grams) or grams<=0:raise DomainError('Peso ingrediente non verificabile','recipe_unavailable')
        candidates=[c for c in ingredient['candidates'] if c.get('reviewed') is True and c.get('state_checked') is True]
        generics={c['id'] for c in candidates if c['source']=='CREA'}
        if generics&set(profile.get('excluded_crea_ids',[])):raise DomainError('Ricetta contiene un alimento escluso','recipe_excluded')
        preferences=profile.get('food_preferences',{});preferred=[preferences.get('preferred_products',{}).get(g) for g in generics]
        def rank(c):
            ref=dict(source='OFF' if c['source']=='Open Food Facts' else c['source'],id=c['id'])
            return (ref not in preferred,c['source'] not in ('OFF','Open Food Facts'),c['id'])
        found=None
        for candidate in sorted(candidates,key=rank):
            if candidate['id'] in preferences.get('disabled_products',[]) or candidate['source']+':'+candidate['id'] in preferences.get('disabled_products',[]):continue
            try:
                source=candidate['source'];food=(dict(name='Acqua pura',nutrient_basis='per_100_g',**{n:0. for n in NUTRIENTS}) if source=='water' and candidate['id']=='water' else special_food(source,candidate['id'],food_lookup) if source in ('stock','condiment') else food_lookup('Open Food Facts' if source=='OFF' else source,candidate['id']))
                if food.get('nutrient_basis','per_100_g')!='per_100_g' or food.get('source_quality_errors') or any(f.startswith(('implausible','inconsistent')) for f in food.get('quality_flags',[])):continue
                values=[float(food[n]) for n in NUTRIENTS]
                if any(not math.isfinite(v) or v<0 for v in values):continue
                found=candidate,food,values;break
            except (KeyError,ValueError,TypeError,sqlite3.Error):continue
        if not found:raise DomainError('Ingrediente senza candidato nutrizionale approvato: '+ingredient['name'],'recipe_unavailable')
        candidate,food,values=found
        parts.append(dict(source=candidate['source'],id=candidate['id'],canonical_id=next(iter(generics)) if len(generics)==1 else None,protein_g=grams*values[1]/100,grams=grams,food=food['name'],ingredient=ingredient['name']))
        for n,value in zip(NUTRIENTS,values):totals[n]+=grams*value/100
    for trace in recipe.get('trace_condiments',[]):
        if trace.get('reviewed') is not True or trace.get('state_checked') is not True or trace.get('category')!='condimento' or trace.get('declared_kcal')!=0:raise DomainError('Condimento non approvato','recipe_unavailable')
    mass=sum(p['grams'] for p in parts)
    unit_g=max(5,round(mass/5)*5)
    # Normalize <=2.5g to the 5g grid, preserving ratios; recompute the
    # nutrient totals on those actual normalized ingredient weights.
    for part in parts:
        part['grams']*=unit_g/mass;part['protein_g']*=unit_g/mass
    for n in totals:totals[n]*=unit_g/mass
    if unit_g>3000:raise DomainError('La porzione di riferimento supera il limite di quantità','recipe_unavailable')
    return dict(status='optimal',title=recipe['title'],recipe_id=identifier,unit_g=unit_g,reference_mass_g=mass,weight_normalization_g=unit_g-mass,selections=parts,trace_condiments=copy.deepcopy(recipe.get('trace_condiments',[])),nutrients={n.replace('_100g','').replace('carbs_available_g','carbs_g'):v for n,v in totals.items()},provenance='reviewed_reference_recipe_recalculated_fixed_ratios',recipe=recipe)


def recipe_food(identifier,profile):
    recipe=materialize(identifier,profile)
    from plan_diet_day import NUTRIENTS
    snapshot={k:v for k,v in recipe.items() if k!='recipe'}
    from day_orchestration import family
    principal=max((p for p in recipe['selections'] if p.get('canonical_id') and family(p['canonical_id'])),key=lambda p:p.get('protein_g',0),default={}).get('canonical_id')
    snapshot['principal_food_id']=principal
    ref='approved:'+identifier+':'+hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()[:16]
    profile.setdefault('_recipe_runs',{})[ref]=snapshot
    profile.setdefault('_generated_recipe_snapshots',{})[ref]=snapshot
    return dict(name=recipe['title'],source='recipe',source_id=ref,recipe_id=identifier,principal_food_id=principal,unit_g=recipe['unit_g'],composition_provenance=dict(ingredients=[dict(source=p['source'],id=p['id'],name=p['food'],fraction=p['grams']/recipe['unit_g']) for p in recipe['selections']]),**{n:recipe['nutrients']['carbs_g' if n=='carbs_available_g_100g' else n.replace('_100g','')]*100/recipe['unit_g'] for n in NUTRIENTS})


def catalog_recipe(identifier):
    try:return template(identifier)
    except DomainError:pass
    with sqlite3.connect('file:'+str(ROOT/'dataset/recipes/catalog.sqlite')+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT payload FROM recipes WHERE id=?',(identifier,)).fetchone()
    if not row:raise DomainError('Ricetta non trovata','recipe_not_found',404)
    return json.loads(row[0])


def set_preferred(db,user,identifier,data):
    if not isinstance(data,dict) or set(data)!={'preferred'} or not isinstance(data['preferred'],bool):raise DomainError('Indica preferred: true oppure false')
    catalog_recipe(identifier)
    db.execute('INSERT INTO recipe_preference VALUES(?,?,?,?) ON CONFLICT(user_id,recipe_id) DO UPDATE SET preferred=excluded.preferred,updated=excluded.updated',(user,identifier,int(data['preferred']),time.time()))
    return dict(recipe_id=identifier,preferred=data['preferred'])


def preferences(profile):
    rows=[];queue=[]
    for identifier in profile.get('_preferred_recipe_ids',[]):
        recipe=catalog_recipe(identifier)
        try:materialize(identifier,profile);status='ready';reason=None
        except DomainError as e:status='unavailable';reason=str(e)
        item=dict(recipe_id=identifier,title=recipe['title'],preferred=True,solver_status=status,reason=reason);rows.append(item)
        if status!='ready':queue.append(dict(item,priority='preferred_first',ingredients=[i.get('name') for i in recipe.get('ingredients',[])]))
    return dict(recipes=rows,review_queue=queue,limits=dict(max_occurrences_per_week=MAX_OCCURRENCES,max_portions=MAX_PORTIONS,objective_bonus=PREFERENCE_BONUS))


def validate_lock(start,data,profile,today=None):
    import diary_service as diary
    from meal_rebalance import estimate
    today=today or diary.local_today();start=diary.valid_date(start)
    if not isinstance(data,dict) or set(data)-{'date','slot','recipe','preset','custom'}:raise DomainError('Piatto bloccato non valido')
    date=diary.valid_date(data.get('date'));slot=diary.valid_slot(data.get('slot'));day=dt.date.fromisoformat(date)
    if day<=today or not start<=date<=(dt.date.fromisoformat(start)+dt.timedelta(days=6)).isoformat():raise DomainError('Scegli un pasto futuro della settimana richiesta')
    if slot not in ('lunch','dinner'):raise DomainError('Un piatto può essere bloccato a pranzo o cena')
    if sum(k in data for k in ('recipe','preset','custom'))!=1:raise DomainError('Scegli ricetta, preset oppure stima libera')
    if 'recipe' in data:
        ref=data['recipe']
        if not isinstance(ref,dict) or set(ref)!={'id','portions'}:raise DomainError('Ricetta: servono id e portions')
        diary.integer(ref['portions'],1,MAX_PORTIONS);recipe=materialize(ref['id'],profile)
        if recipe['unit_g']*ref['portions']>3000:raise DomainError('Porzione complessiva oltre 3000 g')
        return dict(date=date,slot=slot,kind='recipe',recipe=copy.deepcopy(ref),title=recipe['title'])
    # Reuse the exact preset/interval validation; only the temporal rule differs.
    body=dict(data,date=today.isoformat());body.pop('recipe',None)
    value=estimate(body,today);value['date']=date;value['kind']='estimate'
    value['title']=display_title(value)
    value['food_id']=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()[:24]
    return value


def put_lock(db,user,profile,start,data):
    import diary_service as diary
    value=validate_lock(start,data,profile)
    if diary.state(db,user,value['date'],value['slot'])!='unknown':raise DomainError('Pasto già registrato','slot_already_logged',409)
    previous=diary.planned(db,user,value['date'],value['slot'])
    if previous and previous['locked']:db.execute('UPDATE planned_meal SET locked=0 WHERE id=?',(previous['id'],))
    db.execute('INSERT INTO locked_dish VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,date,slot) DO UPDATE SET week_start=excluded.week_start,payload=excluded.payload,updated=excluded.updated',(user,start,value['date'],value['slot'],json.dumps(value),time.time()))
    return dict(week_start=start,locked_dish=value,effect='next_generation_only')


def prepare(profile,request):
    start=request['week_start'];entries=[dict(d,_stored=True) for d in profile.get('_locked_dishes',[]) if d['week_start']==start and d['date']>__import__('diary_service').local_today().isoformat()]
    extra=request.get('locked_dishes',[])
    if not isinstance(extra,list):raise DomainError('Piatti bloccati non validi')
    entries.extend(validate_lock(start,d,profile) for d in extra)
    locks=copy.deepcopy(request.get('locked',[]));seen={(l['date'],l['slot']) for l in locks}
    recipe_ids=set(profile.get('_preferred_recipe_ids',[]));estimates=dict(profile.get('_dish_estimates',{}));intent_by_date={}
    for dish in entries:
        key=dish['date'],dish['slot']
        if key in seen:
            if dish.get('_stored'):continue
            raise DomainError('Blocco duplicato per giorno e pasto')
        seen.add(key);intent_by_date.setdefault(dish['date'],[]).append(dish)
        if dish['kind']=='recipe':
            ref=dish['recipe'];recipe_ids.add(ref['id']);food=recipe_food(ref['id'],profile)
            items=[dict(food=dict(source='recipe',id=food['source_id']),grams=food['unit_g']*ref['portions'],units=ref['portions'])]
        else:
            estimates[dish['food_id']]=dish;items=[dict(food=dict(source='dish_estimate',id=dish['food_id']),grams=100)]
        locks.append(dict(date=dish['date'],slot=dish['slot'],items=items))
    profile['_dish_estimates']=estimates
    return dict(request,locked=locks),recipe_ids,intent_by_date


def configure(config,foods,profile,recipe_ids):
    from plan_diet_day import NUTRIENTS
    rows=[];unavailable=[]
    for identifier in sorted(recipe_ids):
        try:
            recipe=materialize(identifier,profile);food=recipe_food(identifier,profile)
            key='approved-recipe:'+identifier;foods[key]=food
            rows.append(dict(id=identifier,food_id=key,food=food,recipe=recipe['recipe'],preferred=identifier in profile.get('_preferred_recipe_ids',[])))
        except DomainError as e:unavailable.append(dict(recipe_id=identifier,reason=str(e)))
    config['_recipe_candidates']=rows;config['_recipe_unavailable']=unavailable
    config['_preferred_recipe_ids']=profile.get('_preferred_recipe_ids',[])
    config['_recipe_snapshots']=copy.deepcopy(profile.get('_generated_recipe_snapshots',{}))
    config['_dish_estimates']=copy.deepcopy(profile.get('_dish_estimates',{}))
    return config


def persist_snapshots(db,user,profile,plan):
    for day in plan.get('days',[plan]):
        for source,field,profile_field in [('recipe','_recipe_snapshots','_recipe_runs'),('dish_estimate','_dish_estimates','_dish_estimates')]:
            snapshots=day.get(field,{}) or plan.get(field,{})
            used={s.get('reference_id') for s in day.get('selections',[]) if s.get('source')==source}
            for ref in used:
                if ref not in snapshots:continue
                raw=json.dumps(snapshots[ref]);db.execute('INSERT OR IGNORE INTO planned_food_snapshot VALUES(?,?,?,?)',(user,source,ref,raw))
                profile.setdefault(profile_field,{})[ref]=snapshots[ref]


def explain(plan,profile):
    chosen={s.get('recipe_id') for d in plan['days'] for s in d['selections']}
    eligible={r['id'] for d in plan['days'] for r in d.get('_recipe_candidates_summary',[])}
    failures={r['recipe_id']:r['reason'] for d in plan['days'] for r in d.get('_recipe_unavailable',[])}
    return [dict(recipe_id=i,inserted=i in chosen,reason=None if i in chosen else failures.get(i) or ('Nessun abbinamento della dieta verificato per questa ricetta nei pasti disponibili.' if i not in eligible else 'La porzione intera minima non è stata selezionata: vincoli nutrizionali, limite di frequenza o compromesso con gli altri obiettivi. Non è una prova di impossibilità.')) for i in profile.get('_preferred_recipe_ids',[])]


def add_branches(config,foods,meal,expression,var,add,choices):
    from plan_diet_day import NUTRIENTS,STARCH,VEG,PROTEIN,LEGUMES,FRUIT,OIL,bounds
    from recipe_diet_compatibility import assess
    branches=[];eligible=[]
    for record in config.get('_recipe_candidates',[]):
        locked=config.get('_locked_recipe_by_slot',{}).get(meal)
        if locked and locked['id']!=record['id']:continue
        if not record['preferred'] and not locked:continue
        recipe=record['recipe'];food=record['food'];identifier=record['food_id'];mode=config['mode']
        if mode=='free':specs=[dict(id='free',groups=[],optional=True)]
        else:
            assessment=assess(recipe,mode,expression);specs=[]
            from recipe_diet_compatibility import GROUPS
            categories=json.loads(GROUPS.read_text())['foods']
            for branch in assessment['branches']:
                if branch['status']=='needs_review':continue
                supplements=[]
                for missing in branch['complement_options']:
                    supplement=[i for i in foods if categories.get('CREA:'+i) in missing['allowed_groups'] and i not in config.get('excluded_crea_ids',[])]
                    if not supplement:break
                    supplements.append(supplement)
                else:specs.append(dict(id=branch['branch_id'],groups=supplements,optional=False))
        for i,spec in enumerate(specs):
            unique_branch=len(branches)
            eligible.append(record['id']);branch=var(f'{meal}_recipe_{record["id"]}_{i}',0,1,'B');branches.append(branch)
            max_portions=min(MAX_PORTIONS,3000//food['unit_g'])
            portions=var('recipe_portions_'+str(len(choices)),0,max_portions,'I');q=var('recipe_grams_'+str(len(choices)),0,food['unit_g']*max_portions)
            add({q:1,portions:-food['unit_g']},'=',0);add({portions:1,branch:-1},'>=',0);add({portions:1,branch:-max_portions},'<=',0)
            if locked:add({portions:1,branch:-locked['portions']},'=',0)
            values=[float(food[n])/100 for n in NUTRIENTS]
            choices.append(dict(meal=meal,combination='recipe',branch_index=unique_branch,group=0,food_id=identifier,recipe_id=record['id'],principal_food_id=food.get('principal_food_id'),y=branch,q=q,portion_index=portions,nutrients=values,source='recipe',reference_id=food['source_id'],preferred_recipe=record['preferred']))
            for group_no,group in enumerate(spec['groups'],1):
                selected=[]
                for ref in group:
                    if ref in config.get('excluded_crea_ids',[]):continue
                    value=foods[ref]
                    try:nut=[float(value[n])/100 for n in NUTRIENTS]
                    except (KeyError,ValueError,TypeError):continue
                    if any(not math.isfinite(v) or v<0 for v in nut):continue
                    low,high=config.get('portion_bounds_g',{}).get(ref,bounds(ref));y=var('recipe_side_y'+str(len(choices)),0,1,'B');q=var('recipe_side_q'+str(len(choices)),0,high);steps=var('recipe_side_steps'+str(len(choices)),0,math.floor(high/5),'I')
                    add({q:1,steps:-5},'=',0);add({q:1,y:-high},'<=',0);add({q:1,y:-low},'>=',0);selected.append(y)
                    choices.append(dict(meal=meal,combination='recipe',branch_index=unique_branch,group=group_no,food_id=ref,y=y,q=q,nutrients=nut))
                add({**{y:1 for y in selected},branch:-1},'<=' if spec['optional'] else '=',0)
    if config['mode']=='free' and branches:
        # All recipes share the same optional free-mode complements. Duplicating
        # them per favorite creates a dense quadratic model for no extra choice.
        on=var(meal+'_any_recipe',0,1,'B');add({**{b:1 for b in branches},on:-1},'=',0)
        for group_no,group in enumerate([STARCH,VEG,PROTEIN+LEGUMES,FRUIT,OIL],1):
            selected=[]
            for ref in group:
                if ref in config.get('excluded_crea_ids',[]):continue
                value=foods[ref]
                try:nut=[float(value[n])/100 for n in NUTRIENTS]
                except (KeyError,ValueError,TypeError):continue
                if any(not math.isfinite(v) or v<0 for v in nut):continue
                low,high=config.get('portion_bounds_g',{}).get(ref,bounds(ref));y=var('recipe_shared_y'+str(len(choices)),0,1,'B');q=var('recipe_shared_q'+str(len(choices)),0,high);steps=var('recipe_shared_steps'+str(len(choices)),0,math.floor(high/5),'I')
                add({q:1,steps:-5},'=',0);add({q:1,y:-high},'<=',0);add({q:1,y:-low},'>=',0);selected.append(y)
                choices.append(dict(meal=meal,combination='recipe_sides',branch_index=0,group=group_no,food_id=ref,y=y,q=q,nutrients=nut))
            add({**{y:1 for y in selected},on:-1},'<=',0)
    config.setdefault('_recipe_candidates_summary',[]).extend(dict(id=i) for i in sorted(set(eligible)))
    return branches

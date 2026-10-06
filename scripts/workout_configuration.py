"""User-declared feasibility and loads; never infer personal readiness or equipment."""
import copy
import json
from pathlib import Path
from build_workout_catalog import REVIEWED
from diary_service import DomainError
from workout_sessions import compile_session

ROOT=Path(__file__).resolve().parents[1]
EQUIPMENT=('manubri','bilanciere','bilanciere_curvo','panca','panca_inclinata','vogatore_acqua','cyclette','tapis_roulant_inclinabile','ellittica','aqua_bag','aqua_tank','crunch_machine','ab_wheel','parallele','barra_trazioni','sedia')
VARIANTS={key:['standard'] for key in REVIEWED}
VARIANTS.update({'push-up':['standard','knees','hands_elevated'],'bodyweight-squat':['standard','chair_assisted'],'inverted-row':['feet_on_floor']})


def defaults():
    return dict(level=None,equipment=None,available_loads_kg=[],starting_loads_kg={},variants={},australian_pullups_setup_verified=False,intensity_confirmed=False,high_intensity_ready=False,protocol_overrides={})


def read(db,user):
    row=db.execute('SELECT settings FROM workout_configuration WHERE user_id=?',(user,)).fetchone()
    settings=dict(defaults(),**json.loads(row['settings'])) if row else defaults()
    owner=db.execute('SELECT profile FROM users WHERE id=?',(user,)).fetchone()
    settings['strength_anchors']=copy.deepcopy(json.loads(owner['profile']).get('goals',{}).get('strength_anchors',[])) if owner else []
    settings['_load_history']=[dict(r) for r in db.execute('SELECT s.exercise_id,s.reps,s.kg,s.rir,s.rpe,w.date FROM set_log s JOIN workout_log w ON w.id=s.workout_log_id WHERE w.user_id=? ORDER BY w.date DESC,s.id DESC LIMIT 500',(user,))][::-1]
    from diary_service import local_today
    today=local_today();monday=(today-__import__('datetime').timedelta(days=today.weekday())).isoformat()
    references={}
    for row in db.execute('SELECT s.date,s.snapshot FROM planned_session s JOIN week_plan w ON w.id=s.week_plan_id WHERE w.user_id=? AND s.date<? ORDER BY s.date,s.id',(user,monday)):
        for exercise in json.loads(row['snapshot']).get('exercises',[]):
            if exercise.get('load_kg') is not None and exercise['load_kg']>0:references[exercise['source_id']]=dict(load_kg=exercise['load_kg'],date=row['date'])
    settings['_load_references']=references
    return settings


def seed_legacy_equipment(db,user,path):
    """One-time transfer of the designated owner's already declared local inventory."""
    if db.execute('SELECT 1 FROM workout_configuration WHERE user_id=?',(user,)).fetchone() or not path.exists():return
    inventory=json.loads(path.read_text())
    settings=update(defaults(),dict(equipment=inventory['equipment'],australian_pullups_setup_verified=inventory.get('requirements',{}).get('australian_pullups_setup_verified',False)))
    from workout_service import now
    db.execute('INSERT INTO workout_configuration(user_id,settings,updated) VALUES(?,?,?)',(user,json.dumps(settings),now()))


def update(current,data):
    from workout_service import finite
    if not isinstance(data,dict) or set(data)-set(defaults()):raise DomainError('Campi della configurazione non validi')
    config=copy.deepcopy(current)
    # Nested maps are replacements, making removal of old loads/variants explicit.
    config.update(copy.deepcopy(data))
    if config['level'] not in (None,'beginner','intermediate','advanced'):raise DomainError('Livello non valido')
    equipment=config['equipment']
    if equipment is not None and (not isinstance(equipment,list) or any(not isinstance(e,str) or e not in EQUIPMENT for e in equipment) or len(equipment)!=len(set(equipment))):raise DomainError('Attrezzatura non valida')
    for key in ('australian_pullups_setup_verified','intensity_confirmed','high_intensity_ready'):
        if not isinstance(config[key],bool):raise DomainError('Conferma personale non valida')
    weights=config['available_loads_kg']
    if not isinstance(weights,list) or len(weights)>100:raise DomainError('Pesi disponibili non validi')
    for weight in weights:finite(weight,'Peso disponibile',.01,1000)
    if len(weights)!=len(set(weights)):raise DomainError('Pesi disponibili duplicati')
    loads=config['starting_loads_kg']
    if not isinstance(loads,dict) or set(loads)-set(REVIEWED):raise DomainError('Carichi di partenza non validi')
    for exercise,weight in loads.items():
        finite(weight,'Carico di partenza',0,1000,True)
        if 'manubri' in REVIEWED[exercise] and weight is not None and weight not in weights:raise DomainError('Il carico per manubrio deve essere fra i pesi disponibili')
    variants=config['variants']
    if not isinstance(variants,dict) or set(variants)-set(REVIEWED):raise DomainError('Varianti non valide')
    for exercise,variant in variants.items():
        if not isinstance(variant,dict) or set(variant)!= {'variant','executable'} or variant['variant'] not in VARIANTS[exercise] or not isinstance(variant['executable'],bool):raise DomainError('Variante non valida')
    overrides=config['protocol_overrides'];protocols={p['id']:p for p in json.loads((ROOT/'config/workout-protocols.json').read_text())['protocols']}
    if not isinstance(overrides,dict) or set(overrides)-set(protocols):raise DomainError('Protocolli personali non validi')
    for key,params in overrides.items():
        if not isinstance(params,dict) or set(params)-set(protocols[key]['defaults_demo']):raise DomainError('Parametri personali non validi')
        for name,value in params.items():
            finite(value,'Parametro '+name,0,1000 if name in ('reps','sets','rounds') else 86400)
    return config


def personalize(public,settings):
    settings=dict(defaults(),**settings);equipment=set(settings['equipment'] or [])
    protocols={p['id']:p for p in public['protocols']};index={e['source_id']:copy.deepcopy(e) for e in public['exercises']}
    # Compile with reviewed base prerequisites, then report personal feasibility separately.
    for e in index.values():e['equipment_feasible']=True
    sessions=[];unavailable=[]
    for original in public['templates']:
        movements=[e['source_id'] for e in original['exercises']]
        overrides=settings['protocol_overrides'].get(original['protocol_id'],{})
        try:s=compile_session(original['id'],original['name'],protocols[original['protocol_id']],movements,index,overrides)
        except ValueError as exc:raise DomainError('Configurazione del protocollo '+original['protocol_id']+': '+str(exc))
        pending=[];feasible=True;reasons=[]
        if settings['level'] is None:pending.append('level')
        if settings['equipment'] is None:pending.append('equipment')
        if not settings['intensity_confirmed']:pending.append('intensity_confirmed')
        if s['format']=='intervals' and not settings['high_intensity_ready']:pending.append('high_intensity_ready')
        for e in s['exercises']:
            key=e['source_id'];base=index[key];variant=settings['variants'].get(key);required=set(base['requirements'])
            if variant and variant['variant']=='hands_elevated':required.add('panca')
            if variant and variant['variant']=='chair_assisted':required.add('sedia')
            if not required.issubset(equipment):feasible=False;reasons.append(dict(exercise_id=key,code='missing_equipment',equipment=sorted(required-equipment)))
            if key=='inverted-row' and not settings['australian_pullups_setup_verified']:
                feasible=False;pending.append('australian_pullups_setup_verified');reasons.append(dict(exercise_id=key,code='setup_not_confirmed'))
            if variant is None:pending.append('variants.'+key)
            elif not variant['executable']:feasible=False;reasons.append(dict(exercise_id=key,code='variant_not_executable'))
            load=settings['starting_loads_kg'].get(key)
            from load_curve import curve,prescribe
            from diary_service import local_today
            anchor=next((a for a in settings.get('strength_anchors',[]) if a['exercise_key']==key),None)
            history=[r for r in settings.get('_load_history',[]) if r['exercise_id']==key]
            model=curve(anchor,history,local_today())
            intensity=s['intensity'];rir=intensity.get('target',intensity.get('min',2)) if intensity.get('kind')=='rir' else 2
            if not isinstance(rir,(int,float)):rir=2
            prescription=prescribe(model,e.get('repetitions'),rir,settings['available_loads_kg'])
            reference=settings.get('_load_references',{}).get(key)
            if prescription['status']=='available' and reference:
                cap=reference['load_kg']*1.05
                allowed=[w for w in settings['available_loads_kg'] if w<=min(cap,prescription['estimated_kg'])+1e-9]
                prescription.update(max_weekly_load_kg=cap,reference=reference)
                if allowed:prescription['load_kg']=max(allowed)
                else:prescription.update(status='unavailable',reason='Nessun peso disponibile entro il limite settimanale del 5%.')
            if load is None and prescription['status']=='available':load=prescription['load_kg']
            e.update(load_curve=model,load_prescription=prescription,load_source='manual' if key in settings['starting_loads_kg'] and settings['starting_loads_kg'][key] is not None else 'personal_curve')
            if 'manubri' in required:
                if not settings['available_loads_kg']:pending.append('available_loads_kg')
                if load is None or load<=0:pending.append('starting_loads_kg.'+key)
            e.update(name=base['name'],exercise_id=key,media=base['media'],load_kg=load,load_basis='kg_per_dumbbell' if 'manubri' in required else 'external_load_kg',variant=variant['variant'] if variant else None,executable=variant['executable'] if variant else None,requirements=sorted(required))
        s['efficiency']=dict(hard_sets_per_minute=sum(e.get('sets',0) for e in s['exercises'])/s['duration_minutes_assumed'] if s['format'] in ('sets','emom','superset') else None,muscles_per_minute=len({m for key in movements for m in index[key]['primary_muscles']})/s['duration_minutes_assumed'],basis='dose_proxy_not_effectiveness')
        s.update(title=s['name'],equipment_feasible=feasible,high_intensity_ready=settings['high_intensity_ready'],pending_configuration=sorted(set(pending)),personal_configuration_complete=feasible and not pending,personal_level=settings['level'],personal_overrides=copy.deepcopy(overrides),parameter_provenance='user_overrides_with_demo_defaults' if overrides else 'local_demo_assumptions')
        if not feasible:unavailable.append(dict(id=s['id'],reasons=reasons))
        sessions.append(s)
    for e in public['exercises']:
        key=e['source_id'];variant=settings['variants'].get(key);required=set(REVIEWED[key])
        if variant and variant['variant']=='hands_elevated':required.add('panca')
        if variant and variant['variant']=='chair_assisted':required.add('sedia')
        feasible=required.issubset(equipment) and (key!='inverted-row' or settings['australian_pullups_setup_verified']) and (variant is None or variant['executable'])
        e.update(requirements=sorted(required),equipment_feasible=feasible,variant=variant['variant'] if variant else None,executable=variant['executable'] if variant else None,load_kg=settings['starting_loads_kg'].get(key))
    public['pending_custom_equipment']=[dict(equipment=e,reason='Nessun protocollo con prerequisiti verificati nel catalogo corrente') for e in ('aqua_bag','aqua_tank') if e in equipment]
    for protocol in public['protocols']:protocol['efficiency_examples']=[dict(session_id=s['id'],**s['efficiency']) for s in sessions if s['protocol_id']==protocol['id']]
    public.update(templates=sessions,unavailable_sessions=unavailable,configuration=copy.deepcopy(settings))
    return public


def view(settings,public):
    missing=[]
    for key,prompt in [('level','Qual è il tuo livello di allenamento?'),('equipment','Quali attrezzi hai a disposizione?'),('intensity_confirmed','Hai verificato che intensità e volume proposti siano adatti a te?')]:
        if settings.get(key) is None or key=='intensity_confirmed' and not settings[key]:missing.append(dict(field=key,prompt=prompt))
    for e in public['exercises']:
        key=e['source_id']
        if key not in settings['variants']:missing.append(dict(field='variants.'+key,prompt='Quale variante di '+e['name']+' riesci a eseguire?',choices=VARIANTS[key]))
        if 'manubri' in e['requirements']:
            if not settings['available_loads_kg'] and settings.get('equipment') and 'manubri' in settings['equipment']:
                if not any(m['field']=='available_loads_kg' for m in missing):missing.append(dict(field='available_loads_kg',prompt='Quali pesi per singolo manubrio hai disponibili?'))
            if settings['starting_loads_kg'].get(key) is None and not any(x.get('load_kg') is not None for s in public['templates'] for x in s['exercises'] if x['source_id']==key) and settings.get('equipment') and 'manubri' in settings['equipment']:missing.append(dict(field='starting_loads_kg.'+key,prompt='Qual è il carico di partenza per singolo manubrio per '+e['name']+'?'))
    if settings.get('equipment') and 'barra_trazioni' in settings['equipment'] and not settings['australian_pullups_setup_verified']:missing.append(dict(field='australian_pullups_setup_verified',prompt='Hai verificato la barra regolabile per trazioni australiane con i piedi a terra?'))
    if settings.get('equipment') and 'cyclette' in settings['equipment'] and not settings['high_intensity_ready']:missing.append(dict(field='high_intensity_ready',prompt='Se vuoi usare intervalli ad alta intensità, hai verificato di poterli eseguire?',protocol_ids=['cardio_hiit'],optional=True))
    return dict(settings=settings,missing_fields=missing,equipment_options=list(EQUIPMENT),variant_options=VARIANTS,protocols=public['protocols'],sessions=[dict(id=s['id'],demo=s['demo'],equipment_feasible=s['equipment_feasible'],personal_configuration_complete=s['personal_configuration_complete'],pending_configuration=s['pending_configuration']) for s in public['templates']])

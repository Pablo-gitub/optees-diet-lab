"""Compile reviewable workout sessions with an explicit, non-overlapping timeline."""
import copy
import math
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]


def number(value, name, integer=False, positive=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (positive and value==0) or (integer and int(value)!=value):
        raise ValueError('Invalid '+name)
    return value


def compile_session(identifier, name, protocol, movements, index, overrides=None, warmup_seconds=300, cooldown_seconds=180, transition_seconds=30):
    params=copy.deepcopy(protocol['defaults_demo']);params.update(overrides or {})
    allowed=set(protocol['defaults_demo'])
    if set(params)-allowed:raise ValueError('Unknown protocol parameter')
    for key,value in params.items():number(value,key,integer=key in ['sets','reps','rounds'],positive=key in ['sets','reps','rounds','seconds_per_rep','work_seconds','hold_seconds','slot_seconds'])
    for name_,value in [('warmup',warmup_seconds),('cooldown',cooldown_seconds),('transition',transition_seconds)]:number(value,name_)
    if not movements:raise ValueError('No movements')
    exercises=[]
    for key in movements:
        if key not in index or not index[key]['equipment_feasible']:raise ValueError('Missing reviewed prerequisite: '+key)
        exercises.append(index[key])
    fmt=protocol['format']
    if fmt in ['continuous','intervals'] and any(e['source_id'] not in ['stationary-bike','rowing-machine','incline-treadmill-walk','elliptical-trainer'] for e in exercises):raise ValueError('Cardio protocol needs cardio movements')
    if fmt in ['continuous','intervals','isometric'] and len(exercises)!=1:raise ValueError('This protocol requires one movement')
    if fmt=='isometric' and movements!=['plank']:raise ValueError('Isometric compatibility not reviewed')
    if fmt in ['sets','circuit','emom'] and any(e['source_id']=='plank' or e['source_id'] in ['stationary-bike','rowing-machine','incline-treadmill-walk','elliptical-trainer'] for e in exercises):raise ValueError('Dynamic protocol compatibility not reviewed')
    timeline=[];clock=0
    def event(kind,seconds,exercise=None,**details):
        nonlocal clock
        number(seconds,'duration')
        if seconds:
            timeline.append(dict(kind=kind,start_seconds=clock,end_seconds=clock+seconds,duration_seconds=seconds,source_id=exercise,**details));clock+=seconds
    event('warmup',warmup_seconds,note='Mobilità e avvicinamento graduale; dettagli personali da configurare')
    event('setup',transition_seconds)
    dose=[]
    if fmt in ['sets','isometric']:
        for j,e in enumerate(exercises):
            key=e['source_id'];work=params.get('hold_seconds',params.get('reps',0)*params.get('seconds_per_rep',0))
            dose.append(dict(source_id=key,sets=params['sets'],repetitions=params.get('reps'),hold_seconds=params.get('hold_seconds'),work_seconds_per_set=work,rest_seconds_between_sets=params['rest_seconds']))
            for series in range(params['sets']):
                event('hold' if fmt=='isometric' else 'work',work,key,set_number=series+1)
                if series<params['sets']-1:event('rest',params['rest_seconds'],key)
            if j<len(exercises)-1:event('transition',transition_seconds)
    elif fmt=='circuit':
        for e in exercises:dose.append(dict(source_id=e['source_id'],rounds=params['rounds'],work_seconds_per_round=params['work_seconds'],repetitions=None))
        for round_ in range(params['rounds']):
            for j,e in enumerate(exercises):
                event('work',params['work_seconds'],e['source_id'],round_number=round_+1)
                if j<len(exercises)-1:event('transition',params['station_transition_seconds'])
            if round_<params['rounds']-1:
                event('round_rest',params['round_rest_seconds'])
                event('transition',params['station_transition_seconds'])
    elif fmt=='emom':
        work=params['reps']*params['seconds_per_rep'];rest=params['slot_seconds']-work-params['transition_seconds']
        if rest<params['min_rest_seconds']:raise ValueError('EMOM work and transition leave insufficient recovery')
        for e in exercises:dose.append(dict(source_id=e['source_id'],sets=params['rounds'],repetitions=params['reps'],work_seconds_per_set=work,slot_seconds=params['slot_seconds'],rest_seconds=rest))
        for round_ in range(params['rounds']):
            for e in exercises:
                event('work',work,e['source_id'],round_number=round_+1)
                event('transition',params['transition_seconds'])
                event('rest',rest,e['source_id'])
    elif fmt=='continuous':
        event('work',params['work_seconds'],movements[0]);dose.append(dict(source_id=movements[0],work_seconds=params['work_seconds'],repetitions=None))
    elif fmt=='intervals':
        for round_ in range(params['rounds']):
            event('work',params['work_seconds'],movements[0],interval_number=round_+1)
            event('active_recovery',params['recovery_seconds'],movements[0],interval_number=round_+1)
        dose.append(dict(source_id=movements[0],intervals=params['rounds'],work_seconds=params['work_seconds'],recovery_seconds=params['recovery_seconds'],repetitions=None))
    else:raise ValueError('Unknown protocol format')
    event('cooldown',cooldown_seconds)
    totals={kind:sum(e['duration_seconds'] for e in timeline if e['kind']==kind) for kind in set(e['kind'] for e in timeline)}
    # Timed circuits/holds do not invent effective hypertrophy sets.
    coverage={}
    if fmt in ['sets','emom']:
        for e in exercises:
            sets=params.get('sets',params.get('rounds'))
            for muscle in e['primary_muscles']:coverage[muscle]=coverage.get(muscle,0)+sets
            for muscle in e['secondary_muscles']:coverage[muscle]=coverage.get(muscle,0)+sets*.5
    pending=['personal_level_and_variant','personal_intensity_confirmation']
    if any(e['requirements'] and 'manubri' in e['requirements'] for e in exercises):pending.append('load_kg_and_available_weights')
    if fmt=='intervals':pending.append('high_intensity_readiness')
    return dict(id=identifier,name=name,protocol_id=protocol['id'],format=fmt,compatible_goals=protocol['compatible_goals'],demo=True,status='draft_requires_personal_configuration',equipment_feasible=True,pending_configuration=pending,parameters=params,intensity=copy.deepcopy(protocol['intensity']),exercises=dose,timeline=timeline,time_breakdown_seconds=totals,duration_seconds=clock,duration_minutes_assumed=clock/60,source_refs=protocol['source_refs'],parameter_provenance='local_demo_assumptions',score_vector=dict(muscle_coverage_proxy=coverage,time_cost_minutes=clock/60,energy_kcal=None,adherence=None,performance=None),resistance_session=fmt in ['sets','circuit','emom','isometric'],cardio_work_seconds=sum(e['duration_seconds'] for e in timeline if e['kind']=='work') if fmt in ['continuous','intervals'] else 0)


def build_sessions(index):
    catalog=json.loads((ROOT/'config/workout-protocols.json').read_text());protocols={p['id']:p for p in catalog['protocols']}
    definitions=[('strength_dumbbells','Forza con manubri','strength_sets',['dumbbell-floor-press','dumbbell-deadlift']),('hypertrophy_basic','Massa · corpo libero','hypertrophy_sets',['bodyweight-squat','push-up','inverted-row']),('endurance_basic','Resistenza muscolare','endurance_sets',['bodyweight-squat','push-up','inverted-row']),('circuit_bodyweight','Circuito corpo libero','circuit_basic',['bodyweight-squat','push-up','inverted-row']),('emom_bodyweight','EMOM corpo libero','emom_basic',['bodyweight-squat','push-up','inverted-row']),('isometric_core','Isometria · plank','isometric_basic',['plank'])]
    for key,name in [('stationary-bike','Cyclette'),('rowing-machine','Vogatore'),('incline-treadmill-walk','Camminata inclinata'),('elliptical-trainer','Ellittica')]:definitions.append(('continuous_'+key,name+' continuo','cardio_continuous',[key]))
    definitions.append(('interval_bike','Cyclette a intervalli','cardio_hiit',['stationary-bike']))
    sessions=[];unavailable=[]
    for id,name,p,movements in definitions:
        if any(key not in index or not index[key]['equipment_feasible'] for key in movements):
            unavailable.append(dict(id=id,reason='missing_reviewed_equipment',movements=movements));continue
        sessions.append(compile_session(id,name,protocols[p],movements,index))
    return sessions,unavailable


def validate_session(session):
    clock=0.;totals={}
    if session.get('status')!='draft_requires_personal_configuration':raise ValueError('Unknown session status')
    for event in session['timeline']:
        for key in ['start_seconds','end_seconds','duration_seconds']:number(event[key],key)
        if abs(event['start_seconds']-clock)>1e-6 or abs(event['end_seconds']-event['start_seconds']-event['duration_seconds'])>1e-6:raise ValueError('Timeline gap or overlap')
        clock=event['end_seconds'];totals[event['kind']]=totals.get(event['kind'],0)+event['duration_seconds']
    if abs(clock-session['duration_seconds'])>1e-6 or abs(clock/60-session['duration_minutes_assumed'])>1e-6:raise ValueError('Duration mismatch')
    if totals!=session['time_breakdown_seconds']:raise ValueError('Time breakdown mismatch')
    if abs(session['score_vector']['time_cost_minutes']-clock/60)>1e-6:raise ValueError('Time score mismatch')
    return True

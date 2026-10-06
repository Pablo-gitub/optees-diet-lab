"""Reviewed activities, explicit additional sessions and conservative net energy."""
import copy
import datetime as dt
import json
from pathlib import Path
from diary_service import DomainError
ROOT=Path(__file__).resolve().parents[1]
SCENARIOS=('low','central','high')
HEALTH_SOURCE=dict(url='https://www.who.int/europe/news-room/fact-sheets/item/physical-activity',checked_on='2026-10-06',moderate_equivalent_minutes=150,strength_days=2)


def catalog():return copy.deepcopy(json.loads((ROOT/'config/activity-catalog.json').read_text()))


def energy(activity,minutes,weight,health=None):
    from joint_energy import finite
    models=[m for m in (health or {}).get('workout_energy_models',[]) if m.get('activity') in activity['healthkit_types']]
    keys=('kcal_per_min_p20','kcal_per_min_p50','kcal_per_min_p80')
    models=[m for m in models if m.get('status')=='provisional' and m.get('observations',0)>=3 and 0<=m.get('age_days',1000)<=90 and all(finite(m.get(k)) for k in keys) and m[keys[0]]<=m[keys[1]]<=m[keys[2]]]
    if models:
        model=max(models,key=lambda m:(m['observations'],-m['age_days']))
        return dict(status='available',energy_kcal={s:minutes*model[k] for s,k in zip(SCENARIOS,keys)},source='apple_health_activity_quantiles',observations=model['observations'],age_days=model['age_days'],net=True,uncertainty='Quantili empirici provvisori; non intervalli di confidenza.')
    if not finite(weight) or not 30<=weight<=300:return dict(status='unavailable',reason='Manca un peso filtrato recente per stimare l’energia netta dell’attività.')
    central=max(0,activity['met']-1)*weight*minutes/60
    return dict(status='available',energy_kcal={s:central*f for s,f in zip(SCENARIOS,(.7,1,1.3))},source='compendium_met_net',net=True,weight_kg=weight,met=activity['met'],source_url=activity['compendium_url'],uncertainty='Scenari ±30%, euristica in attesa della matrice 8.2; non intervallo di confidenza.')


def snapshot(activity,minutes,weight=None,health=None):
    limits=activity['duration_minutes']
    if isinstance(minutes,bool) or not isinstance(minutes,(int,float)) or minutes%limits['step'] or not limits['min']<=minutes<=limits['max']:raise DomainError('Durata attività non ammessa dal catalogo')
    seconds=minutes*60
    zone=next((g['zone'] for g in activity['goals'] if g['goal_id']=='health'),None)
    return dict(id='activity:'+activity['id'],activity_id=activity['id'],kind='activity',name=activity['name_it'],title=activity['name_it'],protocol_id='activity_catalog',format='activity_continuous',compatible_goals=[g['goal_id'] for g in activity['goals']],demo=True,status='draft_requires_personal_configuration',pending_configuration=[],personal_configuration_complete=True,equipment_feasible=True,high_intensity_ready=False,additional_activity=True,timing_provenance='planned_additional_workout_not_extra_steps',duration_seconds=seconds,duration_minutes_assumed=minutes,activity_duration=copy.deepcopy(limits),health_equivalent_factor=2 if zone=='vigorous' else 1 if zone=='moderate' else 0,healthkit_types=activity['healthkit_types'],parameters=dict(work_seconds=seconds),exercises=[dict(source_id='activity:'+activity['id'],exercise_id='activity:'+activity['id'],name=activity['name_it'],repetitions=None,media=None)],timeline=[dict(kind='work',start_seconds=0,end_seconds=seconds,duration_seconds=seconds,source_id='activity:'+activity['id'])],time_breakdown_seconds=dict(work=seconds),score_vector=dict(muscle_coverage_proxy={},time_cost_minutes=minutes,energy_kcal=None),resistance_session=False,cardio_work_seconds=seconds if any(g['goal_id']=='cardio_fitness' for g in activity['goals']) else 0,source_refs=[dict(url=activity['compendium_url'],checked_on=activity['checked_on'])],energy_estimate=energy(activity,minutes,weight,health))


def candidates(profile,request,health=None):
    activity=profile.get('goals',{}).get('activity',{});priorities=profile.get('goals',{}).get('training_priorities',{})
    explicit=request.get('activities')
    if explicit is not None and (not isinstance(explicit,list) or any(not isinstance(i,str) for i in explicit) or len(explicit)!=len(set(explicit))):raise DomainError('Attività richieste non valide')
    rows=catalog()['activities'];known={a['id'] for a in rows}
    if explicit is not None and set(explicit)-known:raise DomainError('Attività non presente nel catalogo')
    disliked=set(activity.get('disliked_activities',[]))
    if explicit is not None and set(explicit)&disliked:raise DomainError('Attività richiesta anche esclusa nel profilo')
    selected=set(explicit if explicit is not None else activity.get('liked_activities',[]))
    if explicit is None and not any(priorities.values()):return []
    if not selected and explicit is None:selected=known
    weight=profile.get('_filtered_weight_kg')
    maximum=activity.get('max_session_minutes',90)
    return [snapshot(a,a['duration_minutes']['min'],weight,health) for a in rows if a['id'] in selected-disliked and a['duration_minutes']['min']<=maximum and (explicit is not None or any(priorities.get(g['goal_id'],0)>0 for g in a['goals']))]


def materialize(template,minutes,profile,health=None):
    row=next(a for a in catalog()['activities'] if a['id']==template['activity_id'])
    return snapshot(row,minutes,profile.get('_filtered_weight_kg'),health)


def confirm(db,user,profile,data):
    import workout_service as workouts
    if not isinstance(data,dict) or set(data)!={'planned_session_id'}:raise DomainError('Indica solo l’attività pianificata da confermare')
    row=workouts.planned(db,user,data['planned_session_id']);session=json.loads(row['snapshot'])
    if session.get('kind')!='activity':raise DomainError('La conferma rapida è riservata alle attività')
    from diary_service import local_today
    if dt.date.fromisoformat(row['date'])>local_today():raise DomainError('Non puoi confermare un’attività futura','future_activity',409)
    if row['status']=='done':return workouts.day_view(db,user,profile,row['date'])
    if row['status']!='chosen':raise DomainError('Stato attività cambiato','conflict',409)
    from diary_service import valid_date
    valid_date(row['date'],True)
    end=dt.datetime.fromisoformat(workouts.now());start=end-dt.timedelta(seconds=session['duration_seconds'])
    session['timing_provenance']='user_confirmation_assumed_planned_duration'
    db.execute('INSERT INTO workout_log(user_id,date,planned_session_id,session_id,started,ended,snapshot) VALUES(?,?,?,?,?,?,?)',(user,row['date'],row['id'],row['session_id'],start.isoformat(),end.isoformat(),json.dumps(session)))
    db.execute("UPDATE planned_session SET status='done' WHERE id=?",(row['id'],))
    return workouts.day_view(db,user,profile,row['date'])

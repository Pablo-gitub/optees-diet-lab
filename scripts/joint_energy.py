"""Conservative Health scenarios with observed workouts removed before forecasting."""
import datetime as dt
import math
from zoneinfo import ZoneInfo

SCENARIOS=('low','central','high')
ACTIVITIES={
    'continuous_stationary-bike':'HKWorkoutActivityTypeCycling',
    'interval_bike':'HKWorkoutActivityTypeCycling',
    'continuous_rowing-machine':'HKWorkoutActivityTypeRowing',
    'continuous_incline-treadmill-walk':'HKWorkoutActivityTypeWalking',
    'continuous_elliptical-trainer':'HKWorkoutActivityTypeElliptical',
}


def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0


def non_workout_baseline(days,workouts,timezone,today):
    from apple_health import quantile
    zone=ZoneInfo(timezone);eligible=[d for d in days if d['usable_for_baseline']]
    anchor=max((d['date'] for d in eligible),default=None);totals={};bad=set();intervals={}
    for w in workouts:
        start,end=w['start'],w['end']
        if end<=start:bad.add(w['date']);continue
        first=dt.datetime.fromtimestamp(start,zone).date();last=dt.datetime.fromtimestamp(end-1e-6,zone).date()
        for offset in range((last-first).days+1):
            day=first+dt.timedelta(days=offset);date=day.isoformat()
            a=max(start,dt.datetime.combine(day,dt.time(),zone).timestamp());b=min(end,dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),zone).timestamp())
            if not finite(w.get('active_kcal')):bad.add(date);continue
            if any(a<other_b and other_a<b for other_a,other_b in intervals.get(date,[])):bad.add(date)
            intervals.setdefault(date,[]).append((a,b));totals[date]=totals.get(date,0)+w['active_kcal']*(b-a)/(end-start)
    selected=[];excluded=[]
    for d in eligible:
        if anchor is None or not dt.date.fromisoformat(anchor)-dt.timedelta(days=27)<=dt.date.fromisoformat(d['date'])<=dt.date.fromisoformat(anchor):continue
        removed=totals.get(d['date'],0)
        if d['date'] in bad or removed>d['active_kcal']+.01:
            excluded.append(d['date']);continue
        selected.append(dict(date=d['date'],total_kcal=d['total_estimated_kcal'],observed_workout_kcal=removed,non_workout_kcal=d['total_estimated_kcal']-removed))
    values=[d['non_workout_kcal'] for d in selected];age=(today-dt.date.fromisoformat(anchor)).days if anchor else None
    return dict(status='available' if len(values)>=7 and age is not None and 0<=age<=14 else 'insufficient_or_stale',end_date=anchor,valid_days=len(values),staleness_days=age,**{key+'_kcal':round(quantile(values,p),3) if values else None for key,p in zip(SCENARIOS,(.2,.5,.8))},source='apple_health_total_minus_observed_workouts',excluded_days=excluded,daily=selected,workout_inventory_complete=True,assumption='Workout energy is distributed uniformly across its UTC interval; ordinary activity remains included.')


def day_scenarios(health,sessions,activity_map=None):
    baseline=(health or {}).get('non_workout_consumption_scenarios',{})
    if baseline.get('status')!='available' or not all(finite(baseline.get(s+'_kcal')) for s in SCENARIOS):return dict(status='unavailable',reason='Base Salute senza allenamenti insufficiente o non recente.')
    values={s:baseline[s+'_kcal'] for s in SCENARIOS};models={m['activity']:m for m in (health or {}).get('workout_energy_models',[])};mapping=dict(ACTIVITIES,**(activity_map or {}));estimates=[]
    for session in sessions:
        identifier=session['session_id'];activity=mapping.get(identifier);model=models.get(activity)
        keys=('kcal_per_min_p20','kcal_per_min_p50','kcal_per_min_p80')
        if model is None or model.get('status')!='provisional' or model.get('observations',0)<3 or not 0<=model.get('age_days',1000)<=90 or not all(finite(model.get(k)) for k in keys):return dict(status='unavailable',reason='Modello energetico recente mancante per '+identifier,missing_session_id=identifier)
        if not model[keys[0]]<=model[keys[1]]<=model[keys[2]]:return dict(status='unavailable',reason='Quantili energetici incoerenti')
        minutes=session['session']['duration_seconds']/60
        energy={s:minutes*model[k] for s,k in zip(SCENARIOS,keys)}
        for s in SCENARIOS:values[s]+=energy[s]
        estimates.append(dict(session_id=identifier,activity=activity,duration_seconds=session['session']['duration_seconds'],energy_kcal=energy,observations=model['observations'],age_days=model['age_days'],source='apple_health_activity_quantiles',assumption='Rate scaled to complete session duration, including recovery; provisional estimate.'))
    return dict(status='available',consumption_kcal=values,non_workout_kcal={s:baseline[s+'_kcal'] for s in SCENARIOS},sessions=estimates,source=baseline['source'],double_counting_prevented=True,uncertainty='Three correlated empirical scenarios; not confidence intervals.')

"""Opt-in conservative activity columns for the portion-first rebalance MILP."""
import copy
import math
import activity_service
from diary_service import DomainError
from multiobjective_day import extend
LIMITS=dict(maximum_activity_share=.5,maximum_added_minutes_per_day=45,maximum_added_activities_per_day=1,energy_scenario='low')


def validate(value):
    value=copy.deepcopy(value) if value is not None else dict(mode='none',max_minutes_per_day=45)
    if not isinstance(value,dict) or set(value)-{'mode','max_minutes_per_day'} or value.get('mode') not in ('none','walk','liked'):raise DomainError('Scegli attività none, walk oppure liked')
    maximum=value.setdefault('max_minutes_per_day',45)
    if isinstance(maximum,bool) or not isinstance(maximum,int) or not 5<=maximum<=45 or maximum%5:raise DomainError('Durata aggiuntiva: da 5 a 45 minuti a passi di 5')
    return value


def intense(view):
    for session in view.get('workouts',[]):
        if session.get('status')=='skipped':continue
        if session.get('kind')=='activity':
            row=next((a for a in activity_service.catalog()['activities'] if a['id']==session.get('activity_id')),None)
            if not row or row['met']>=6:return True
        else:
            # Without a complete intensity snapshot we cannot certify a light session.
            return True
    return False


def add(problem,views,profile,option,rows,baseline,surplus,low_by_date,health=None):
    """Each candidate is one integer five-minute duration + optional presence."""
    choices=[];reasons=[]
    if option['mode']=='none':return choices,reasons
    preferences=profile.get('goals',{}).get('activity',{})
    selected={'walking_moderate'} if option['mode']=='walk' else set(preferences.get('liked_activities',[]))
    selected-=set(preferences.get('disliked_activities',[]))
    maximum=min(45,option['max_minutes_per_day'],preferences.get('max_session_minutes',90))
    for view in views:
        date=view['date']
        if intense(view):reasons.append(dict(date=date,reason='Sessione intensa o intensità non verificabile già pianificata.'));continue
        if len([s for s in view.get('workouts',[]) if s['status']!='skipped'])>=preferences.get('max_sessions_per_day',1):reasons.append(dict(date=date,reason='Numero personale massimo di sessioni già raggiunto.'));continue
        for activity in activity_service.catalog()['activities']:
            bounds=activity['duration_minutes']
            if activity['id'] not in selected or maximum<bounds['min']:continue
            template=activity_service.snapshot(activity,bounds['min'],profile.get('_filtered_weight_kg'),health)
            energy=template['energy_estimate']
            if energy['status']!='available':reasons.append(dict(date=date,reason=energy['reason']));continue
            step=bounds['step'];minimum=math.ceil(bounds['min']/step);upper=math.floor(min(maximum,bounds['max'])/step)
            y=extend(problem,dict(name='rebalance_activity_on_'+str(len(choices)),lb=0,ub=1,integrality='B'))
            q=extend(problem,dict(name='rebalance_activity_units_'+str(len(choices)),lb=0,ub=upper,integrality='I'))
            for relation,coefficient in (('<=',upper),('>=',minimum)):
                row=[0.]*len(problem['variables']);row[q]=1;row[y]=-coefficient
                problem['constraints'].append(dict(coefficients=row,relation=relation,rhs=0))
            choices.append(dict(date=date,activity=activity,template=template,y=y,q=q,step=step,energy_per_unit=energy['energy_kcal']['low']*step/bounds['min']))
    size=len(problem['variables'])
    for date in rows:rows[date].extend([0.]*(size-len(rows[date])))
    activity_rows={date:[0.]*size for date in rows}
    for c in choices:activity_rows[c['date']][c['q']]=c['energy_per_unit']
    for date,row in activity_rows.items():
        on=[0.]*size
        for c in choices:
            if c['date']==date:on[c['y']]=1
        problem['constraints'].append(dict(coefficients=on,relation='<=',rhs=1))
        # Additional expenditure raises the minimum food energy needed to retain
        # the already established maximum net deficit of 500 kcal per day.
        problem['constraints'].append(dict(coefficients=[a-b for a,b in zip(rows[date],row)],relation='>=',rhs=low_by_date[date]-500))
    total=[sum(r[i] for r in activity_rows.values()) for i in range(size)]
    food=[sum(r[i] for r in rows.values()) for i in range(size)]
    # Activity cannot exceed food correction: <= 50% of actual combined correction.
    problem['constraints'].append(dict(coefficients=[a+b for a,b in zip(food,total)],relation='<=',rhs=sum(baseline.values())))
    problem['constraints'].append(dict(coefficients=total,relation='<=',rhs=surplus*.5))
    for c in choices:rows[c['date']][c['q']]-=c['energy_per_unit']
    return choices,reasons


def decode(choices,values,profile,health=None):
    by={}
    for c in choices:
        if values[c['y']]<=.5:continue
        minutes=round(values[c['q']])*c['step'];session=activity_service.snapshot(c['activity'],minutes,profile.get('_filtered_weight_kg'),health)
        by.setdefault(c['date'],[]).append(dict(activity_id=c['activity']['id'],minutes=minutes,energy_kcal=session['energy_estimate']['energy_kcal'],source=session['energy_estimate']['source'],_session=session))
    return by

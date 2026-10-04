"""Owner-scoped progress, missing-aware adherence and short-horizon energy checks."""
import datetime as dt
import math
import statistics
from zoneinfo import ZoneInfo
import diary_service as diary

PARAMETERS=dict(version='progress-v2',filter_input='daily_median',filter_method='scalar_kalman',trend_method='weekly_least_squares_filtered',ema_half_life_days=7,kalman_process_variance_kg2_per_day=.01,kalman_observation_variance_kg2=.04,kalman_initial_variance_kg2=.25,filter_reset_gap_days=14,minimum_complete_week_days=5,meal_kcal_tolerance_fraction=.1,adherence_threshold=.8,energy_equivalent_kcal_per_kg=7700,weight_response_tolerance_kg=.3)


def number(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def unavailable(reason,**fields):return dict(status='insufficient_data',reason=reason,**fields)
def monday(day):return day-dt.timedelta(days=day.weekday())
def days(start):return [(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat() for i in range(7)]


def weight_series(measurements,as_of):
    cutoff=(as_of-dt.timedelta(days=365)).isoformat()
    raw=sorted([dict(p) for p in measurements if p.get('kind')=='weight' and p.get('unit')=='kg' and number(p.get('value')) and 1<=p['value']<=500 and cutoff<=p['date']<=as_of.isoformat()],key=lambda p:(p['date'],str(p.get('timestamp','')),p.get('id',0)))
    grouped={}
    for p in raw:grouped.setdefault(p['date'],[]).append(p)
    daily=[];ema=None;filtered=None;variance=None;previous=None
    for date,items in grouped.items():
        manual=[p for p in items if p['source']=='manual'];chosen=manual or items
        value=statistics.median(p['value'] for p in chosen);day=dt.date.fromisoformat(date);gap=(day-previous).days if previous else 0
        reset=previous is None or gap>PARAMETERS['filter_reset_gap_days']
        if reset:ema=filtered=value;variance=PARAMETERS['kalman_initial_variance_kg2']
        else:
            alpha=1-2**(-gap/PARAMETERS['ema_half_life_days']);ema+=alpha*(value-ema)
            predicted=variance+gap*PARAMETERS['kalman_process_variance_kg2_per_day'];gain=predicted/(predicted+PARAMETERS['kalman_observation_variance_kg2']);filtered+=gain*(value-filtered);variance=(1-gain)*predicted
        daily.append(dict(date=date,value=value,ema_kg=ema,filtered_kg=filtered,filter_variance_kg2=variance,raw_count=len(items),aggregation_count=len(chosen),source='manual' if manual else 'apple_health',reset=reset,gap_days=gap));previous=day
    fields=dict(raw_points=raw,daily_points=daily,points=[[p['date'],round(p['filtered_kg'],4)] for p in daily],ema_points=[[p['date'],round(p['ema_kg'],4)] for p in daily],parameters=PARAMETERS,trend_7d=None)
    if not daily:return unavailable('Nessuna pesata disponibile.',**fields)
    latest=daily[-1];age=(as_of-dt.date.fromisoformat(latest['date'])).days
    prior=next((p for p in daily if p['date']==(dt.date.fromisoformat(latest['date'])-dt.timedelta(days=7)).isoformat()),None)
    fields.update(value=latest['value'],unit='kg',date=latest['date'],source=latest['source'],age_days=age,trend_status='available' if prior else 'insufficient_data')
    if prior:
        window=[p for p in daily if prior['date']<=p['date']<=latest['date']]
        xs=[(dt.date.fromisoformat(p['date'])-dt.date.fromisoformat(prior['date'])).days for p in window];ys=[p['filtered_kg'] for p in window]
        mx=statistics.mean(xs);my=statistics.mean(ys)
        fields['trend_7d']=round(7*sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs),4)
    else:fields['trend_reason']='Manca una pesata sette giorni prima; nessuna interpolazione.'
    if age>14:return unavailable('Ultima pesata più vecchia di 14 giorni.',**fields)
    return dict(status='available',**fields)


def contexts(db,user,start):
    end=days(start)[-1];result={}
    for row in db.execute("SELECT day_context FROM week_plan WHERE user_id=? AND status='active' AND week_start<=? AND date(week_start,'+6 days')>=? ORDER BY created,id",(user,end,start)):
        import json
        result.update({d:c for d,c in json.loads(row['day_context'] or '{}').items() if start<=d<=end})
    return result


def week_analysis(db,user,profile,start,as_of):
    diary.valid_date(start);views=[diary.day_view(db,user,profile,d) for d in days(start)];context=contexts(db,user,start)
    complete=[];full=[];adherent=0;denominator=0;missing=[]
    past=[v for v in views if v['date']<as_of.isoformat()]
    for v in past:
        planned=[m for m in v['meals'] if m['planned'] is not None]
        if not planned:missing.append(dict(date=v['date'],reason='no_plan'));continue
        if any(m['eaten'] is None or not number(m['planned']['kcal']) or not number(m['eaten']['kcal']) for m in planned):missing.append(dict(date=v['date'],reason='incomplete_diary_or_nutrients'));continue
        complete.append(v['date'])
        for m in planned:
            denominator+=1
            expected=m['planned']['kcal'];actual=m['eaten']['kcal']
            adherent+=m['state']=='as_planned' or abs(actual-expected)<=PARAMETERS['meal_kcal_tolerance_fraction']*expected
        c=context.get(v['date'],{})
        full_scope=c.get('scope')=='full_day_planned_meals' or len(planned)==5
        if full_scope and v['totals']['eaten'] is not None and all(number(n) for n in v['totals']['eaten'].values()):full.append(v)
    coverage=dict(complete_days=len(complete),required_days=5,total_days=7,elapsed_days=len(past),complete_dates=complete,missing_days=missing)
    diet=dict(status='available',value=adherent/denominator,adherent_meals=adherent,assessed_meals=denominator,coverage=coverage) if len(complete)>=5 else unavailable('Servono almeno cinque giorni completi di diario nella settimana.',value=None,coverage=coverage)
    kcal=dict(status='available',eaten_avg=sum(v['totals']['eaten']['kcal'] for v in full)/len(full),target=sum(v['targets']['kcal']['target'] for v in full)/len(full),days=len(full),dates=[v['date'] for v in full]) if len(full)>=5 else unavailable('Servono almeno cinque giornate intere con nutrienti noti.',eaten_avg=None,target=None,days=len(full))
    sessions=[s for v in views for s in v['workouts'] if s['planned_session_id'] is not None]
    due=[s for v in past for s in v['workouts'] if s['planned_session_id'] is not None]
    free_done=sum(s['status']=='done' for v in past for s in v['workouts'] if s['planned_session_id'] is None)
    done=sum(s['status']=='done' for s in due);unknown=sum(s['status'] not in ('done','skipped') for s in due)
    logged_done_total=sum(s['status']=='done' for v in views if v['date']<=as_of.isoformat() for s in v['workouts'])
    free_done_total=sum(s['status']=='done' for v in views if v['date']<=as_of.isoformat() for s in v['workouts'] if s['planned_session_id'] is None)
    training_fields=dict(logged_done_total=logged_done_total,free_done_total=free_done_total,value=None,planned=len(sessions),due=len(due),done=done,skipped=sum(s['status']=='skipped' for s in due),unknown=unknown,free_done=free_done)
    if len(past)<5:training=unavailable('Settimana ancora troppo incompleta per valutare gli allenamenti.',**training_fields)
    elif not due:training=unavailable('Nessuna sessione pianificata da valutare.',**training_fields)
    elif unknown:training=unavailable('Alcune sessioni passate non sono concluse né dichiarate saltate.',**training_fields)
    else:training=dict(training_fields,status='available',value=done/len(due))
    return dict(week_start=start,week_end=days(start)[-1],status=diet['status'],**({'reason':diet['reason']} if diet['status']!='available' else {}),diet=diet,training=training,kcal_average=kcal,coverage=coverage,days=views,contexts=context)


def expected_week(week,weight):
    start=week['week_start'];dates=days(start);by_date={p['date']:p for p in weight['daily_points']}
    anchor=by_date.get(start)
    if not anchor:return unavailable('Manca la pesata all’inizio della settimana.',points=[])
    low=central=high=anchor['filtered_kg'];points=[dict(date=start,low_kg=low,central_kg=central,high_kg=high)]
    for date in dates:
        c=week['contexts'].get(date,{});forecast=c.get('progress_forecast',{});energy=forecast.get('energy_scenarios',{})
        values=energy.get('consumption_kcal',{})
        if not forecast.get('valid') or forecast.get('scope')!='full_day_planned_meals' or energy.get('status')!='available' or not number(forecast.get('planned_kcal')) or any(not number(values.get(s)) for s in ('low','central','high')):
            return unavailable('Previsione completa del piano applicato mancante o invalidata.',points=[])
        intake=forecast['planned_kcal'];scale=PARAMETERS['energy_equivalent_kcal_per_kg']
        low+=(intake-values['high'])/scale;central+=(intake-values['central'])/scale;high+=(intake-values['low'])/scale
        points.append(dict(date=(dt.date.fromisoformat(date)+dt.timedelta(days=1)).isoformat(),low_kg=low,central_kg=central,high_kg=high))
    return dict(status='available',points=points,model='short_horizon_energy_accounting_not_physiological_prediction',anchor=dict(date=start,weight_kg=anchor['filtered_kg'],source=anchor['source']),parameters=dict(kcal_per_kg=scale),provenance='applied_joint_plan_scenarios_without_double_counting')


def comparison(week,weight,expected,as_of):
    if dt.date.fromisoformat(week['week_end'])>=as_of:return unavailable('La settimana non è ancora conclusa.',classification=None)
    if week['diet']['status']!='available':return unavailable('Copertura del diario insufficiente per distinguere aderenza e risposta.',classification=None)
    training=week['training']
    if training['planned'] and training['status']!='available':return unavailable('Esecuzione degli allenamenti non sufficientemente registrata.',classification=None)
    not_followed=week['diet']['value']<.8 or training['status']=='available' and training['value']<.8 or training.get('free_done',0)>0
    if week.get('days'):
        full=week['kcal_average'].get('dates',[])
        intake_deviation=[abs(v['totals']['eaten']['kcal']-v['totals']['planned']['kcal'])/max(v['totals']['planned']['kcal'],1) for v in week['days'] if v['date'] in full]
        if intake_deviation and sum(intake_deviation)/len(intake_deviation)>.1:not_followed=True
    if not_followed:return dict(status='available',classification='plan_not_followed',reason='Le registrazioni mostrano scostamenti dal piano; la risposta corporea non è attribuibile al solo modello.',response_assessment='not_assessed')
    if week.get('kcal_average',{}).get('days',7)<7:return unavailable('Servono sette giornate intere per confrontare la risposta.',classification=None)
    if expected['status']!='available':return unavailable(expected['reason'],classification=None)
    end=(dt.date.fromisoformat(week['week_end'])+dt.timedelta(days=1)).isoformat();points={p['date']:p for p in weight['daily_points']}
    if end not in points:return unavailable('Manca la pesata di fine settimana.',classification=None)
    a=points[week['week_start']];b=points[end];predicted=expected['points'][-1]
    tolerance=max(.3,2*math.sqrt(a['filter_variance_kg2']+b['filter_variance_kg2']))
    differs=b['filtered_kg']<predicted['low_kg']-tolerance or b['filtered_kg']>predicted['high_kg']+tolerance
    return dict(status='available',classification='response_differs_from_expected' if differs else 'within_expected_uncertainty',reason='Scarto rispetto a una stima breve, non prova di una causa metabolica.' if differs else 'Peso filtrato compatibile con gli scenari e il rumore del filtro.',observed_delta_kg=b['filtered_kg']-a['filtered_kg'],expected_delta_kg=predicted['central_kg']-a['filtered_kg'],observed_end_kg=b['filtered_kg'],expected_end_kg=predicted['central_kg'],tolerance_kg=tolerance)


def progress(db,user,profile,measurements,as_of,weeks=8):
    diary.integer(weeks,1,52);weight=weight_series(measurements,as_of);analyses=[];series=[]
    start=monday(as_of)
    for offset in reversed(range(weeks)):
        week=week_analysis(db,user,profile,(start-dt.timedelta(days=offset*7)).isoformat(),as_of)
        expected=expected_week(week,weight);week['comparison']=comparison(week,weight,expected,as_of);week['expected_weight']=expected
        week.pop('days');week.pop('contexts');analyses.append(week)
        if expected['status']=='available':series.append(dict(week_start=week['week_start'],**expected))
    expected=dict(status='available',segments=series) if series else unavailable('Nessuna settimana con previsione completa e peso iniziale.',segments=[])
    return dict(as_of=as_of.isoformat(),weight=weight,expected_weight=expected,weeks=analyses,parameters=PARAMETERS)


def summary(analysis):
    week=analysis['weeks'][-1];diet=week['diet'];training=week['training']
    fields=dict(diet=diet['value'],training=training['value'],diet_detail=diet,training_detail=training,week_start=week['week_start'])
    adherence=dict(status='available',**fields) if diet['status']=='available' or training['status']=='available' else unavailable('Copertura settimanale insufficiente; vedere dieta e allenamento.',**fields)
    workout_fields={k:training[k] for k in ('done','planned','free_done','unknown','skipped')}
    workout_fields['done']=training['logged_done_total'];workout_fields['free_done']=training['free_done_total']
    # Counts of explicit completed logs are valid even when adherence is unknown.
    counts=dict(status='available',**workout_fields) if training['planned'] or training['logged_done_total'] else unavailable('Nessun allenamento pianificato o registrato.',**workout_fields)
    return dict(weight=analysis['weight'],adherence_week=adherence,kcal_average=week['kcal_average'],workouts=counts)


def invalidate_forecast(db,user,date,reason='plan_changed'):
    import json
    rows=db.execute("SELECT id,day_context FROM week_plan WHERE user_id=? AND status='active' AND week_start<=? AND date(week_start,'+6 days')>=?",(user,date,date)).fetchall()
    for row in rows:
        context=json.loads(row['day_context'] or '{}');forecast=context.get(date,{}).get('progress_forecast')
        if forecast:
            forecast.update(valid=False,invalidation_reason=reason)
            db.execute('UPDATE week_plan SET day_context=? WHERE id=?',(json.dumps(context),row['id']))

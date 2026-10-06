"""Personal Epley curves; provisional bounds are explicitly heuristic."""
import datetime as dt
import math
import statistics

PARAMETERS=dict(version='load-curve-v1',fallback_k=30,k_min=10,k_max=60,ema_alpha=.3,last_sets=12,winsor_fraction=.2,max_weekly_increase=.05,evidence='heuristic_pending_8.2')


def curve(anchor,history=(),today=None):
    today=today or dt.date.today();warnings=[]
    points=[dict(anchor[key],rir=0,source='strength_anchor') for key in ('heavy','light') if (anchor or {}).get(key) and anchor[key]['kg']>0]
    logged=[]
    for row in history:
        if not isinstance(row.get('kg'),(int,float)) or isinstance(row['kg'],bool) or not math.isfinite(row['kg']) or row['kg']<=0 or not isinstance(row.get('reps'),(int,float)) or not 1<=row['reps']<=50:continue
        try:date=dt.date.fromisoformat(row['date'])
        except (ValueError,TypeError,KeyError):continue
        if date>today:continue
        rir=row.get('rir')
        if rir is None and row.get('rpe') is not None:rir=max(0,min(4,10-row['rpe']))
        if rir is None:continue
        if not isinstance(rir,(int,float)) or not math.isfinite(rir):continue
        logged.append(dict(kg=row['kg'],reps=row['reps'],date=row['date'],rir=max(0,min(4,rir)),source='performed_set'))
    logged=sorted(logged,key=lambda p:p['date'])[-PARAMETERS['last_sets']:]
    if not points and not logged:return dict(status='unavailable',reason='Mancano serie con carico esterno e ripetizioni/RIR verificabili.',parameters=PARAMETERS)
    k=30
    if len(points)==2:
        a,b=points
        candidate=(b['kg']*b['reps']-a['kg']*a['reps'])/(a['kg']-b['kg']) if a['kg']!=b['kg'] else None
        if candidate is not None and PARAMETERS['k_min']<=candidate<=PARAMETERS['k_max']:k=candidate
        else:warnings.append('Due serie incoerenti o k fuori dall’intervallo euristico 10–60: usato k=30.')
    initial=statistics.median(p['kg']*(1+p['reps']/k) for p in points) if points else logged[0]['kg']*(1+(logged[0]['reps']+logged[0]['rir'])/k)
    def moving(rows):
        if not rows:return initial
        values=[p['kg']*(1+(p['reps']+p['rir'])/k) for p in rows]
        median=statistics.median(values);estimate=initial
        for value in values:estimate=.7*estimate+.3*max(median*.8,min(median*1.2,value))
        return estimate
    monday=today-dt.timedelta(days=today.weekday())
    previous=[p for p in logged if p['date']<monday.isoformat()]
    reference=moving(previous)
    raw=moving(logged);M=min(raw,reference*1.05)
    if M<raw:warnings.append('Aumento limitato al 5% rispetto al riferimento della settimana conclusa; rigenerare non aumenta il limite.')
    return dict(status='available',M=M,k=k,raw_M=raw,reference_M=reference,week_start=monday.isoformat(),max_M=reference*1.05,warnings=warnings,parameters=PARAMETERS,data_used=points+logged,assumption='Serie di riferimento considerate massime; RIR dei registri limitato a 0–4. Pesi esterni nella stessa unità dichiarata.')


def prescribe(model,reps,rir,available):
    if model.get('status')!='available':return dict(status='unavailable',reason=model.get('reason','Curva non disponibile.'))
    if reps is None or not isinstance(reps,(int,float)) or reps<=0:return dict(status='unavailable',reason='Il protocollo a tempo non specifica ripetizioni: nessun carico inventato.')
    desired=model['M']/(1+(reps+max(0,min(4,rir)))/model['k'])
    valid=[w for w in available if isinstance(w,(int,float)) and not isinstance(w,bool) and math.isfinite(w) and 0<w<=desired+1e-9]
    if not valid:return dict(status='unavailable',reason='Nessun carico disponibile per difetto della stima.',estimated_kg=desired)
    return dict(status='available',load_kg=max(valid),estimated_kg=desired,reps=reps,rir=rir,rounding='down',curve=model)

"""Private, streaming Apple Health import and conservative energy summaries."""
import collections
import datetime as dt
import hashlib
import heapq
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo

VERSION='apple-health-v1'
ANALYSIS_VERSION='health-analysis-v1.1'
TYPES={
 'HKQuantityTypeIdentifierActiveEnergyBurned':'active_energy',
 'HKQuantityTypeIdentifierBasalEnergyBurned':'resting_energy',
 'HKQuantityTypeIdentifierBodyMass':'weight',
 'HKQuantityTypeIdentifierHeight':'height',
 'HKQuantityTypeIdentifierBodyFatPercentage':'body_fat',
 'HKQuantityTypeIdentifierBodyMassIndex':'bmi',
 'HKQuantityTypeIdentifierRestingHeartRate':'resting_hr',
 'HKQuantityTypeIdentifierVO2Max':'vo2max',
}
ENERGY={'active_energy','resting_energy'}


def timestamp(value):
    parsed=dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:raise ValueError('Missing timezone')
    return parsed.timestamp()


def normalize(kind,value,unit):
    value=float(value)
    if not math.isfinite(value) or value<0:raise ValueError('Invalid number')
    factors={'active_energy':{'kcal':1,'kJ':1/4.184,'J':1/4184},'resting_energy':{'kcal':1,'kJ':1/4.184,'J':1/4184},'weight':{'kg':1,'lb':.45359237,'g':.001},'height':{'cm':1,'m':100,'in':2.54,'ft':30.48},'body_fat':{'%':1},'bmi':{'count':1},'resting_hr':{'count/min':1},'vo2max':{'mL/min·kg':1,'ml/kg/min':1}}
    if kind=='body_fat' and value>1:raise ValueError('HealthKit percent must be a fraction 0..1')
    if unit not in factors[kind]:raise ValueError('Unsupported unit')
    return value*factors[kind][unit]


def priority(source,device=''):
    if 'watch' in (source+' '+device).lower():return 3
    if 'iphone' in (source+' '+device).lower():return 2
    return 1


def split_days(start,end,value,timezone):
    if end<=start:raise ValueError('Nonpositive energy interval')
    if end-start>7*86400:raise ValueError('Energy interval too long')
    cursor=start
    while cursor<end:
        date=dt.datetime.fromtimestamp(cursor,timezone).date()
        boundary=dt.datetime.combine(date+dt.timedelta(days=1),dt.time(),timezone).timestamp()
        stop=min(end,boundary)
        yield date.isoformat(),cursor,stop,value*(stop-cursor)/(end-start)
        cursor=stop


def resolve_intervals(rows):
    """One source per instant, uniform allocation within each interval, no sums of overlaps."""
    events=[];active=set();queue=[];total=covered=overlap=0.;sources=collections.defaultdict(float)
    for i,r in enumerate(rows):
        if r['end']<=r['start']:continue
        events.extend([(r['start'],1,i),(r['end'],-1,i)])
    events.sort();previous=None;index=0
    while index<len(events):
        moment=events[index][0]
        while queue and queue[0][-1] not in active:heapq.heappop(queue)
        if previous is not None and moment>previous and queue:
            r=rows[queue[0][-1]];duration=moment-previous;amount=r['value']*duration/(r['end']-r['start'])
            total+=amount;covered+=duration;sources[r['source']]+=amount
            if len(active)>1:overlap+=duration
        while index<len(events) and events[index][0]==moment:
            _,kind,i=events[index];r=rows[i]
            if kind==1:
                active.add(i);heapq.heappush(queue,(-r['priority'],r['end']-r['start'],-r.get('created',0),i))
            else:active.discard(i)
            index+=1
        previous=moment
    return dict(value=total,covered_seconds=covered,overlap_seconds=overlap,sources=dict(sources))


def quantile(values,p):
    values=sorted(values);pos=(len(values)-1)*p;lo=int(pos);hi=math.ceil(pos)
    return values[lo]+(values[hi]-values[lo])*(pos-lo)


def summarize(db,timezone='Europe/Rome',today=None):
    zone=ZoneInfo(timezone);today=today or dt.datetime.now(zone).date()
    days=[]
    for (date,) in db.execute('SELECT DISTINCT day FROM energy ORDER BY day'):
        types={}
        for kind in sorted(ENERGY):
            rows=[dict(start=r[0],end=r[1],value=r[2],source=r[3],priority=r[4],created=r[5]) for r in db.execute('SELECT start,end,value,source,priority,created FROM energy WHERE day=? AND kind=?',(date,kind))]
            types[kind]=resolve_intervals(rows)
        day=dt.date.fromisoformat(date)
        expected=(dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),zone)-dt.datetime.combine(day,dt.time(),zone)).total_seconds()
        # Use UTC timestamps for DST day lengths (23/25 hours).
        expected=dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),zone).timestamp()-dt.datetime.combine(day,dt.time(),zone).timestamp()
        usable=date<today.isoformat() and types['resting_energy']['covered_seconds']>=expected*20/24 and types['active_energy']['covered_seconds']>0
        days.append(dict(date=date,active_kcal=round(types['active_energy']['value'],2),resting_kcal=round(types['resting_energy']['value'],2),total_estimated_kcal=round(sum(t['value'] for t in types.values()),2),usable_for_baseline=usable,resting_coverage_fraction=round(types['resting_energy']['covered_seconds']/expected,4),active_covered_seconds=types['active_energy']['covered_seconds'],sources={k:t['sources'] for k,t in types.items()},overlap_seconds={k:t['overlap_seconds'] for k,t in types.items()}))
    eligible=[d for d in days if d['usable_for_baseline']]
    anchor=dt.date.fromisoformat(eligible[-1]['date']) if eligible else None
    windows=[]
    for width in [7,14,28]:
        selected=[d for d in eligible if anchor and anchor-dt.timedelta(days=width-1)<=dt.date.fromisoformat(d['date'])<=anchor]
        values=[d['total_estimated_kcal'] for d in selected]
        windows.append(dict(days=width,valid_days=len(values),end_date=anchor.isoformat() if anchor else None,mean_daily_estimated_kcal=round(sum(values)/len(values),2) if values else None,weekly_equivalent_estimated_kcal=round(7*sum(values)/len(values),2) if values else None,p20=round(quantile(values,.2),2) if values else None,p50=round(quantile(values,.5),2) if values else None,p80=round(quantile(values,.8),2) if values else None))
    baseline=next(w for w in windows if w['days']==28)
    stale=(today-anchor).days if anchor else None
    scenarios=dict(status='available' if baseline['valid_days']>=7 and stale is not None and stale<=14 else 'insufficient_or_stale',low_kcal=baseline['p20'],central_kcal=baseline['p50'],high_kcal=baseline['p80'],valid_days=baseline['valid_days'],staleness_days=stale,kind='empirical_daily_variation_not_confidence_interval',note='Consumo stimato del dispositivo, non apporto calorico consigliato; nessun obiettivo personale viene modificato automaticamente.')
    measures={}
    for kind in sorted(set(TYPES.values())-ENERGY):
        row=db.execute('SELECT value,unit,end,source FROM measures WHERE kind=? ORDER BY end DESC LIMIT 1',(kind,)).fetchone()
        if row:measures[kind]=dict(value=row[0]*100 if kind=='body_fat' else row[0],unit=row[1],raw_value=row[0],unit_note='HealthKit fraction converted to percentage points' if kind=='body_fat' else None,date=dt.datetime.fromtimestamp(row[2],zone).date().isoformat(),source=row[3],age_days=(today-dt.datetime.fromtimestamp(row[2],zone).date()).days)
    weights=[dict(value=r[0],date=dt.datetime.fromtimestamp(r[1],zone).date().isoformat(),source=r[2]) for r in db.execute("SELECT value,end,source FROM measures WHERE kind='weight' ORDER BY end DESC LIMIT 90")]
    workouts=[];rates=collections.defaultdict(list)
    raw_workouts={}
    for row in db.execute('SELECT payload FROM workouts ORDER BY start'):
        candidate=json.loads(row[0]);key=(candidate['activity'],candidate['start'],candidate['end'])
        if key not in raw_workouts or priority(candidate['source'])>priority(raw_workouts[key]['source']):raw_workouts[key]=candidate
    for w in sorted(raw_workouts.values(),key=lambda w:w['start']):
        w=dict(w);w['active_energy_kind']='workout_statistic' if w.get('active_kcal') is not None else None
        if w.get('active_kcal') is None:
            segments=[]
            for r in db.execute("SELECT start,end,value,source,priority,created FROM energy WHERE kind='active_energy' AND end>? AND start<?",(w['start'],w['end'])):
                a=max(r[0],w['start']);b=min(r[1],w['end'])
                segments.append(dict(start=a,end=b,value=r[2]*(b-a)/(r[1]-r[0]),source=r[3],priority=r[4],created=r[5]))
            energy=resolve_intervals(segments)
            fraction=energy['covered_seconds']/max(1,w['end']-w['start']);w['active_interval_coverage_fraction']=round(fraction,4)
            if fraction>=.5:
                w['active_kcal']=round(energy['value'],2);w['active_energy_kind']='energy_samples_in_workout_window'
        w['date']=dt.datetime.fromtimestamp(w['start'],zone).date().isoformat()
        if w.get('active_kcal') is not None and w['duration_minutes']>0 and w['date']>=today.isoformat():w['excluded_from_training']='current_or_future_day'
        if w.get('active_kcal') is not None and w['duration_minutes']>0 and w['date']<today.isoformat():rates[w['activity']].append((w['start'],w['active_kcal']/w['duration_minutes']))
        workouts.append(w)
    forecasts=[]
    for activity,observations in sorted(rates.items()):
        observations=observations[-20:];values=[v for _,v in observations];age=(today-dt.datetime.fromtimestamp(observations[-1][0],zone).date()).days
        forecasts.append(dict(activity=activity,observations=len(values),kcal_per_min_p20=round(quantile(values,.2),3),kcal_per_min_p50=round(quantile(values,.5),3),kcal_per_min_p80=round(quantile(values,.8),3),status='provisional' if len(values)>=3 and age<=90 else 'insufficient_or_stale',age_days=age,note='Stima per tipo Apple, non per esercizio/protocollo; scalare alla durata è un’ipotesi.'))
    return dict(version=VERSION,analysis_version=ANALYSIS_VERSION,as_of=today.isoformat(),timezone=timezone,latest_energy_date=days[-1]['date'] if days else None,measures=measures,weight_history=weights,body_profile_needs_review=not measures.get('weight') or measures['weight']['age_days']>90,windows=windows,scenarios=scenarios,daily=days[-90:],workouts=workouts[-100:],workout_forecasts=forecasts,limitations=['Energia Watch stimata, non misura metabolica diretta.','L’energia delle sessioni non è sommata al totale giornaliero.','Sovrapposizioni: Watch > iPhone > altre fonti; a parità intervallo più breve, poi registrazione più recente.','Distribuzione uniforme delle calorie dentro ogni intervallo; giorni nel fuso configurato.','Copertura del riposo è un indicatore di completezza, non prova di uso continuo del Watch.','Frequenza cardiaca campione per campione, sonno e itinerari non vengono importati in questa prima versione; le statistiche cardiache degli allenamenti sono conservate se presenti.','Mancano etichette dei protocolli, carichi, ripetizioni e feedback reale per stimare la risposta a una scheda.'])


def import_zip(archive,output,owner,progress=None,timezone='Europe/Rome',force=False):
    archive=Path(archive);output=Path(output);output.mkdir(parents=True,exist_ok=True);output.chmod(0o700)
    status=lambda **kw:progress(kw) if progress else None
    with zipfile.ZipFile(archive) as z:
        candidates=[f for f in z.infolist() if f.filename.endswith('.xml') and not f.filename.endswith('export_cda.xml')]
        if len(candidates)!=1:raise ValueError('Expected one main Health XML')
        member=candidates[0]
        manifest=dict(member=member.filename,crc32=member.CRC,uncompressed_bytes=member.file_size,version=VERSION,timezone=timezone,owner=owner)
        fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
        final=output/'health.sqlite';report_path=output/'summary.json'
        if not force and final.exists() and report_path.exists():
            report=json.loads(report_path.read_text())
            if report.get('import',{}).get('fingerprint')==fingerprint:
                if report.get('analysis_version')!=ANALYSIS_VERSION:
                    status(state='summarizing',reused=True)
                    with sqlite3.connect(final) as db:updated=summarize(db,timezone)
                    updated['import']=report['import'];report=updated
                    temp_report=output/'summary.importing.json';temp_report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');temp_report.chmod(0o600);os.replace(temp_report,report_path)
                status(state='complete',reused=True);return report
        temporary=output/'health.importing.sqlite'
        if temporary.exists():temporary.unlink()
        db=sqlite3.connect(temporary)
        db.executescript('''PRAGMA journal_mode=OFF;
        CREATE TABLE measures(id TEXT PRIMARY KEY,kind TEXT,value REAL,unit TEXT,start REAL,end REAL,source TEXT);
        CREATE TABLE energy(id TEXT,part INTEGER,day TEXT,kind TEXT,start REAL,end REAL,value REAL,source TEXT,priority INTEGER,created REAL,PRIMARY KEY(id,part));
        CREATE TABLE workouts(id TEXT PRIMARY KEY,start REAL,payload TEXT);
        CREATE TABLE metadata(key TEXT PRIMARY KEY,payload TEXT);''')
        counts=collections.Counter();invalid=collections.Counter();latest={};seen=0;last=time.monotonic();duplicates=0
        try:
            with z.open(member) as stream:
                parser=ET.iterparse(stream,events=('start','end'));_,root=next(parser)
                if root.tag!='HealthData':raise ValueError('Not a Health export')
                for event,element in parser:
                    if event!='end' or element.tag not in ['Record','Workout','ActivitySummary','Me','ExportDate']:continue
                    a=element.attrib
                    if element.tag=='Record':
                        type_=a.get('type','unknown');counts[type_]+=1;seen+=1
                        if a.get('endDate','')>latest.get(type_,''):latest[type_]=a.get('endDate','')
                        if type_ in TYPES:
                            kind=TYPES[type_]
                            try:
                                value=normalize(kind,a['value'],a['unit']);start=timestamp(a['startDate']);end=timestamp(a['endDate']);source=a.get('sourceName','unknown')
                                created=timestamp(a.get('creationDate',a['endDate']))
                                identifier=hashlib.sha256(json.dumps({k:a.get(k) for k in ['type','value','unit','startDate','endDate','sourceName','device']},sort_keys=True).encode()).hexdigest()
                                if kind in ENERGY:
                                    for part,(day,begin,finish,amount) in enumerate(split_days(start,end,value,ZoneInfo(timezone))):
                                        cursor=db.execute('INSERT OR IGNORE INTO energy VALUES(?,?,?,?,?,?,?,?,?,?)',(identifier,part,day,kind,begin,finish,amount,source,priority(source,a.get('device','')),created));duplicates+=cursor.rowcount==0
                                else:
                                    unit={'weight':'kg','height':'cm','body_fat':'%','bmi':'count','resting_hr':'count/min','vo2max':'mL/min·kg'}[kind]
                                    cursor=db.execute('INSERT OR IGNORE INTO measures VALUES(?,?,?,?,?,?,?)',(identifier,kind,value,unit,start,end,source));duplicates+=cursor.rowcount==0
                            except (ValueError,KeyError,OverflowError):invalid[type_]+=1
                    elif element.tag=='Workout':
                        counts['Workout']+=1
                        try:
                            start=timestamp(a['startDate']);end=timestamp(a['endDate']);duration=float(a.get('duration',(end-start)/60));unit=a.get('durationUnit','min')
                            if unit=='s':duration/=60
                            elif unit=='hr':duration*=60
                            elif unit!='min':raise ValueError('Unknown workout duration unit')
                            if not math.isfinite(duration) or duration<=0 or end<=start:raise ValueError('Invalid workout duration')
                            w=dict(activity=a.get('workoutActivityType','unknown'),start=start,end=end,duration_minutes=duration,source=a.get('sourceName','unknown'),active_kcal=None,legacy_energy=None,heart_rate_statistics=None)
                            if 'totalEnergyBurned' in a:w['legacy_energy']=dict(value=a['totalEnergyBurned'],unit=a.get('totalEnergyBurnedUnit'),note='Legacy energy semantics not assumed active')
                            for child in element:
                                if child.tag!='WorkoutStatistics':continue
                                if child.get('type')=='HKQuantityTypeIdentifierActiveEnergyBurned' and child.get('sum') is not None:w['active_kcal']=normalize('active_energy',child.get('sum'),child.get('unit'))
                                if child.get('type')=='HKQuantityTypeIdentifierHeartRate':w['heart_rate_statistics']={k:child.get(k) for k in ['average','minimum','maximum','unit']}
                            identifier=hashlib.sha256(json.dumps({k:a.get(k) for k in ['workoutActivityType','startDate','endDate','sourceName','device']},sort_keys=True).encode()).hexdigest()
                            db.execute('INSERT OR IGNORE INTO workouts VALUES(?,?,?)',(identifier,start,json.dumps(w)))
                        except (ValueError,KeyError,OverflowError):invalid['Workout']+=1
                    element.clear();root.clear()
                    if seen%10000==0:db.commit()
                    if time.monotonic()-last>5:status(state='parsing',records=seen);last=time.monotonic()
            db.commit();status(state='summarizing',records=seen)
            db.executescript('CREATE INDEX energy_day ON energy(day,kind); CREATE INDEX energy_time ON energy(kind,start,end); CREATE INDEX measures_kind ON measures(kind,end);')
            report=summarize(db,timezone)
            report['import']=dict(fingerprint=fingerprint,fingerprint_kind='sha256_of_member_crc_size_and_rules_not_file_sha256',owner=owner,counts=dict(counts),latest_by_type=latest,invalid=dict(invalid),duplicates_skipped=duplicates,records_seen=seen,normalized_energy_segments=db.execute('SELECT COUNT(*) FROM energy').fetchone()[0],normalized_measurements=db.execute('SELECT COUNT(*) FROM measures').fetchone()[0],workouts_stored=db.execute('SELECT COUNT(*) FROM workouts').fetchone()[0])
            db.execute('INSERT INTO metadata VALUES(?,?)',('import',json.dumps(report['import'])));db.commit();db.close();temporary.chmod(0o600)
            os.replace(temporary,final);temp_report=output/'summary.importing.json';temp_report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');temp_report.chmod(0o600);os.replace(temp_report,report_path)
            status(state='complete',records=seen,reused=False);return report
        except BaseException:
            db.close()
            if temporary.exists():temporary.unlink()
            raise

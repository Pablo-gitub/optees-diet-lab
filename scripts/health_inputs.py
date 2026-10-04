"""Read private Health-derived inputs without prescribing nutritional targets."""
import copy
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo


def refresh_report(report,today=None):
    report=copy.deepcopy(report);today=today or dt.datetime.now(ZoneInfo(report['timezone'])).date()
    original_date=report.get('imported_as_of',report['as_of'])
    report['as_of']=today.isoformat()
    for measure in report['measures'].values():measure['age_days']=(today-dt.date.fromisoformat(measure['date'])).days
    scenarios=report['scenarios'];anchor=next(w['end_date'] for w in report['windows'] if w['days']==28)
    age=(today-dt.date.fromisoformat(anchor)).days if anchor else None
    scenarios['staleness_days']=age;scenarios['status']='available' if scenarios['valid_days']>=7 and age is not None and 0<=age<=14 else 'insufficient_or_stale'
    for f in report['workout_forecasts']:
        # Stored age refers to the report's original import day.
        f['age_days']+=max(0,(today-dt.date.fromisoformat(original_date)).days)
        f['status']='provisional' if f['observations']>=3 and 0<=f['age_days']<=90 else 'insufficient_or_stale'
    for window in report['windows']:
        if window.get('end_date') and report.get('daily'):
            anchor=dt.date.fromisoformat(window['end_date']);selected=[d for d in report['daily'] if d['usable_for_baseline'] and anchor-dt.timedelta(days=window['days']-1)<=dt.date.fromisoformat(d['date'])<=anchor]
            if len(selected)==window['valid_days'] and selected:
                window['mean_active_kcal']=round(sum(d['active_kcal'] for d in selected)/len(selected),2)
                window['mean_resting_kcal']=round(sum(d['resting_kcal'] for d in selected)/len(selected),2)
    report['body_profile_needs_review']=not report['measures'].get('weight') or report['measures']['weight']['age_days']>90
    return report


def algorithm_inputs(report):
    scenario=report['scenarios']
    return dict(version='health-inputs-v1',body_measurements=report['measures'],body_profile_needs_review=report.get('body_profile_needs_review',True),consumption_scenarios=scenario,workout_energy_models=report['workout_forecasts'],usable_consumption_baseline=scenario['status']=='available',nutritional_targets='unchanged_requires_goal_configuration',joint_optimization='not_yet_implemented',do_not_add_workout_energy_to_existing_daily_total=True)


def load_report(directory):
    path=Path(directory)/'summary.json'
    if not path.exists():return None
    report=json.loads(path.read_text());report['imported_as_of']=report['as_of']
    return refresh_report(report)

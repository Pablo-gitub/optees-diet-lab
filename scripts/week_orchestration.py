"""Weekly backend entry point; extended to a joint MILP in step 2.3."""
import datetime as dt
from day_orchestration import orchestrate_day
from diary_service import DomainError,valid_date

async def generate_week(session,profile,request,make_config,foods):
    start=dt.date.fromisoformat(valid_date(request.get('week_start')))
    if request.get('locked'):raise DomainError('Blocchi settimanali previsti nel passo 2.3')
    days=[];warnings=[]
    for offset in range(7):
        config=make_config(profile,offset)
        result=await orchestrate_day(session,config,foods,dict(k=1,pool_size=1))
        if not result['plans']:return dict(spec_version='orchestration-v2',status='infeasible',mode=profile['mode'],week_start=start.isoformat(),plans=[],warnings=result['warnings'])
        plan=result['plans'][0];plan['date']=(start+dt.timedelta(days=offset)).isoformat();days.append(plan);warnings.extend(result['warnings'])
    return dict(spec_version='orchestration-v2',status='ok',mode=profile['mode'],week_start=start.isoformat(),horizon=dict(days=7),plans=[dict(role='best',days=days,targets=config['daily_meals']['targets'] if config.get('daily_meals',{}).get('enabled') else config['main_meals_targets'])],warnings=warnings)

def generate_meal_alternatives(*args):raise DomainError('Alternative per pasto previste nel passo 2.3')

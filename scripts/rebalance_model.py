"""Conservative portion-first models; existing food references remain authoritative."""
import copy
import math
from multiobjective_day import extend
from week_orchestration import weekly_model

SUBSTITUTION_COST = 10000
SNACK_CHANGE_COST = 100000
PORTION_FRACTION = .20


def identity(item):
    if 'food' in item and isinstance(item['food'],dict):
        return item['food']['source'],item['food']['id']
    return item.get('source','CREA'),item.get('reference_id') or item['food_id']


def quantities(items):
    result={}
    for item in items:
        key=identity(item);result[key]=result.get(key,0.)+item['grams']
    return {key:round(value,3) for key,value in result.items()}


def changed(before,after):
    return quantities(before)!=quantities(after)


def excluded_dishes(meal,foods):
    # A preset describes a dish, not every individual ingredient in that dish.
    pizza=meal.get('provenance',{}).get('preset_id')=='pizzeria'
    refs=meal.get('excluded_foods',[])
    return {identifier for identifier,food in foods.items()
            if pizza and 'pizza' in food.get('name','').lower() or
            (food.get('source','CREA'),food.get('source_id',identifier)) in refs}


def _remove_fixed_quantity(problem,index):
    problem['constraints']=[r for r in problem['constraints'] if not (
        r['relation']=='=' and r['coefficients'][index]==1 and
        sum(v!=0 for v in r['coefficients'])==1)]


def build(profile,request,configuration,foods,views,stage,forbidden):
    request=copy.deepcopy(request)
    protected={(v['date'],m['slot']) for v in views for m in v['meals']
               if m['state']!='unknown' or m['planned'] and m['planned']['locked']}
    locks=list(request['locked'])
    for view in views:
        for meal in view['meals']:
            key=view['date'],meal['slot']
            if key in protected or not meal['planned']:continue
            if stage=='grams' or stage=='main_meals' and meal['slot'] not in ('lunch','dinner'):
                locks.append(dict(date=view['date'],slot=meal['slot'],items=[
                    {k:x[k] for k in ('food','grams','units') if k in x} for x in meal['planned']['items']]))
    request['locked']=locks
    if stage=='grams':
        # No food changes => the existing repetition pattern is preserved exactly.
        request['max_protein_repetitions']=14;request['_prior_frequencies']={}
    problem,blocks,choices,maximum=weekly_model(profile,request,configuration,foods)
    problem.pop('preference_coefficients',None)
    costs={};old={}
    for view in views:
        for meal in view['meals']:
            if meal['planned']:
                for ref,grams in quantities(meal['planned']['items']).items():old[view['date'],meal['slot'],ref]=grams
    for block in blocks:
        if stage=='grams':
            for local in block['choices']:
                if (block['date'],local['meal']) in protected or local['meal'] not in ('lunch','dinner') or local.get('units') is not None:continue
                if local['food_id'] in forbidden:raise ValueError('Il piatto fuori programma richiede una sostituzione.')
                index=local['q'];global_index=index+block['shift'];original=local['locked_grams']
                low=min(original,max(5,original*(1-PORTION_FRACTION)));high=min(3000,original*(1+PORTION_FRACTION))
                configured=block['config'].get('portion_bounds_g',{}).get(local['food_id'])
                if configured and configured[0]<=original<=configured[1]:
                    low=max(low,configured[0]);high=min(high,configured[1])
                first_step=math.ceil((low-original)/5);last_step=math.floor((high-original)/5)
                # Encode the actual grid endpoints, relative to the current reference,
                # in both the weekly model and the independently verified day.
                low=original+5*first_step;high=original+5*last_step
                for model,q in ((block['problem'],index),(problem,global_index)):
                    _remove_fixed_quantity(model,q);model['variables'][q].update(lb=low,ub=high)
                steps=extend(problem,dict(name=f'portion_step_{global_index}',lb=first_step,ub=last_step,integrality='I'))
                row=[0.]*len(problem['variables']);row[global_index]=1;row[steps]=-5
                problem['constraints'].append(dict(coefficients=row,relation='=',rhs=original))
                local['locked']=False
        for slot in list(block['config'].get('locked_meals',{})):
            if (block['date'],slot) not in protected:block['config']['locked_meals'].pop(slot)
    for choice in choices:
        if (choice['date'],choice['meal']) in protected:continue
        q,y=choice['q'],choice['y'];reference=old.get((choice['date'],choice['meal'],identity(choice)),0.)
        if choice['food_id'] in forbidden:
            if choice.get('locked'):raise ValueError('Il piatto fuori programma è presente in un pasto da sostituire.')
            problem['variables'][y]['ub']=0
        if stage!='grams' and not reference:costs[y]=SUBSTITUTION_COST+(SNACK_CHANGE_COST if choice['meal'] not in ('lunch','dinner') else 0)
        dev=extend(problem,dict(name=f'portion_change_{q}',lb=0,ub=3000,integrality='C'));costs[dev]=1
        for sign in (1,-1):
            row=[0.]*len(problem['variables']);row[q]=sign;row[dev]=-1
            problem['constraints'].append(dict(coefficients=row,relation='<=',rhs=sign*reference))
        indicator=extend(problem,dict(name=f'food_change_{q}',lb=0,ub=1,integrality='B'))
        row=[0.]*len(problem['variables']);row[dev]=1;row[indicator]=-3000
        problem['constraints'].append(dict(coefficients=row,relation='<=',rhs=0))
        costs[indicator]=SUBSTITUTION_COST if stage=='grams' else 100+(SNACK_CHANGE_COST if choice['meal'] not in ('lunch','dinner') else 0)
    return problem,blocks,choices,maximum,costs

"""MILP scalarizations and a sampled Pareto set; all original hard bounds remain."""
import copy
import math
from plan_diet_day import solve_problem, NUTRIENTS
from plan_recipe import values_verified

STRATEGIES = ('balanced', 'minmax', 'maxmin', 'pareto')


def metrics(config, choices, size):
    targets = config['daily_meals']['targets'] if config.get('daily_meals', {}).get('enabled') else config['main_meals_targets']
    out = []
    for n, nutrient in enumerate(NUTRIENTS):
        if nutrient not in targets:
            continue
        spec = targets[nutrient]
        row = [0.] * size
        for c in choices:
            row[c['q']] = c['nutrients'][n]
        out.append((nutrient.replace('_100g', ''), spec, row))
    return out


def extend(problem, variable):
    problem['variables'].append(variable)
    problem['objective']['coefficients'].append(0.)
    for row in problem['constraints']:
        row['coefficients'].append(0.)
    return len(problem['variables']) - 1


async def solve_strategy(session, problem, config, choices, strategy='balanced', weights=None):
    if strategy not in STRATEGIES:
        raise ValueError('Unknown strategy')
    p = copy.deepcopy(problem)
    pref = p.pop('preference_coefficients', None)
    penalty = None
    original_size = len(p['variables'])
    if pref and any(pref):
        p['objective']['coefficients'] = pref[:]
        first = await solve_problem(session, p)
        if first['mathematical_status'] != 'optimal':
            return first
        values = values_verified(p, first)
        penalty = sum(a*b for a,b in zip(pref, values))
        p['constraints'].append(dict(coefficients=pref[:], relation='<=', rhs=penalty+1e-7))
    measures = metrics(config, choices, original_size)
    coefficients = [0.] * original_size
    for key, spec, row in measures:
        n = NUTRIENTS.index(key+'_100g')
        idx = next(i for i,v in enumerate(p['variables']) if v['name'] == f'dev{n}')
        coefficients[idx] = (weights or {}).get(key, 1.) / spec['target']
    p['objective']['coefficients'] = coefficients[:]
    primary = None
    if strategy in ('minmax', 'maxmin'):
        idx = extend(p, dict(name='worst_error', lb=0., ub=1e6, integrality='C'))
        for key, spec, row in measures:
            n = NUTRIENTS.index(key+'_100g')
            dev = next(i for i,v in enumerate(p['variables']) if v['name']==f'dev{n}')
            scale = spec['target'] if strategy=='minmax' else max(spec['target']-spec['min'], spec['max']-spec['target'])
            if scale == 0:
                continue  # A fixed target is already an exact hard equality.
            bound = [0.] * len(p['variables']); bound[dev]=1/scale; bound[idx]=-1
            p['constraints'].append(dict(coefficients=bound, relation='<=', rhs=0.))
        p['objective']['coefficients'] = [0.] * len(p['variables']);p['objective']['coefficients'][idx]=1.
        first = await solve_problem(session, p)
        if first['mathematical_status'] not in ('optimal', 'feasible'):
            return first
        values = values_verified(p, first);primary=values[idx]
        if first['mathematical_status']=='optimal':
            bound=[0.]*len(p['variables']);bound[idx]=1.
            p['constraints'].append(dict(coefficients=bound,relation='<=',rhs=primary+1e-7))
            p['objective']['coefficients']=coefficients+[0.]
            result=await solve_problem(session,p)
            if result['mathematical_status'] not in ('optimal','feasible'):
                result=first
        else:
            result=first
    else:
        result=await solve_problem(session,p)
    if result['mathematical_status'] not in ('optimal','feasible'):
        return result
    values=values_verified(p,result)
    errors={key:abs(sum(a*b for a,b in zip(row,values))-spec['target'])/spec['target'] for key,spec,row in measures}
    satisfaction={key:1-abs(sum(a*b for a,b in zip(row,values))-spec['target'])/max(spec['target']-spec['min'],spec['max']-spec['target']) if spec['max']>spec['min'] else 1. for key,spec,row in measures}
    result['preference_penalty']=penalty
    result['optimization']=dict(strategy=strategy,relative_errors=errors,worst_relative_error=max(errors.values()),minimum_satisfaction=min(satisfaction.values()),primary_value=primary,weights=weights)
    return result


def nondominated(results):
    """Remove duplicates and dominance using recomputed nutritional errors."""
    keep=[]
    for result in results:
        point=tuple(result['optimization']['relative_errors'].values())
        if any(all(abs(a-b)<1e-6 for a,b in zip(point,q)) for _,q in keep):continue
        keep.append((result,point))
    return [r for i,(r,p) in enumerate(keep) if not any(j!=i and all(a<=b+1e-8 for a,b in zip(q,p)) and any(a<b-1e-8 for a,b in zip(q,p)) for j,(_,q) in enumerate(keep))]


def choose_arm(observations):
    """UCB1 on actual trial feedback, never on a selected/generated plan."""
    arms=('balanced','minmax','maxmin');counts={a:[] for a in arms}
    for arm,reward in observations:
        if arm in counts:counts[arm].append(reward)
    for arm in arms:
        if not counts[arm]:return arm, 'exploration'
    total=sum(map(len,counts.values()))
    scores={a:sum(v)/len(v)+math.sqrt(2*math.log(total)/len(v)) for a,v in counts.items()}
    return max(scores,key=scores.get), 'ucb1'

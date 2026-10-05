"""Gram-weighted canonical overlap, with fixed-threshold linear MILP cuts."""
import copy
import json
import re
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GROUPS=json.loads((ROOT/'config/recipe-diet-food-groups.json').read_text())['foods']
# Category rules, not low-weight rules. Onion/garlic are intentionally not herbs.
EXCLUDED=re.compile(r'^(olio\b|oli\b|sale\b|pepe\b|spezi[ae]\b|erbe\b|aceto\b|brodo\b|condiment[oi]\b|basilico\b|prezzemolo\b|rosmarino\b|origano\b|salvia\b|timo\b|menta\b|cannella\b|noce moscata\b|curcuma\b|zenzero\b|paprika\b|cumino\b|maionese\b|senape\b|ketchup\b|salsa di soia\b|salsa worcester\b|dado\b|peperoncino\b|alloro\b|aneto\b|erba cipollina\b|coriandolo\b|finocchietto\b|chiodi di garofano\b|curry\b|vaniglia\b|zafferano\b)',re.I)


def canonical(identifier,foods,profile=None):
    row=foods.get(identifier,{})
    source=row.get('source','CREA');source={'OFF':'Open Food Facts'}.get(source,source)
    code=row.get('source_id',identifier)
    name=row.get('name','')
    if source=='water' or GROUPS.get(source+':'+code)=='oil' or EXCLUDED.search(name):return None
    for generic,ref in (profile or {}).get('food_preferences',{}).get('preferred_products',{}).items():
        if ref['id']==code and {'OFF':'Open Food Facts'}.get(ref['source'],ref['source'])==source:
            group=GROUPS.get('CREA:'+generic,'CREA:'+generic)
            if group=='oil' or EXCLUDED.search(foods.get(generic,{}).get('name','')):return None
            return group
    # Unknown branded identities are conservatively shared: changing brand
    # never invents diversity. A reviewed generic mapping refines this bucket.
    fallback='unclassified_product' if source in ('Open Food Facts','user_label') else source+':'+code
    return GROUPS.get(source+':'+code,fallback)


def components(identifier,foods,profile=None):
    provenance=foods.get(identifier,{}).get('composition_provenance') or {}
    ingredients=provenance.get('ingredients',[])
    row=foods.get(identifier,{})
    if not ingredients and row.get('source')=='recipe':
        recipe=(profile or {}).get('_recipe_runs',{}).get(row.get('source_id'))
        if recipe and recipe.get('status') in ('optimal','feasible'):
            mass=sum(s['grams'] for s in recipe['selections'])
            if mass>0:ingredients=[dict(source=s['source'],id=s['id'],name=s.get('food',''),fraction=s['grams']/mass) for s in recipe['selections']]
    if not ingredients and (row.get('source')=='recipe' or identifier.startswith('recipe:')):return {'unclassified_composition':1}
    if ingredients and all('fraction' in i for i in ingredients):
        result={}
        for item in ingredients:
            if item.get('name','').casefold() in ('acqua','water'):continue
            if not item.get('id'):raise ValueError('Ingrediente della ricetta senza identità canonica verificabile')
            ref=item['id'];source=item.get('source','CREA')
            nested=dict(foods);nested['component']=dict(foods.get(ref,{}),source=source,source_id=ref,name=foods.get(ref,{}).get('name') or item.get('name',''))
            key=canonical('component',nested,profile)
            if key and item['fraction']>0:result[key]=result.get(key,0)+item['fraction']
        return result
    key=canonical(identifier,foods,profile)
    return {key:1} if key else {}


def amounts(plan,foods,profile=None,slot=None):
    out={}
    for day in plan.get('days',[plan]):
        for s in day.get('selections',[]):
            if slot and s['meal']!=slot:continue
            for key,fraction in components(s['food_id'],foods,profile).items():out[key]=out.get(key,0)+s['grams']*fraction
    return out


def directed(a,b):
    total=sum(b.values())
    return sum(g for i,g in b.items() if i in a)/total if total else 0.


def overlap(a,b):return max(directed(a,b),directed(b,a))


def cuts(problem,choices,previous,foods,threshold,profile=None,slot=None):
    """Both directed ratios; constants are grams of each previous plan."""
    p=copy.deepcopy(problem);by={}
    for c in choices:
        if slot and c['meal']!=slot:continue
        for key,fraction in components(c['food_id'],foods,profile).items():by.setdefault(key,[]).append(dict(c,fraction=fraction))
    # Presence indicator OR of selected portions. Positive portions are guaranteed
    # by the formulation; all cuts are also checked against decoded actual grams.
    indicators={}
    for key,group in by.items():
        i=len(p['variables']);indicators[key]=i
        p['variables'].append(dict(name='overlap_presence_'+str(i),lb=0,ub=1,integrality='B'))
        for r in p['constraints']:r['coefficients'].append(0.)
        p['objective']['coefficients'].append(0.)
        if 'preference_coefficients' in p:p['preference_coefficients'].append(0.)
        size=len(p['variables'])
        for c in group:
            r=[0.]*size;r[c['y']]=1;r[i]=-1;p['constraints'].append(dict(coefficients=r,relation='<=',rhs=0))
        r=[0.]*size;r[i]=1
        for c in group:r[c['y']]-=1
        p['constraints'].append(dict(coefficients=r,relation='<=',rhs=0))
    for plan in previous:
        a=amounts(plan,foods,profile,slot);size=len(p['variables']);forward=[0.]*size;reverse=[0.]*size
        for key,group in by.items():
            for c in group:forward[c['q']]+=c['fraction']*((1 if key in a else 0)-threshold)
            reverse[indicators[key]]=a.get(key,0)
        p['constraints'].extend([dict(coefficients=forward,relation='<=',rhs=0),dict(coefficients=reverse,relation='<=',rhs=threshold*sum(a.values()))])
    return p


async def minimax_candidate(base,choices,previous,foods,solve,deadline,profile=None,slot=None):
    """Fixed-threshold bisection: no nonlinear t*q and no nutrition relaxation.

    Lower bounds move only on certified infeasibility. 1 percentage point
    absolute precision; time-limited solves never certify maximal diversity.
    """
    async def attempt(threshold):
        p=cuts(base,choices,previous,foods,threshold,profile,slot)
        p['solver']['time_limit']=min(p['solver'].get('time_limit',15),max(.1,deadline-time.monotonic()))
        r=await solve(p)
        return r,p
    r,p=await attempt(.1)
    if r['mathematical_status'] in ('optimal','feasible'):return r,p,dict(threshold=.1,certified=r['mathematical_status']=='optimal',target_feasible=True)
    if r['mathematical_status']!='infeasible':return None,None,dict(certified=False,reason='Tempo di calcolo esaurito senza un’alternativa verificata.')
    low=.1;high=1.;best=None;best_p=None
    if time.monotonic()>=deadline:return None,None,dict(certified=False,reason='Soglia del 10% non fattibile; tempo insufficiente per minimizzare.')
    r,p=await attempt(high)
    if r['mathematical_status'] not in ('optimal','feasible'):return None,None,dict(certified=r['mathematical_status']=='infeasible',reason='Nessun’altra combinazione fattibile entro i vincoli.')
    best,best_p=r,p;certified=True
    while high-low>.01 and time.monotonic()<deadline:
        middle=(low+high)/2;r,p=await attempt(middle)
        if r['mathematical_status'] in ('optimal','feasible'):high=middle;best,best_p=r,p
        elif r['mathematical_status']=='infeasible':low=middle
        else:certified=False;break
    return best,best_p,dict(threshold=high,lower_bound=low,precision_pct=1,certified=certified and high-low<=.01,target_feasible=False)


def report(envelope,plans,foods,profile=None,slot=None,existing=()):
    all_plans=list(existing)+list(plans);vectors=[amounts(p,foods,profile,slot) for p in all_plans]
    pair=[overlap(a,b)*100 for i,a in enumerate(vectors) for b in vectors[:i]]
    for i,p in enumerate(all_plans):p['overlap_pct']=round(max((overlap(vectors[i],v)*100 for j,v in enumerate(vectors) if i!=j),default=0),2)
    envelope['pool'].update(overlap_target=10,overlap_achieved=round(max(pair),2) if pair else None,overlap_scope='meal' if slot else 'week' if plans and 'days' in plans[0] else 'day',overlap_metric='maximum_both_directed_gram_ratios',canonical_version='ingredient-overlap-v1')
    if any('unclassified_product' in v or 'unclassified_composition' in v for v in vectors):
        envelope.setdefault('warnings',[]).append(dict(code='canonical_mapping_missing',message='Prodotti o composizioni senza generico verificato sono confrontati conservativamente; la marca non crea diversità.'))
    if pair and max(pair)>10.0001:
        for p in plans:
            p.setdefault('explanation',{}).setdefault('reasons',[]).append(f"Questa alternativa cambia almeno il {100-p['overlap_pct']:.1f}% degli ingredienti in peso; soglia del 10% non raggiunta entro i vincoli e il budget.")
        envelope.setdefault('warnings',[]).append(dict(code='overlap_target_unavailable',message='Sovrapposizione massima minimizzata nei vincoli nutrizionali; certificazione e intervallo nel pool.',overlap_achieved=envelope['pool']['overlap_achieved']))

#!/usr/bin/env python3
"""Diagnosi offline: soli input pubblici/sintetici, senza DB o servizi esterni.

PYTHONPATH=scripts:. python scripts/diagnose_variety.py --output /tmp/variety.json
Le patch del modello sono circoscritte agli esperimenti di questo processo.
"""
import argparse
import asyncio
import contextlib
import copy
import hashlib
import json
import math
import tempfile
import time
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix
import ingredient_overlap as io
import plan_diet_day as diet
import week_orchestration as week
from plan_recipe import values_verified
from daily_meals import defaults
from audit_ingredient_overlap import config as audit_config, factory

ROOT=Path(__file__).resolve().parents[1]
CATEGORIES=('frutta','verdura','amidi','proteine_animali','proteine_vegetali','latticini','colazione_spuntini','ricette','altro')
EXPANDED=dict(FRUIT=['007120','007260','007000','007050','007330'],
              VEG=['005730','006600','005410','005110','005680','005220'],
              STARCH=['000800','000100','000530','000020','000045','000090'])


@contextlib.contextmanager
def replace_attribute(module,name,value):
    """Rilassamento locale con ripristino garantito; non tocca file o profili salvati."""
    original=getattr(module,name)
    setattr(module,name,value)
    try:yield
    finally:setattr(module,name,original)


def category(food,slot):
    if slot not in ('lunch','dinner'):return 'colazione_spuntini'
    if food.get('composition_provenance') or food.get('source')=='recipe':return 'ricette'
    name=food.get('category','')
    if name=='Frutta':return 'frutta'
    if name=='Verdure e ortaggi':return 'verdura'
    if name=='Cereali e derivati':return 'amidi'
    if name in ('Legumi','Frutta secca a guscio e semi oleaginosi'):return 'proteine_vegetali'
    if name in ('Formaggi e latticini','Latte e yogurt'):return 'latticini'
    if name in ('Carni fresche','Carni trasformate e conservate','Prodotti della pesca','Uova','Frattaglie'):return 'proteine_animali'
    return 'altro'


def matrix(problem):
    rows=problem['constraints']
    return LinearConstraint(csc_matrix(np.asarray([r['coefficients'] for r in rows],dtype=float)),
        [r['rhs'] if r['relation'] in ('=','>=') else -np.inf for r in rows],
        [r['rhs'] if r['relation'] in ('=','<=') else np.inf for r in rows])


class Solver:
    def __init__(self,seconds):self.seconds=seconds;self.calls=[]
    def solve(self,p,objective=None,relax=False):
        begun=time.monotonic();limit=min(self.seconds,p.get('solver',{}).get('time_limit',self.seconds))
        objective=p['objective']['coefficients'] if objective is None else objective
        result=milp(np.asarray(objective,dtype=float),
            integrality=[0 if relax else int(v['integrality']!='C') for v in p['variables']],
            bounds=Bounds([v['lb'] for v in p['variables']],[v['ub'] for v in p['variables']]),
            constraints=matrix(p),options=dict(time_limit=max(.01,limit)))
        status='optimal' if result.success else 'feasible' if result.x is not None else 'infeasible' if result.status==2 else 'unknown'
        record=dict(status=status,elapsed_seconds=time.monotonic()-begun,limit_seconds=limit,
                    scipy_status=int(result.status),message=result.message,
                    mip_gap=None if getattr(result,'mip_gap',None) is None else float(result.mip_gap))
        self.calls.append(record)
        answer=dict(mathematical_status=status,validation=dict(status='verified' if result.x is not None else 'unavailable'),
                    result=dict(variables=[] if result.x is None else [dict(name=v['name'],value=float(x)) for v,x in zip(p['variables'],result.x)]))
        if result.x is not None and not relax:values_verified(p,answer)
        return answer,result


def decomposition(plans,foods,profile):
    vectors=[io.amounts(p,foods,profile) for p in plans];pairs=[]
    for i in range(len(plans)):
        for j in range(i):
            # Direction with the maximum ratio; contributions share its denominator.
            numerator_plan,other=(i,j) if io.directed(vectors[j],vectors[i])>=io.directed(vectors[i],vectors[j]) else (j,i)
            denominator=sum(vectors[numerator_plan].values());cats={c:0. for c in CATEGORIES};slots={};cross={}
            for day in plans[numerator_plan]['days']:
                for sel in day['selections']:
                    cat=category(foods[sel['food_id']],sel['meal']);slot=sel['meal']
                    shared=sum(sel['grams']*fraction for key,fraction in io.components(sel['food_id'],foods,profile).items() if key in vectors[other])
                    cats[cat]+=shared;slots[slot]=slots.get(slot,0)+shared
                    cross.setdefault(slot,{c:0. for c in CATEGORIES})[cat]+=shared
            pct=100*io.overlap(vectors[i],vectors[j])
            assert abs(sum(cats.values())/denominator*100-pct)<1e-7
            pairs.append(dict(pair=[j,i],numerator_plan=numerator_plan,denominator_grams=denominator,
                shared_grams=sum(cats.values()),overlap_pct=pct,
                category_pp={k:v/denominator*100 for k,v in cats.items()},slot_pp={k:v/denominator*100 for k,v in slots.items()},
                category_by_slot_pp={s:{k:v/denominator*100 for k,v in cs.items()} for s,cs in cross.items()}))
    return dict(pairs=pairs,worst_pair=max(pairs,key=lambda p:p['overlap_pct']) if pairs else None,
                max_overlap_pct=max((p['overlap_pct'] for p in pairs),default=None),
                mean_overlap_pct=sum(p['overlap_pct'] for p in pairs)/len(pairs) if pairs else None)


def theoretical(problem,choices,foods,profile,solver,maximum):
    size=len(problem['variables']);identities={};cats={c:np.zeros(size) for c in CATEGORIES};servings={}
    for choice in choices:
        cat=category(foods[choice['food_id']],choice['meal']);parts=io.components(choice['food_id'],foods,profile)
        for key,fraction in parts.items():
            identities.setdefault(key,np.zeros(size))[choice['q']]+=fraction
            cats[cat][choice['q']]+=fraction
        if choice.get('principal_protein') and len(parts)==1:
            key=next(iter(parts));servings.setdefault(key,[]).append(choice['food_id'])
    total=sum(cats.values());_,upper=solver.solve(problem,-total,relax=True)
    # Only optimal LP relaxations supply bounds. A timeout never supplies a proof.
    if not upper.success:return dict(certified=False,reason='Limite superiore LP non certificato')
    total_max=-float(upper.fun);forced={};minima={}
    for key,vector in identities.items():
        _,r=solver.solve(problem,vector,relax=True)
        if not r.success:return dict(certified=False,reason='Minimo identità LP non certificato')
        forced[key]=max(0,float(r.fun)-1e-6)
    for cat,vector in cats.items():
        _,r=solver.solve(problem,vector,relax=True)
        if not r.success:return dict(certified=False,reason='Minimo categoria LP non certificato')
        minima[cat]=max(0,float(r.fun)-1e-6)
    fruit_keys={k for k in identities if any(category(foods[c['food_id']],c['meal'])=='frutta' and k in io.components(c['food_id'],foods,profile) for c in choices)}
    forced_total=sum(forced.values());fruit_bound=minima['frutta'] if len(fruit_keys)==2 and minima['frutta']>0 else 0
    fruit_forced=sum(forced[k] for k in fruit_keys)
    # Three nonempty supports over two identities contain a nested pair.
    combined=forced_total+max(0,fruit_bound-fruit_forced)
    # For the synthetic standard branches: 14 principal servings, max occurrences,
    # distinct canonical identities, all with a positive serving minimum.
    protein_bound=0.;protein_details=None
    principal=[c for c in choices if c.get('principal_protein')]
    if principal and not any(c.get('locked') or c.get('recipe_id') for c in choices):
        codes={c['food_id'] for c in principal};keys={io.canonical(i,foods,profile) for i in codes}
        if len(codes)==len(keys) and all(c['meal'] in ('lunch','dinner') for c in principal):
            support_min=math.ceil(14/maximum);shared_ids=max(0,2*support_min-len(keys))
            # Bounds come from the configuration; infer q/y lower coefficients.
            lows=[]
            for c in principal:
                candidates=[-r['coefficients'][c['y']] for r in problem['constraints'] if r['relation']=='>=' and r['rhs']==0 and r['coefficients'][c['q']]==1 and r['coefficients'][c['y']]<0 and sum(v!=0 for v in r['coefficients'])==2]
                lows.append(max(candidates,default=0))
            vector=np.zeros(size)
            for c in principal:vector[c['q']]+=1
            _,minimum_mass=solver.solve(problem,vector,relax=True)
            if not minimum_mass.success:return dict(certified=False,reason='Minimo massa proteica LP non certificato')
            missing_max=len(keys)-support_min
            source_caps=sorted((maximum*max(problem['variables'][c['q']]['ub'] for c in principal if c['food_id']==code) for code in codes),reverse=True)
            protein_bound=max(shared_ids*min(lows,default=0),float(minimum_mass.fun)-sum(source_caps[:missing_max])-1e-6)
            protein_keys=keys;already=sum(forced.get(k,0) for k in protein_keys)
            combined+=max(0,protein_bound-already)
            protein_details=dict(support_min=support_min,domain_identities=len(keys),shared_identities_min=shared_ids,grams_min=protein_bound,weekly_mass_min_g=float(minimum_mass.fun),absent_sources_max=missing_max,absent_mass_upper_g=sum(source_caps[:missing_max]))
    return dict(certified=True,certification='bound_relaxation_LP_optimal_plus_support_proof_not_optimum',
        total_mass_upper_g=total_max,category_mass_lower_g=minima,forced_identity_mass_lower_g=forced,
        fruit_domain_identities=len(fruit_keys),nested_fruit_pair_g=fruit_bound,protein_support_bound=protein_details,
        overlap_lower_bound_pct=min(100,100*combined/total_max),universally_shared_g=forced_total,
        precision='floating_point_LP_with_1e-6g_downward_margin',solver_budget_seconds=solver.seconds)


def synthetic_profile(mode,index,folder,variant):
    c=audit_config(mode)
    if mode!='free':
        # These are invented experiment schedules, never copies of owner diets.
        a=[diet.STARCH,diet.VEG,diet.PROTEIN+diet.LEGUMES,diet.FRUIT]
        b=copy.deepcopy(a)
        if index==7:b[0]=diet.RICE
        if mode=='training':b[1]=diet.VEG[:2]
        rules={mode:{'A':[a],'B':[b]}}
        if variant=='pairings_relaxed':rules[mode]['B']=[a]
        rules_path=folder/(mode+'-rules.json');schedule_path=folder/(mode+'-schedule.json')
        rules_path.write_text(json.dumps(rules));schedule_path.write_text(json.dumps(dict(weeks=[[dict(lunch='A',dinner='B') for _ in range(7)] for _ in range(2)])))
        c.update(rules_path=str(rules_path),schedule_path=str(schedule_path))
    if variant=='portion_bounds_relaxed':c['portion_bounds_g']={}
    if variant=='habits_removed':
        c['main_meals_targets']=copy.deepcopy(c['daily_meals']['targets']);c['daily_meals']['enabled']=False
    if variant=='candidate_expansion':
        for group,ids in EXPANDED.items():
            if mode=='free':
                low=50 if group=='STARCH' else 100
                c['portion_bounds_g'].update({i:[low,low] for i in ids})
    profile=dict(mode=mode,config=c)
    if variant=='recipe_candidates':
        profile['_preferred_recipe_ids']=[r['id'] for r in recipe_inventory(diet.load_foods())['rows'] if r['status']=='ready_crea_only']
    return profile


@contextlib.contextmanager
def experiment(variant):
    with contextlib.ExitStack() as stack:
        if variant=='recipe_candidates':
            import calculate_recipe_nutrients as calculator
            foods=diet.load_foods()
            def lookup(source,identifier):
                if source!='CREA' or identifier not in foods:raise ValueError('Fonte fuori dal controllo CREA-only')
                return dict(foods[identifier],nutrient_basis='per_100_g')
            stack.enter_context(replace_attribute(calculator,'food_lookup',lookup))
        if variant=='candidate_expansion':
            for name,value in EXPANDED.items():stack.enter_context(replace_attribute(diet,name,value))
        if variant=='reverse_order':
            for name in ('STARCH','VEG','PROTEIN','LEGUMES','FRUIT'):
                stack.enter_context(replace_attribute(diet,name,list(reversed(getattr(diet,name)))))
        if variant=='vegetable_identities':
            original=io.canonical
            def finer(identifier,foods,profile=None):
                key=original(identifier,foods,profile)
                return 'vegetable:'+foods[identifier].get('source_id',identifier) if key=='vegetable' else key
            stack.enter_context(replace_attribute(io,'canonical',finer))
        if variant=='one_gram_portions':
            original=diet.formulate
            def one_gram(config,foods):
                p,choices,slots=original(config,foods)
                for i,v in enumerate(p['variables']):
                    if 'portion_steps' in v['name']:
                        v['ub']*=5
                        for row in p['constraints']:
                            if row['coefficients'][i]==-5:row['coefficients'][i]=-1
                return p,choices,slots
            # weekly_model has an imported binding; only this local experiment changes it.
            stack.enter_context(replace_attribute(week,'formulate',one_gram))
        yield


async def run_one(mode,index,variant,args,folder):
    begun=time.monotonic();solver=Solver(args.solve_limit)
    with experiment(variant):
        profile=synthetic_profile(mode,index,folder,variant)
        request=dict(week_start='2026-10-05',day_index=index,k=3,pool_size=3,time_limit=args.time_limit,
                     solve_time_limit=args.solve_limit,max_protein_repetitions=14 if variant=='frequencies_relaxed' else 3)
        foods=diet.load_foods()
        model,blocks,choices,maximum=week.weekly_model(profile,request,factory,foods)
        if variant=='one_locked_meal':
            # Locks are constructed from a synthetic feasible reference, never from a DB.
            first,_=solver.solve(model)
            if first['mathematical_status'] in ('optimal','feasible'):
                reference=week.decode_week(model,blocks,foods,first,maximum)
                selected=[s for s in reference['days'][0]['selections'] if s['meal']=='lunch' and s['grams']>0]
                request['locked']=[dict(date='2026-10-05',slot='lunch',items=[dict(food=dict(source='CREA',id=s['food_id']),grams=int(round(s['grams']))) for s in selected])]
                model,blocks,choices,maximum=week.weekly_model(profile,request,factory,foods)
        if args.bounds_only:
            return dict(scenario=mode+':'+str(index//7+1),variant=variant,
                        theoretical=theoretical(model,choices,foods,profile,solver,maximum),
                        elapsed_seconds=time.monotonic()-begun,solver_calls=solver.calls)
        async def local(session,p):return solver.solve(p)[0]
        with replace_attribute(diet,'solve_problem',local):
            envelope=await week.generate_week(None,profile,request,factory,foods)
        result=dict(scenario=mode+':'+str(index//7+1),scope='public_free_audit' if mode=='free' else 'synthetic_proxy_not_owner_diet',
            variant=variant,status=envelope['status'],alternatives=len(envelope['plans']),
            budget=dict(per_solve_seconds=args.solve_limit,alternative_search_seconds=args.time_limit,
                        note='Il generatore avvia il budget alternative dopo il riferimento; non è un limite globale di wall time'),
            elapsed_seconds=time.monotonic()-begun,search_certificates=envelope['pool'].get('overlap_searches',[]),
            all_constraints_verified=bool(envelope['plans']) and all(p['constraint_report']['all_respected'] for p in envelope['plans']),
            certification='observed_verified_feasible_pool_not_global_three_plan_optimum',
            decomposition=decomposition(envelope['plans'],foods,profile),
            candidate_ids=sorted({c['food_id'] for c in choices}),candidate_canonical_ids=sorted({k for c in choices for k in io.components(c['food_id'],foods,profile)}),
            model=dict(variables=len(model['variables']),constraints=len(model['constraints'])))
        if variant in ('baseline','candidate_expansion'):
            result['theoretical']=theoretical(model,choices,foods,profile,solver,maximum)
            bound=result['theoretical']
            achieved=result['decomposition']['max_overlap_pct']
            closed=bool(bound.get('certified') and len(envelope['plans'])==3 and achieved is not None and abs(achieved-bound['overlap_lower_bound_pct'])<1e-5)
            result['global_overlap_certificate']=dict(certified=closed,
                reason='Limite inferiore esterno coincidente con una terna fattibile' if closed else 'Divario globale non chiuso',
                tolerance_percentage_points=1e-5)

        result['solver_calls']=solver.calls
        result['total_elapsed_seconds']=time.monotonic()-begun
        return result


def recipe_inventory(foods):
    """Disponibilità condizionata ai soli candidati CREA; nessuna lettura SQLite OFF."""
    import calculate_recipe_nutrients as calculator
    import recipe_intents
    from diary_service import DomainError
    recipes=json.loads((ROOT/'config/recipe-solver.json').read_text())['recipes']
    def lookup(source,identifier):
        if source!='CREA' or identifier not in foods:raise ValueError('Fonte fuori dal controllo CREA-only')
        return dict(foods[identifier],nutrient_basis='per_100_g')
    rows=[]
    with replace_attribute(calculator,'food_lookup',lookup):
        for recipe in recipes:
            try:
                result=recipe_intents.materialize(recipe['id'],{})
                rows.append(dict(id=recipe['id'],title=recipe['title'],status='ready_crea_only',
                                 ingredients=len(result['selections'])))
            except DomainError as error:
                rows.append(dict(id=recipe['id'],title=recipe['title'],status='not_ready_crea_only',reason=str(error)))
    return dict(rows=rows,ready_crea_only=sum(r['status']=='ready_crea_only' for r in rows),
                certification='deterministic_recalculation_CREA_only_not_owner_or_OFF_ready_count',solver_budget_seconds=0)


async def main(args):
    foods=diet.load_foods()
    inventory={name:[dict(id=i,name=foods[i]['name'],canonical=io.canonical(i,foods),category=foods[i].get('category')) for i in ids] for name,ids in EXPANDED.items()}
    templates=json.loads((ROOT/'config/recipe-solver.json').read_text())['recipes']
    output=dict(version='variety-diagnosis-v1',inputs='public_CREA_CSV_config_and_generated_synthetic_rules_only',
        crea_sha256=hashlib.sha256((ROOT/'dataset/crea/foods.csv').read_bytes()).hexdigest(),
        budgets=dict(per_solve_seconds=args.solve_limit,alternative_search_seconds=args.time_limit),
        inventory=inventory,recipe_inventory=recipe_inventory(foods),reviewed_recipe_templates=len(templates),recipe_note='Conteggio statico template, non certificazione ready; nessun lookup OFF SQLite',results=[])
    jobs=[(m,i,'baseline') for m in ('free','sedentary','training') for i in ([0] if m=='free' else [0,7])]
    if not args.baselines_only:
        jobs += [('free',0,v) for v in ('candidate_expansion','vegetable_identities','frequencies_relaxed','one_gram_portions','portion_bounds_relaxed','one_locked_meal','reverse_order','recipe_candidates')]
        jobs += [('sedentary',7,v) for v in ('candidate_expansion','vegetable_identities','frequencies_relaxed','one_gram_portions','pairings_relaxed','habits_removed','reverse_order')]
    if args.scenarios and args.variants:
        scenarios=[(m,i) for m in ('free','sedentary','training') for i in ([0] if m=='free' else [0,7])]
        valid={j[2] for j in jobs}
        requested=args.variants.split(',')
        if set(requested)-valid:raise ValueError('Variante non riconosciuta')
        jobs=[(m,i,v) for m,i in scenarios for v in requested if not ((m=='free' and v=='habits_removed') or (m!='free' and v=='recipe_candidates'))]
    if args.variants:jobs=[j for j in jobs if j[2] in args.variants.split(',')]
    if args.scenarios:jobs=[j for j in jobs if j[0]+':'+str(j[1]//7+1) in args.scenarios.split(',')]
    if not jobs:raise ValueError('Nessun esperimento selezionato')
    with tempfile.TemporaryDirectory(prefix='variety-synthetic-') as temp:
        for mode,index,variant in jobs:
            result=await run_one(mode,index,variant,args,Path(temp));output['results'].append(result)
            Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
            summary=dict(scenario=result['scenario'],variant=variant,elapsed_seconds=result.get('total_elapsed_seconds',result['elapsed_seconds']))
            if 'decomposition' in result:summary.update(alternatives=result['alternatives'],max_overlap_pct=result['decomposition']['max_overlap_pct'])
            else:summary.update(lower_bound_pct=result['theoretical'].get('overlap_lower_bound_pct'))
            print(json.dumps(summary,ensure_ascii=False),flush=True)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/tmp/variety-diagnosis.json')
    parser.add_argument('--solve-limit',type=float,default=5)
    parser.add_argument('--time-limit',type=float,default=90)
    parser.add_argument('--baselines-only',action='store_true')
    parser.add_argument('--bounds-only',action='store_true',help='Calcola solo i limiti LP, senza generare piani')
    parser.add_argument('--variants',help='Varianti separate da virgola')
    parser.add_argument('--scenarios',help='Scenari separati da virgola, per esempio free:1,sedentary:2')
    args=parser.parse_args()
    if not math.isfinite(args.solve_limit) or not 0<args.solve_limit<=180 or not math.isfinite(args.time_limit) or not 1<=args.time_limit<=180:parser.error('Budget non valido')
    asyncio.run(main(args))

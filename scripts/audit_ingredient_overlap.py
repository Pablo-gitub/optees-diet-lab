#!/usr/bin/env python3
"""Read-only before/after audit, publishing aggregates only (no owner DB).

Usage: PYTHONPATH=scripts:. python scripts/audit_ingredient_overlap.py
SciPy/HiGHS is an independent diagnostic solver; production uses Optees.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import subprocess
import types
from pathlib import Path
from unittest.mock import patch
import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp
import week_orchestration as current
from daily_meals import defaults
from ingredient_overlap import amounts,overlap
from plan_diet_day import load_foods
ROOT=Path(__file__).resolve().parents[1]


def solve(problem,seconds):
    rows=problem['constraints']
    result=milp(np.array(problem['objective']['coefficients']),integrality=[int(v['integrality']!='C') for v in problem['variables']],bounds=Bounds([v['lb'] for v in problem['variables']],[v['ub'] for v in problem['variables']]),constraints=LinearConstraint(np.array([r['coefficients'] for r in rows]),[r['rhs'] if r['relation'] in ('=','>=') else -np.inf for r in rows],[r['rhs'] if r['relation'] in ('=','<=') else np.inf for r in rows]),options=dict(time_limit=min(seconds,problem.get('solver',{}).get('time_limit',seconds))))
    return dict(mathematical_status='optimal' if result.success else 'feasible' if result.x is not None else 'infeasible' if result.status==2 else 'unknown',validation=dict(status='verified'),result=dict(variables=[] if result.x is None else [dict(name=v['name'],value=float(x)) for v,x in zip(problem['variables'],result.x)]))


def factory(profile,day):
    c=copy.deepcopy(profile['config']);c['day_index']=day;return c


def config(mode):
    c=json.loads((ROOT/'config/demo-diet-day.json').read_text());c['mode']=mode
    if mode=='free':
        # Public synthetic weighable servings for a tractable repeatable demo.
        c['portion_bounds_g']={i:[50,50] for i in ('000800','000100','000530')}
        c['portion_bounds_g'].update({i:[120,120] for i in ('106500','121410','181100','123610','004005','004125','004505','110020','110400')})
        c['portion_bounds_g'].update({i:[100,100] for i in ('005730','006600','005410','007120','007260')})
        c['portion_bounds_g'].update({i:[40,40] for i in ('008540','008570')});c['portion_bounds_g'].update({'166000':[30,30],'009210':[10,10]})
    else:c.update(daily_meals=defaults(True),food_preferences={})
    return c


async def audit(args):
    old=types.ModuleType('baseline_week')
    source=subprocess.check_output(['git','show',args.baseline+':scripts/week_orchestration.py'],cwd=ROOT).decode()
    exec(compile(source,'baseline_week','exec'),old.__dict__)
    out=dict(baseline=args.baseline,solve_limit_seconds=args.solve_limit,total_limit_seconds=args.time_limit,canonical_version='ingredient-overlap-v1',scope='synthetic_demo_targets_and_personal_rules_no_owner_data',results=[])
    for mode in ('free','sedentary','training'):
        for index in ([0] if mode=='free' else [0,7]):
            for label,engine in [('before',old),('after',current)]:
                async def local(session,p):return solve(p,args.solve_limit)
                profile=dict(mode=mode,config=config(mode))
                with patch('plan_diet_day.solve_problem',side_effect=local):r=await engine.generate_week(None,profile,dict(week_start='2026-10-05',day_index=index,k=3,pool_size=3,time_limit=args.time_limit),factory,load_foods())
                vectors=[amounts(p,load_foods()) for p in r['plans']];pairs=[overlap(a,b)*100 for i,a in enumerate(vectors) for b in vectors[:i]]
                record=dict(mode=mode,rule_week=index//7+1,engine=label,status=r['status'],alternatives=len(vectors),pairs=len(pairs),max_overlap_pct=round(max(pairs),2) if pairs else None,mean_overlap_pct=round(sum(pairs)/len(pairs),2) if pairs else None,all_nutritional_constraints_respected=all(p['constraint_report']['all_respected'] for p in r['plans']),minimax_certified=[s.get('certified',False) for s in r['pool'].get('overlap_searches',[])])
                out['results'].append(record);Path(args.output).write_text(json.dumps(out,indent=2));print(json.dumps(record),flush=True)
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',default='fe2216e');p.add_argument('--output',default='/tmp/phase8-overlap-audit.json');p.add_argument('--solve-limit',type=float,default=5);p.add_argument('--time-limit',type=float,default=120)
    asyncio.run(audit(p.parse_args()))

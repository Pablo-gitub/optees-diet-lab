import sys,json
import plan_diet_day as d
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
p=d.ROOT/'data/personal/diet_fortnight_audit.json'
a=json.loads(p.read_text());diagnoses=[]
for mode in ['sedentary','training']:
 r=next(r for r in a['records'] if r['config']['mode']==mode and r['config']['day_index']==10 and r['scenario']=='local_only')
 problem,choices,_=d.formulate(r['config'],d.load_foods())
 objective=[0.]*len(problem['variables'])
 for c in choices: objective[c['q']]=-c['nutrients'][3]
 rows=problem['constraints']
 sol=milp(np.array(objective),integrality=[v['integrality']!='C' for v in problem['variables']],bounds=Bounds([v['lb'] for v in problem['variables']],[v['ub'] for v in problem['variables']]),constraints=LinearConstraint([x['coefficients'] for x in rows],[x['rhs'] if x['relation'] in ['>=','='] else -np.inf for x in rows],[x['rhs'] if x['relation'] in ['<=','='] else np.inf for x in rows]))
 assert sol.success
 diagnoses.append(dict(mode=mode,day=11,maximum_carbs_g_in_subset=-sol.fun,required_minimum=90,solver='independent SciPy/HiGHS diagnostic'))
a['diagnoses']=diagnoses;p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
report=d.ROOT/'data/personal/diet_fortnight_audit.md'
with report.open('a') as f:
 f.write('\n## Diagnosi dei due casi senza soluzione\n\n')
 for x in diagnoses: f.write(f"- {x['mode']}, giorno 11: massimo carboidrati nei due pasti modellati {x['maximum_carbs_g_in_subset']:.2f} g, contro minimo demo 90 g.\n")
print(diagnoses)

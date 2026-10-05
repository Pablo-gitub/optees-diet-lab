"""Read-only rejection of malformed or unsafe solver results, with bounded diagnostics."""
import math


def failure(error,stage,phase,problem=None,result=None,choices=()):
    variables=[]
    try:
        by_name={v['name']:v['value'] for v in result['result']['variables']}
        for index,spec in enumerate(problem['variables']):
            value=by_name.get(spec['name'])
            numeric=isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
            if numeric and spec['lb']-1e-5<=value<=spec['ub']+1e-5 and (spec['integrality']=='C' or abs(value-round(value))<=1e-5):continue
            detail=dict(name=spec['name'],value=value if numeric else None,lower=spec['lb'],upper=spec['ub'],integrality=spec['integrality'])
            choice=next((c for c in choices if c['q']==index),None)
            if choice:detail.update(date=choice['date'],slot=choice['meal'],food_id=choice['food_id'],reference_grams=choice.get('locked_grams'))
            variables.append(detail)
            if len(variables)==12:break
    except Exception:pass
    text=str(error)
    if phase=='solver':
        reason='Optees non ha completato il calcolo del rientro. Riprova l’anteprima.'
        code='solver_unavailable'
    elif variables or 'Variabile fuori limite' in text:
        reason='Il risultato di Optees non è verificabile: una quantità o variabile è fuori dai limiti ammessi.'
        code='variable_out_of_bounds'
        if variables and variables[0].get('food_id'):
            v=variables[0]
            reason+=' Pasto '+v['slot']+' del '+v['date']+': limiti '+str(v['lower'])+'–'+str(v['upper'])+' g.'
    elif isinstance(error,(KeyError,TypeError,AttributeError,IndexError)):
        reason='Il risultato di Optees è incompleto o contiene valori non validi: impossibile verificarlo.'
        code='invalid_result'
    else:
        reason='Il risultato di Optees non supera la verifica dei vincoli e dei limiti di sicurezza.'
        code='constraints_not_verified'
    return reason,dict(status='failed',stage=stage,phase=phase,code=code,error_type=type(error).__name__,variables=variables)

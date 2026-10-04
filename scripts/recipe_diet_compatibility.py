"""Structural recipe-to-diet matching; never certifies nutrients or a whole day."""
import argparse
import hashlib
import json
from pathlib import Path
from plan_recipe import templates
ROOT=Path(__file__).resolve().parents[1]
GROUPS=ROOT/'config/recipe-diet-food-groups.json'
RULES=ROOT/'data/personal/recipe_diet_semantic_rules.json'
LABELS={'compatible':'Abbinamento modellato coperto','needs_complements':'Da completare con altri alimenti','needs_review':'Nessun abbinamento verificato'}

def classify(recipe,groups):
    ingredients=[]
    for ingredient in recipe['ingredients']:
        candidates=ingredient['candidates']
        categories={groups['foods'].get(c['source']+':'+c['id']) for c in candidates}
        checked=bool(candidates) and all(c.get('reviewed') is True and c.get('state_checked') is True for c in candidates)
        group=next(iter(categories)) if checked and len(categories)==1 and None not in categories else None
        # Identity is the verified reference food, independent of brand alternatives.
        identity=candidates[0]['source']+':'+candidates[0]['id'] if candidates else ingredient['key']
        ingredients.append(dict(key=ingredient['key'],name=ingredient['name'],group=group,identity=identity,
            reason=None if group else 'Gruppo o ruolo non verificato per tutte le alternative del prodotto'))
    return ingredients


def match_branch(ingredients,branch,letter):
    assigned={r['name']:[] for r in branch['required_roles']};blocked=[];condiments=[]
    for ingredient in ingredients:
        group=ingredient['group']
        if group in branch['condiments']:
            condiments.append(ingredient['key']);continue
        roles=[r for r in branch['required_roles'] if group and group in r['groups']]
        if len(roles)!=1:
            blocked.append(dict(ingredient=ingredient['name'],reason=ingredient['reason'] or 'Ingrediente non ammesso in questo ramo modellato',group=group));continue
        assigned[roles[0]['name']].append(ingredient)
    for role in branch['required_roles']:
        used=assigned[role['name']]
        if role.get('one_food_only',True) and len({i['identity'] for i in used})>1:
            blocked.append(dict(role=role['name'],reason='La scheda richiede una scelta: sono presenti più alimenti distinti',ingredients=[i['name'] for i in used]))
    missing=[r['name'] for r in branch['required_roles'] if not assigned[r['name']]]
    status='needs_review' if blocked else 'needs_complements' if missing else 'compatible'
    return dict(letter=letter,branch_id=branch['id'],status=status,label=LABELS[status],missing_roles=missing,
        complement_options=[dict(role=r['name'],allowed_groups=r['groups']) for r in branch['required_roles'] if r['name'] in missing],
        blocked=blocked,assigned_roles={role:[i['name'] for i in used] for role,used in assigned.items()},condiment_keys=condiments)


def assess(recipe,mode,expression,rules=None,groups=None):
    if mode=='free':
        return dict(recipe_id=recipe['id'],title=recipe['title'],status='unconstrained',label='Modalità libera: nessun vincolo sugli abbinamenti',branches=[],ingredients=[],scope='ingredients_only',nutrition_checked=False)
    if mode not in ['sedentary','training']:raise ValueError('Modalità non valida')
    rules=rules if rules is not None else json.loads(RULES.read_text())['rules']
    groups=groups if groups is not None else json.loads(GROUPS.read_text())
    letters=expression.split(' oppure ')
    if any(letter not in rules[mode] for letter in letters):raise ValueError('Lettera senza regole verificate')
    ingredients=classify(recipe,groups)
    branches=[match_branch(ingredients,branch,letter) for letter in letters for branch in rules[mode][letter]]
    rank={'compatible':0,'needs_complements':1,'needs_review':2}
    status=min((b['status'] for b in branches),key=rank.get,default='needs_review')
    return dict(recipe_id=recipe['id'],title=recipe['title'],status=status,label=LABELS[status],expression=expression,branches=branches,ingredients=ingredients,
        scope='ingredients_only',nutrition_checked=False,coverage='modeled_branches_only',
        note='Verifica dei gruppi degli ingredienti nei rami modellati. Non verifica quantità, obiettivi nutrizionali, altri pasti o tutte le alternative della scheda. I complementi mancanti non vengono aggiunti automaticamente.')


def meal_options(mode,day_index,meal,recipes=None):
    if isinstance(day_index,bool) or not isinstance(day_index,int) or not 0<=day_index<14:raise ValueError('Giorno non valido')
    if meal not in ['lunch','dinner']:raise ValueError('Pasto non valido')
    recipes=templates() if recipes is None else recipes
    if mode=='free':return dict(mode=mode,day_index=day_index,meal=meal,expression='free',recipes=[assess(r,'free','free') for r in recipes])
    if mode not in ['sedentary','training']:raise ValueError('Modalità non valida')
    schedule=ROOT/f'data/personal/ocr/{mode}/schedule_visual_checked.json'
    expression=json.loads(schedule.read_text())['weeks'][day_index//7][day_index%7][meal]
    rules=json.loads(RULES.read_text())['rules'];groups=json.loads(GROUPS.read_text())
    result=dict(mode=mode,day_index=day_index,meal=meal,expression=expression,
        recipes=[assess(r,mode,expression,rules,groups) for r in recipes],
        rules_sha256=hashlib.sha256(RULES.read_bytes()).hexdigest(),groups_sha256=hashlib.sha256(GROUPS.read_bytes()).hexdigest(),
        schedule_sha256=hashlib.sha256(schedule.read_bytes()).hexdigest())
    result['counts']={s:sum(r['status']==s for r in result['recipes']) for s in LABELS}
    return result


def audit(output):
    rows=[meal_options(mode,day,meal) for mode in ['sedentary','training'] for day in range(14) for meal in ['lunch','dinner']]
    result=dict(scope='Ingredients only; modeled branches, not complete personal diet or nutrition approval',
        templates_sha256=hashlib.sha256((ROOT/'config/recipe-solver.json').read_bytes()).hexdigest(),checks=rows)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({mode:{status:sum(row['counts'][status] for row in rows if row['mode']==mode) for status in LABELS} for mode in ['sedentary','training']},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'data/personal/recipe_diet_compatibility_audit.json');args=parser.parse_args();audit(args.output)

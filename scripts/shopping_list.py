"""Owner shopping totals from applied plans; no guessed recipe composition."""
import datetime as dt
import json
import math
import re
import sqlite3
from pathlib import Path
from functools import lru_cache
import diary_service as diary
ROOT=Path(__file__).resolve().parents[1]
DEPARTMENTS=('Ortofrutta','Carne e pesce','Latticini e uova','Pasta, riso e cereali','Legumi e conserve','Dispensa','Condimenti in traccia')


def package_grams(quantity):
    if not isinstance(quantity,str):return None
    match=re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(g|kg)\s*',quantity,re.I)
    if not match:return None
    value=float(match[1].replace(',','.'))*(1000 if match[2].lower()=='kg' else 1)
    return value if value>0 else None


@lru_cache(maxsize=1)
def reviewed_generics():
    from plan_recipe import templates
    refs={}
    for recipe in templates():
        for ingredient in recipe['ingredients']:
            candidates=[c for c in ingredient['candidates'] if c.get('reviewed') is True and c.get('state_checked') is True]
            generic={c['id'] for c in candidates if c['source']=='CREA'}
            if len(generic)!=1:continue
            for c in candidates:
                if c['source'] in ('OFF','Open Food Facts'):refs.setdefault(c['id'],set()).update(generic)
    return {code:next(iter(ids)) for code,ids in refs.items() if len(ids)==1}


def canonical_ref(ref,profile):
    source={'Open Food Facts':'OFF'}.get(ref['source'],ref['source']);code=ref['id']
    for generic,product in profile.get('food_preferences',{}).get('preferred_products',{}).items():
        if product==dict(source=source,id=code):return 'CREA:'+generic,dict(source='CREA',id=generic)
    generic=reviewed_generics().get(code) if source=='OFF' else None
    if generic:return 'CREA:'+generic,dict(source='CREA',id=generic)
    return source+':'+code,dict(source=source,id=code)


def department(name):
    name=name.casefold()
    for label,pattern in [('Carne e pesce',r'pollo|carne|manzo|vitello|maiale|tacchino|pesce|tonno|salmone|merluzzo'),('Latticini e uova',r'latte|yogurt|formaggio|mozzarella|ricotta|uov|burro'),('Pasta, riso e cereali',r'pasta|spaghetti|riso|pane|farina|avena|cereal|cracker'),('Legumi e conserve',r'ceci|fagiol|lenticch|piselli|conserv'),('Ortofrutta',r'pomodor|zucchin|cipoll|agli|mela|mele|banana|pera|pere|insalata|frutta|verdura|carot|patat|spinac|broccol')]:
        if re.search(pattern,name):return label
    return 'Dispensa'


def read_week(db,user,profile,start):
    start=diary.valid_date(start)
    row=db.execute("SELECT * FROM week_plan WHERE user_id=? AND week_start=? AND status='active'",(user,start)).fetchone()
    if not row:raise diary.DomainError('Nessuna settimana applicata per questa data','week_not_applied',404)
    return dict(row),[diary.day_view(db,user,profile,(dt.date.fromisoformat(start)+dt.timedelta(days=i)).isoformat()) for i in range(7)]


def shopping_list(db,user,profile,start,include_all=False,today=None):
    week,views=read_week(db,user,profile,start);today=today or diary.local_today();items={};traces={};unresolved=[];meals=0
    def trace(name):
        label={'salt and pepper':'Sale e pepe','salt & pepper':'Sale e pepe','salt and black pepper':'Sale e pepe nero'}.get(name.casefold(),name)
        traces[label.casefold()]=dict(name=label,grams=None,department='Condimenti in traccia')
    def add(ref,grams,location,name=None,depth=0):
        if depth>8:raise diary.DomainError('Ricetta ricorsiva non risolvibile')
        source={'Open Food Facts':'OFF'}.get(ref['source'],ref['source']);ref=dict(source=source,id=ref['id'])
        if source=='dish_estimate':
            unresolved.append(dict(food=ref,grams=None,reason='Piatto stimato senza composizione: inserisci gli ingredienti da acquistare.'));return
        if source=='water':return
        if source=='condiment':trace(name or 'Condimento in traccia');return
        if source=='stock':
            from recipe_special_sources import POLICY
            add(dict(source='CREA',id=POLICY['stock']['base_id']),grams*POLICY['stock']['cube_g_per_100g_liquid']/100,location,'Dado per brodo diluito',depth+1);return
        if source=='recipe':
            if ref['id']=='vegetable_puree':
                food=diary.resolve_food(ref,profile);components=food['composition_provenance']['ingredients']
                for part in components:
                    if part.get('id'):add(dict(source=part['source'],id=part['id']),grams*part['fraction'],location,part.get('name'),depth+1)
                return
            recipe=profile.get('_recipe_runs',{}).get(ref['id'])
            if not recipe or recipe.get('status') not in ('optimal','feasible'):
                unresolved.append(dict(food=ref,grams=grams,reason='Composizione della ricetta non verificata'));return
            mass=sum(i['grams'] for i in recipe['selections'])
            if mass<=0:raise diary.DomainError('Massa della ricetta non valida')
            for part in recipe['selections']:add(dict(source=part['source'],id=part['id']),grams*part['grams']/mass,location,part.get('food') or part.get('ingredient'),depth+1)
            for part in recipe.get('trace_condiments',[]):trace(part['name'])
            return
        key,generic=canonical_ref(ref,profile)
        food=diary.resolve_food(generic,profile)
        entry=items.setdefault(key,dict(canonical_id=key,food=generic,name=food['name'],grams=0.,occurrences=0,department=department(food['name']),locations=[]))
        entry['grams']+=grams;entry['occurrences']+=1
        if location not in entry['locations']:entry['locations'].append(location)
    for view in views:
        if not include_all and view['date']<today.isoformat():continue
        for meal in view['meals']:
            if not meal['planned'] or not include_all and meal['state']!='unknown':continue
            meals+=1
            for item in meal['planned']['items']:add(item['food'],item['grams'],dict(date=view['date'],slot=meal['slot']),item.get('name'))
    warnings=[]
    for item in items.values():
        generic=item['food'];preferred=profile.get('food_preferences',{}).get('preferred_products',{}).get(generic['id']) if generic['source']=='CREA' else None
        item['product']=preferred or generic;product=diary.resolve_food(item['product'],profile)
        item['product_name']=product['name'];item['brand']=product.get('brand');pack=None
        if item['product']['source']=='OFF':
            with sqlite3.connect('file:'+str(ROOT/'dataset/open_food_facts/catalog.sqlite')+'?mode=ro',uri=True) as catalog:
                row=catalog.execute('SELECT payload FROM products WHERE barcode=?',(item['product']['id'],)).fetchone()
            if row:pack=package_grams(json.loads(row[0]).get('quantity'))
        elif item['product']['source']=='user_label':
            label=next(p for p in profile['food_preferences']['products'] if p['id']==item['product']['id']);pack=label.get('package_g')
        item.update(grams=round(item['grams'],3),package_g=pack,packages=math.ceil(item['grams']/pack) if pack else None)
        if preferred:warnings.append('Il prodotto preferito è una proposta di acquisto; questa lista non ricalcola i nutrienti del piano.')
    result=sorted(items.values(),key=lambda x:(DEPARTMENTS.index(x['department']),x['name'].casefold()))
    return dict(week_start=start,status='partial' if unresolved else 'ok',scope='whole_applied_week' if include_all else 'remaining_unconsumed_meals',as_of=today.isoformat(),included_meals=meals,items=result,trace_condiments=sorted(traces.values(),key=lambda x:x['name']),unresolved=unresolved,warnings=sorted(set(warnings)),identity_rule='Precise CREA id or unambiguous reviewed recipe ingredient; preferred brands map to that exact generic id; unmapped products retain their source id')

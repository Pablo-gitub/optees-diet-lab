"""Local GTIN lookup and owner labels. Never performs network requests."""
import copy
import json
import math
import sqlite3
import uuid
from pathlib import Path
from diary_service import DomainError,resolve_food
from daily_meals import products
ROOT=Path(__file__).resolve().parents[1]
FIELDS={'barcode','name','brand','basis','serving_g','density_g_per_ml','kcal','kj','protein_g','carbs_g','fat_g','sugars_g','fiber_g','salt_g','package_g'}


def gtin(value):
    if not isinstance(value,str) or len(value) not in (8,12,13,14) or not value.isascii() or not value.isdigit():raise DomainError('GTIN deve essere una stringa di 8, 12, 13 o 14 cifre')
    check=(10-sum(int(x)*(3 if i%2==0 else 1) for i,x in enumerate(value[-2::-1]))%10)%10
    if check!=int(value[-1]):raise DomainError('Cifra di controllo GTIN non valida')
    return value


def number(value,label,low=0,high=10000):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:raise DomainError(label+' non valido')
    return value


def normalize(data,identifier):
    if not isinstance(data,dict) or set(data)-FIELDS:raise DomainError('Campi etichetta non validi')
    name=data.get('name');basis=data.get('basis')
    if not isinstance(name,str) or not name.strip() or len(name)>200 or basis not in ('per_100g','per_100ml','per_serving'):raise DomainError('Nome o base dell’etichetta non validi')
    brand=data.get('brand')
    if brand is not None and (not isinstance(brand,str) or len(brand)>200):raise DomainError('Marca non valida')
    barcode=gtin(data['barcode']) if data.get('barcode') is not None else None
    if ('kcal' in data)==('kj' in data):raise DomainError('Indica kcal oppure kJ')
    energy=number(data.get('kcal',data.get('kj')),'Energia')/(4.184 if 'kj' in data else 1)
    for key in ('protein_g','carbs_g','fat_g'):number(data.get(key),key,0,1000)
    for key in ('sugars_g','fiber_g','salt_g'):
        if key in data:number(data[key],key,0,1000)
    if data.get('sugars_g',0)>data['carbs_g']:raise DomainError('Zuccheri superiori ai carboidrati')
    for key in ('serving_g','density_g_per_ml','package_g'):
        if data.get(key) is not None:number(data[key],key,.001,10000 if key!='density_g_per_ml' else 10)
    if basis=='per_serving' and data.get('serving_g') is None:raise DomainError('Peso della porzione richiesto')
    volume=basis=='per_100ml' and data.get('density_g_per_ml') is None
    basis_g=data['serving_g'] if basis=='per_serving' else 100*data['density_g_per_ml'] if basis=='per_100ml' and not volume else 100
    serving=data.get('serving_g') or basis_g
    product=dict(id=identifier,name=name.strip(),brand=brand,barcode=barcode,basis=basis,label=copy.deepcopy(data),serving_g=None if volume else serving,label_basis_g=None if volume else basis_g,label_nutrients={k:data[k] for k in ('protein_g','carbs_g','fat_g')},kcal_per_serving=energy*serving/basis_g,volume_only=volume,package_g=data.get('package_g'))
    expected=4*data['protein_g']+4*data['carbs_g']+9*data['fat_g']+2*data.get('fiber_g',0)
    deviation=abs(energy-expected)/max(expected,1e-9)*100
    product['coherence']=dict(ok=deviation<=15,expected_kcal=round(expected,4),declared_kcal=round(energy,4),deviation_pct=round(deviation,4),basis=basis)
    product['solver_eligible']=not volume and product['coherence']['ok']
    if volume:product['per_100ml']=dict(kcal=energy,protein_g=data['protein_g'],fat_g=data['fat_g'],carbs_available_g=data['carbs_g'])
    # Conversion of energy/label weights has one authority, daily_meals.products.
    row=products(dict(products=[product]))[identifier]
    product['per_100g']={n:None if row[k]=='' else float(row[k]) for n,k in [('kcal','kcal_100g'),('protein_g','protein_g_100g'),('fat_g','fat_g_100g'),('carbs_available_g','carbs_available_g_100g')]}
    return product


def response(product,profile):
    return dict(food=dict(source='user_label',id=product['id']),per_100g=product['per_100g'],per_100ml=product.get('per_100ml'),coherence=product['coherence'],solver_eligible=product['solver_eligible'],label=product['label'],serving_g=product['serving_g'],package_g=product.get('package_g'))


def save(db,user,data,identifier=None):
    profile=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user,)).fetchone()[0]);prefs=profile.setdefault('food_preferences',{});labels=prefs.setdefault('products',[])
    existing=next((p for p in labels if p['id']==identifier),None) if identifier else None
    if identifier and existing is None:raise DomainError('Prodotto personale non trovato','not_found',404)
    identifier=identifier or 'label_'+uuid.uuid4().hex
    product=normalize(data,identifier)
    if product['barcode'] and any(p.get('barcode')==product['barcode'] and p['id']!=identifier for p in labels):raise DomainError('Codice già presente nei tuoi prodotti','duplicate_barcode',409)
    prefs['products']=[p for p in labels if p['id']!=identifier]+[product]
    db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(profile),user))
    return response(product,profile)


def lookup(code,profile):
    gtin(code)
    with sqlite3.connect('file:'+str(ROOT/'dataset/open_food_facts/catalog.sqlite')+'?mode=ro',uri=True) as db:row=db.execute('SELECT payload FROM products WHERE barcode=?',(code,)).fetchone()
    if row:
        label=json.loads(row[0]);food=resolve_food(dict(source='OFF',id=code),profile)
        return dict(status='found' if all(v is not None for v in food['per_100g'].values()) else 'incomplete',food=food,label=label,serving_g=label.get('serving_g'),package_g=label.get('package_g'),source='OFF')
    product=next((p for p in profile.get('food_preferences',{}).get('products',[]) if p.get('barcode')==code),None)
    if product:
        food=resolve_food(dict(source='user_label',id=product['id']),profile)
        return dict(status='found' if all(v is not None for v in food['per_100g'].values()) else 'incomplete',food=food,label=product.get('label'),serving_g=product.get('serving_g'),package_g=product.get('package_g'),source='user_label',coherence=product.get('coherence'),per_100ml=product.get('per_100ml'))
    return dict(status='not_found',source=None)


def delete(db,user,identifier):
    profile=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user,)).fetchone()[0]);prefs=profile.get('food_preferences',{});labels=prefs.get('products',[])
    if not any(p['id']==identifier for p in labels):raise DomainError('Prodotto non trovato','not_found',404)
    if db.execute('SELECT 1 FROM food_usage WHERE user_id=? AND source=? AND food_id=?',(user,'user_label',identifier)).fetchone():raise DomainError('Prodotto già usato nel diario: non eliminabile','food_used',409)
    for row in db.execute('SELECT p.items FROM planned_meal p JOIN week_plan w ON w.id=p.week_plan_id WHERE w.user_id=?',(user,)):
        if any(x['food']==dict(source='user_label',id=identifier) for x in json.loads(row[0])):raise DomainError('Prodotto presente in un piano: rimuovi prima il riferimento','food_planned',409)
    prefs['products']=[p for p in labels if p['id']!=identifier]
    for preference in prefs.get('preferences',{}).values():
        if preference.get('preferred_product_id')==identifier:preference.pop('preferred_product_id',None)
    prefs['preferred_products']={k:v for k,v in prefs.get('preferred_products',{}).items() if v!=dict(source='user_label',id=identifier)}
    db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(profile),user))
    return dict(status='deleted',food=dict(source='user_label',id=identifier))


def preferred(db,user,data):
    if not isinstance(data,dict) or set(data)!={'generic','product'}:raise DomainError('Preferenza prodotto non valida')
    generic=data['generic']
    if not isinstance(generic,dict) or generic.get('source')!='CREA':raise DomainError('Il generico deve essere CREA')
    profile=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user,)).fetchone()[0]);resolve_food(generic,profile)
    ref=data['product']
    if ref is not None:
        if not isinstance(ref,dict) or ref.get('source') not in ('OFF','user_label'):raise DomainError('Prodotto preferito non valido')
        food=resolve_food(ref,profile)
        if any(v is None for v in food['per_100g'].values()):raise DomainError('Servono valori completi per 100 g','incomplete_product')
        if ref['source']=='user_label':
            p=next(p for p in profile['food_preferences']['products'] if p['id']==ref['id'])
            if not p.get('coherence',{}).get('ok',True):raise DomainError('Etichetta incoerente: verifica i valori prima di preferirla','incoherent_product')
        else:
            with sqlite3.connect('file:'+str(ROOT/'dataset/open_food_facts/catalog.sqlite')+'?mode=ro',uri=True) as catalog:label=json.loads(catalog.execute('SELECT payload FROM products WHERE barcode=?',(ref['id'],)).fetchone()[0])
            fiber=label.get('fiber_g_100g') or 0
            expected=4*food['per_100g']['protein_g']+4*food['per_100g']['carbs_available_g']+9*food['per_100g']['fat_g']+2*float(fiber);energy=food['per_100g']['kcal']
            if abs(energy-expected)/max(expected,1e-9)>.15:raise DomainError('Etichetta incoerente: verifica i valori','incoherent_product')
    mapping=profile.setdefault('food_preferences',{}).setdefault('preferred_products',{})
    if ref is None:mapping.pop(generic['id'],None)
    else:mapping[generic['id']]=ref
    db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(profile),user))
    return dict(generic=generic,product=ref,preferred_products=mapping)

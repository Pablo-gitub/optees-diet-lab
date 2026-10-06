"""Declared special recipe sources, shared by matcher, calculator and solver."""
import json
import math
import re
from pathlib import Path
POLICY=json.loads((Path(__file__).resolve().parents[1]/'config/recipe-special-sources.json').read_text())
_CONVERSIONS_PATH=Path(__file__).resolve().parents[1]/'config/ingredient-unit-conversions.json'
APPROVED_CONVERSIONS=json.loads(_CONVERSIONS_PATH.read_text()).get('conversions',{}) if _CONVERSIONS_PATH.exists() else {}
NUTRIENTS=('kcal_100g','protein_g_100g','fat_g_100g','carbs_available_g_100g')


def positive(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0


def aromatic_trace(ing,canonical,recipe,grams,conversions=None):
    """Declared user policy, never an inferred nutritional measurement."""
    policy=POLICY.get('aromatic',{})
    if not policy:return None
    name=re.sub(r'\s+',' ',str(ing.get('name','')).strip().casefold())
    evidence=' '.join(str(v or '') for v in (name,ing.get('note'),(ing.get('source_nutrition_reference') or {}).get('description'))).casefold()
    if re.search(POLICY.get('never_trace_pattern',r'(?!)'),evidence):return None
    if re.search(r'\b(and|or|dried|dry|powder|ground|secco|secca|polvere|sauce|salsa|soup|zuppa|lemonade|limonata)\b',evidence) or '&' in evidence:
        if name not in ('soy sauce','salsa di soia'):return None
    servings=recipe.get('servings')
    if not positive(servings):return None
    quantity=ing.get('quantity');unit=str(ing.get('unit') or '').strip().casefold()
    aliases={'cloves':'clove','sprigs':'sprig','leaves':'leaf','bunches':'bunch','handfuls':'handful','slices':'slice','pieces':'piece','teaspoon':'tsp','teaspoons':'tsp','tablespoon':'tbsp','tablespoons':'tbsp'}
    unit=aliases.get(unit,unit)
    embedded=re.match(r'^(\d+(?:\.\d+)?)\s+(cloves?|sprigs?|leaves|leaf|bunch(?:es)?|handfuls?|slices?|pieces?|heads?)\s+(?:of\s+)?(.+)$',name)
    if embedded:
        if quantity is None:quantity=float(embedded[1])
        unit=aliases.get(embedded[2],embedded[2]);name=embedded[3]
    juice=re.fullmatch(r'juice\s+of\s+(?:(\d+(?:\.\d+)?)\s+)?(?:a\s+)?(lemon|lime)s?',name)
    if juice:
        quantity=float(juice[1]) if juice[1] else quantity if positive(quantity) else 1
        name=juice[2]+' juice';unit='juice_fruit'
    cleaned=re.sub(r'\b(fresh|fresco|fresca|chopped|finely|minced|grated|leaves|leaf)\b',' ',name)
    cleaned=re.sub(r'\s+',' ',cleaned).strip(' ,')
    entry=next((v for v in policy['entries'].values() if name in v['exact_names'] or cleaned in v['exact_names']),None)
    # Canonicals cover harmless preparation/name variants, never whole citrus fruit.
    if entry is None:
        cid=(canonical or {}).get('id')
        entry=next((v for v in policy['entries'].values() if cid in v['canonical_ids']),None)
    if entry is None:return None
    threshold=entry['max_g_per_serving']
    result=dict(trace_class='aromatic',max_g_per_serving=threshold,reason=policy['note'])
    if unit in ('head','heads') or re.search(r'\bheads?\b',name):return None
    if unit in policy['always_trace_units']:return result if positive(quantity) else None
    explicit=ing.get('grams_whole_recipe')
    if positive(explicit):return result if max(explicit,grams if positive(grams) else 0)/servings<=threshold else None
    if entry is policy['entries'].get('soy_sauce') and unit in policy['volume_unit_ml'] and positive(quantity) and quantity*policy['volume_unit_ml'][unit]/servings>15:return None
    if positive(grams):return result if grams/servings<=threshold else None
    if unit in policy['qualitative_units']:return result if quantity is None or positive(quantity) else None
    if not positive(quantity):return None
    if unit=='juice_fruit':return result if quantity/servings<=policy['max_juice_fruits_per_serving'] else None
    if unit not in policy['accepted_units']:return None
    cid=(canonical or {}).get('id') or (entry['canonical_ids'][0] if len(entry['canonical_ids'])==1 else None)
    conversion=(APPROVED_CONVERSIONS if conversions is None else conversions).get(cid,{}).get(unit)
    if conversion and positive(conversion.get('grams')) and conversion.get('source') and conversion.get('approved_by'):
        weight=quantity*conversion['grams']
        result['conversion']=conversion
    elif unit in policy['volume_unit_ml']:
        weight=quantity*policy['volume_unit_ml'][unit]*policy['volume_density_g_per_ml']
        result['quantity_assumption']='Proxy volumetrico dichiarato 1 g/ml, non peso misurato'
    else:return None
    return result if weight/servings<=threshold else None


def trace_allowed(ing,canonical,recipe,grams,conversions=None):
    if aromatic_trace(ing,canonical,recipe,grams,conversions):return True
    policy=POLICY['trace_condiment'];name=str(ing.get('name','')).strip().casefold()
    mixture=re.sub(r'\s+',' ',name) in ('salt and pepper','salt & pepper','salt and black pepper')
    evidence=' '.join(str(v or '') for v in (name,ing.get('note'),(ing.get('source_nutrition_reference') or {}).get('description'))).casefold()
    if re.search(POLICY.get('never_trace_pattern',r'(?!)'),evidence):return False
    checked=evidence[len(name):] if mixture else evidence
    if '&' in checked or re.search(r'\b(and|or|fresh|sugar|paste|sauce|oil|fresco|fresca|zucchero)\b',checked):return False
    eligible=mixture or (canonical or {}).get('id') in policy['canonical_ids'] or name in policy['exact_names']
    if not eligible:return False
    servings=recipe.get('servings')
    if not positive(servings):return False
    if positive(grams):return grams/servings<=policy['max_g_per_serving']
    unit=str(ing.get('unit','')).casefold();qty=ing.get('quantity')
    if unit in policy['qualitative_units']:return qty is None or positive(qty)
    if positive(qty):
        if unit=='tsp':return qty/servings<=policy['max_tsp_per_serving']
        if unit in ('count','piece') and (canonical or {}).get('id') in ('alloro_foglie','vaniglia','cannella_stecca'):return qty/servings<=policy['max_count_per_serving']
    return False


def liquid_stock(ing,canonical):
    return (canonical or {}).get('flags',{}).get('requires_dilution',False) and not re.search(r'\b(cube|cubes|powder|granules|concentrate|dado|dadi|polvere|and|or)\b',str(ing.get('name','')).casefold())


def special_food(source,identifier,lookup):
    if source=='condiment' and identifier=='trace':
        return dict(name='Condimento in traccia (0 kcal dichiarate)',category='condimento',nutrient_basis='per_100_g',declared_zero=True,approximation=POLICY['trace_condiment']['note'],**{n:0. for n in NUTRIENTS})
    if source=='stock' and identifier=='cube_1_50':
        p=POLICY['stock'];base=lookup(p['base_source'],p['base_id']);factor=p['cube_g_per_100g_liquid']/100
        values={n:float(base[n])*factor for n in NUTRIENTS}
        if any(not math.isfinite(v) or v<0 for v in values.values()):raise ValueError('Nutrienti del dado non validi')
        return dict(name='Brodo liquido da dado diluito 1:50 (proxy dichiarato)',category='brodo',nutrient_basis='per_100_g',dilution=dict(base_source=p['base_source'],base_id=p['base_id'],cube_g_per_100g_liquid=p['cube_g_per_100g_liquid'],water_g_per_100g_liquid=p['water_g_per_100g_liquid']),approximation=p['note'],**values)
    raise ValueError('Fonte speciale non valida: '+source+':'+identifier)

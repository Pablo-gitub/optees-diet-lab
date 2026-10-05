"""Declared special recipe sources, shared by matcher, calculator and solver."""
import json
import math
import re
from pathlib import Path
POLICY=json.loads((Path(__file__).resolve().parents[1]/'config/recipe-special-sources.json').read_text())
NUTRIENTS=('kcal_100g','protein_g_100g','fat_g_100g','carbs_available_g_100g')


def positive(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0


def trace_allowed(ing,canonical,recipe,grams):
    policy=POLICY['trace_condiment'];name=str(ing.get('name','')).strip().casefold()
    evidence=' '.join(str(v or '') for v in (name,ing.get('note'),(ing.get('source_nutrition_reference') or {}).get('description'))).casefold()
    if re.search(r'\b(and|or|fresh|sugar|paste|sauce|oil|fresco|fresca|zucchero)\b',evidence):return False
    eligible=(canonical or {}).get('id') in policy['canonical_ids'] or name in policy['exact_names']
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

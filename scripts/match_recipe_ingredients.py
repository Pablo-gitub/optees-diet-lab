"""Offline recipe ingredient matching against CREA and Open Food Facts.

Extracts ingredients across recipes, groups equivalent items, normalizes terms
via a versionable dictionary, preserves nutritional states (raw/cooked, fresh/canned,
whole/refined, etc.), proposes matches with rationale and confidence, produces an
ingredient-centric review queue, outputs comprehensive validation reports, and
exports only approved associations to the solver and nutrient calculator formats.
"""

import argparse
import collections
import csv
import json
import math
import re
import sqlite3
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREA = ROOT / 'dataset/crea/foods.csv'
DEFAULT_OFF = ROOT / 'dataset/open_food_facts/catalog.sqlite'
DEFAULT_RECIPES = ROOT / 'dataset/recipes/catalog.sqlite'
DEFAULT_DICT = ROOT / 'config/ingredient-dictionary.json'
DEFAULT_CONVERSIONS = ROOT / 'config/ingredient-unit-conversions.json'
DEFAULT_APPROVED = ROOT / 'config/ingredient-approved-mappings.json'

from recipe_special_sources import POLICY,trace_allowed,liquid_stock,special_food

NUTRIENTS = ['kcal_100g', 'protein_g_100g', 'fat_g_100g', 'carbs_available_g_100g']


def fold(text: str) -> str:
    """Normalize and fold text for case-insensitive, accent-free matching."""
    if not text:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(text).casefold()) if not unicodedata.combining(c)
    ).strip()


def singularize(word: str) -> str:
    """Strip common English plurals for canonical grouping."""
    w = word.strip()
    if len(w) <= 3:
        return w
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if w.endswith('oes') and len(w) > 4:
        return w[:-2]
    for irregular in ['leaves', 'halves', 'loaves', 'calves', 'wives']:
        if w.endswith(irregular):
            return w[:-3] + 'f'
    if w.endswith('s') and not w.endswith(('ss', 'us', 'is')):
        return w[:-1]
    return w


def extract_qualifiers(text: str, note: any, usda_desc: str, qualifiers_dict: dict) -> dict:
    """Extract nutritional state qualifiers (raw/cooked, fresh/canned, whole/refined, etc.)."""
    full_text = fold(f"{text or ''} {note or ''} {usda_desc or ''}")
    extracted = {}

    for dimension, values in qualifiers_dict.items():
        found = []
        for val_key, tokens in values.items():
            for tok in tokens:
                pattern = r'\b' + re.escape(fold(tok)) + r'\b'
                if re.search(pattern, full_text):
                    found.append((val_key, tok))
                    break
        if found:
            keys = set(f[0] for f in found)
            if 'canned' in keys and 'drained' in keys:
                extracted[dimension] = 'canned'
                extracted['drained'] = True
            elif len(keys) == 1:
                extracted[dimension] = list(keys)[0]
            else:
                extracted[dimension] = 'multiple'
            extracted[f'{dimension}_evidence'] = [f[1] for f in found]
        else:
            extracted[dimension] = 'unspecified'

    return extracted


def load_crea(crea_path: Path) -> dict:
    """Load CREA foods keyed by source_id."""
    foods = {}
    with crea_path.open(newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            foods[r['source_id']] = r
    return foods


def load_dictionary(dict_path: Path) -> dict:
    """Load the versionable canonical ingredient dictionary."""
    if not dict_path.exists():
        raise FileNotFoundError(f"Dictionary not found: {dict_path}")
    return json.loads(dict_path.read_text(encoding='utf-8'))


def load_approved_mappings(approved_path: Path, proposals_dir=None) -> dict:
    """Load explicit approved mappings."""
    data=json.loads(approved_path.read_text(encoding='utf-8')) if approved_path.exists() else {'version':'1.0','canonical_approvals':{},'recipe_overrides':{}}
    exclusions=collections.defaultdict(set)
    directory=Path(proposals_dir) if proposals_dir is not None else approved_path.parent/'ingredient-proposals'
    for path in sorted(directory.glob('batch-*.json')):
        for proposal in json.loads(path.read_text()).get('proposals',[]):
            for raw in proposal.get('raw_names_excluded',[]):
                name=raw.get('name') if isinstance(raw,dict) else raw
                if name:exclusions[proposal['canonical_id']].add(re.sub(r'\s+',' ',fold(name)))
    data['_raw_names_excluded']={k:sorted(v) for k,v in exclusions.items()}
    return data


def save_approved_mappings(data: dict, approved_path: Path):
    """Save approved mappings."""
    approved_path.parent.mkdir(parents=True, exist_ok=True)
    approved_path.write_text(json.dumps({k:v for k,v in data.items() if not k.startswith('_')}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def find_canonical_ingredient(ing: dict, dictionary: dict) -> dict:
    """Identify the canonical ingredient from name, USDA reference, or unitools ID."""
    canonical_dict = dictionary.get('canonical_ingredients', {})
    raw_name = fold(ing.get('name', ''))
    raw_words = [singularize(w) for w in raw_name.split()]
    normalized_name = ' '.join(raw_words)
    unitools_id = fold(str(ing.get('source_ingredient_id', '')))

    ref = ing.get('source_nutrition_reference') or {}
    usda_id = str(ref.get('id', '')).strip()

    # 1. Direct USDA ID match (highest priority for foodose)
    if usda_id:
        for cid, item in canonical_dict.items():
            if usda_id in item.get('usda_ids', []):
                return item

    # 2. Direct exact synonym match
    for cid, item in canonical_dict.items():
        syns = [fold(s) for s in item.get('synonyms_en', []) + item.get('synonyms_it', [])]
        if raw_name in syns or normalized_name in syns:
            return item

    # 3. Unitools source_ingredient_id + word match
    if unitools_id:
        for cid, item in canonical_dict.items():
            if unitools_id in [fold(x) for x in item.get('unitools_ids', [])]:
                # Verify that name is compatible
                syns = [fold(s) for s in item.get('synonyms_en', [])]
                if any(w in raw_name for s in syns for w in s.split()):
                    return item

    # 4. Normalized substring / token match
    for cid, item in canonical_dict.items():
        for s in item.get('synonyms_en', []):
            fs = fold(s)
            fs_words = [singularize(w) for w in fs.split()]
            fs_norm = ' '.join(fs_words)
            if fs_norm == normalized_name:
                return item
            if len(fs.split()) >= 2 and fs in raw_name:
                return item

    return None


def match_crea_candidates(canonical: dict, qualifiers: dict, crea_foods: dict) -> list:
    """Find CREA candidates respecting cooking/processing state distinctions."""
    candidates = []
    cm = canonical.get('crea_matches', {})
    primary = cm.get('primary')
    cooked_alt = cm.get('cooked_alternate')
    cooking_state = qualifiers.get('cooking_state', 'unspecified')

    # If ingredient is cooked, and cooked alternate exists
    if cooking_state == 'cooked' and cooked_alt:
        target_id = cooked_alt['id']
        food = crea_foods.get(target_id)
        if food:
            candidates.append(
                {
                    'source': 'CREA',
                    'id': target_id,
                    'name': food['name'],
                    'match_type': 'exact',
                    'confidence': 'high',
                    'state': 'cotto / bollito',
                    'reason': f"Corrispondenza esatta per stato cotto ({food['name']})",
                    'nutrients': {k: float(food[k]) for k in NUTRIENTS if food.get(k)},
                }
            )
    # If ingredient is raw or unspecified, evaluate primary
    elif primary:
        target_id = primary['id']
        food = crea_foods.get(target_id)
        if food:
            # Check if there is an ambiguity: food is raw by default, but cooking_state is ambiguous
            is_ambiguous = cooking_state == 'unspecified' and cooked_alt is not None
            candidates.append(
                {
                    'source': 'CREA',
                    'id': target_id,
                    'name': food['name'],
                    'match_type': primary.get('match_type', 'exact'),
                    'confidence': 'low'
                    if is_ambiguous
                    else ('high' if primary.get('match_type') == 'exact' else 'medium'),
                    'state': canonical.get('state', 'crudo / prima della cottura'),
                    'reason': primary.get('reason', 'Corrispondenza da catalogo CREA'),
                    'is_ambiguous': is_ambiguous,
                    'nutrients': {k: float(food[k]) for k in NUTRIENTS if food.get(k)},
                }
            )
            if is_ambiguous and cooked_alt:
                alt_food = crea_foods.get(cooked_alt['id'])
                if alt_food:
                    candidates.append(
                        {
                            'source': 'CREA',
                            'id': cooked_alt['id'],
                            'name': alt_food['name'],
                            'match_type': 'cooked_alternate',
                            'confidence': 'low',
                            'state': 'cotto / bollito',
                            'reason': f"Possibile alternativa cotta ({alt_food['name']}) - stato non specificato nella ricetta",
                            'is_ambiguous': True,
                            'nutrients': {k: float(alt_food[k]) for k in NUTRIENTS if alt_food.get(k)},
                        }
                    )

    if canonical.get('flags', {}).get('proxy_only'):
        for candidate in candidates:
            candidate.update(
                match_type='proxy',
                confidence='medium',
                reason='Taglio o composizione non equivalente: proxy da verificare per ricetta.',
            )

    # A liquid stock must never be proposed as undiluted concentrate.
    if canonical.get('flags',{}).get('requires_dilution'):candidates=[c for c in candidates if c['id']!='503010']

    # Add proxies if available
    for proxy in cm.get('proxies', []):
        p_id = proxy['id']
        if p_id=='503010' and canonical.get('flags',{}).get('requires_dilution'):continue
        food = crea_foods.get(p_id)
        if food and all(c['id'] != p_id for c in candidates):
            candidates.append(
                {
                    'source': 'CREA',
                    'id': p_id,
                    'name': food['name'],
                    'match_type': proxy.get('match_type', 'proxy'),
                    'confidence': 'medium',
                    'state': food['name'],
                    'reason': proxy.get('reason', 'Proxy nutrizionale / culinario documentato'),
                    'nutrients': {k: float(food[k]) for k in NUTRIENTS if food.get(k)},
                }
            )

    return candidates


def search_off_candidates(canonical: dict, qualifiers: dict, db_off: sqlite3.Connection) -> list:
    """Retrieve verified Open Food Facts brand candidates adhering to quality rules."""
    candidates = []

    # 1. Curated brand candidates in dictionary
    for brand_c in canonical.get('off_brand_candidates', []):
        barcode = brand_c['barcode']
        row = db_off.execute(
            "SELECT barcode, name, brands, numeric_candidate, payload FROM products WHERE barcode=?", (barcode,)
        ).fetchone()
        if row:
            p = json.loads(row[4])
            if p.get('numeric_candidate') == 1 and p.get('nutrient_basis') == 'per_100_g':
                candidates.append(
                    {
                        'source': 'Open Food Facts',
                        'id': barcode,
                        'name': f"{row[1]} · {row[2]}",
                        'brands': row[2],
                        'match_type': brand_c.get('match_type', 'brand_candidate'),
                        'confidence': 'high' if brand_c.get('match_type') == 'brand_candidate' else 'medium',
                        'reason': brand_c.get('reason', 'Candidato di marca verificato'),
                        'nutrients': {k: p.get(k) for k in NUTRIENTS},
                    }
                )

    return candidates


def evaluate_quantity(ing: dict, canonical: dict, dictionary: dict) -> tuple:
    """Evaluate quantity: returns (grams, quantity_status, note)."""
    raw_grams = ing.get('grams_whole_recipe')
    if raw_grams is not None:
        try:
            val = float(raw_grams)
            if math.isfinite(val) and val > 0:
                return val, 'resolved', 'Pesi espliciti dichiarati dalla ricetta'
        except (ValueError, TypeError):
            pass

    unit = str(ing.get('unit', '')).strip().lower()
    qty = ing.get('quantity')
    approved=dictionary.get('_approved_conversions',{}).get((canonical or {}).get('id'),{}).get(unit)
    if approved and (canonical or {}).get('id') in dictionary.get('_approved_conversion_canonicals',set()):
        try:
            value=float(qty)*approved['grams']
            if isinstance(qty,bool):raise ValueError()
            if math.isfinite(value) and value>0:
                return value,'resolved','Conversione approvata: '+approved['source']+'; autore '+approved['approved_by']
        except (TypeError,ValueError):pass
    conversions = dictionary.get('standard_conversions', {})

    # Kilograms
    if unit == 'kg' and qty is not None:
        try:
            val = float(qty) * 1000.0
            if math.isfinite(val) and val > 0:
                return val, 'resolved', 'Conversione esplicita kg -> g (* 1000)'
        except (ValueError, TypeError):
            pass

    if unit in ('l','liter','litre') and liquid_stock(ing,canonical) and qty is not None:
        try:
            amount=float(qty)*1000
            if math.isfinite(amount) and amount>0:return amount,'resolved','Brodo liquido: litri -> ml, densità dichiarata 1 g/ml'
        except (ValueError,TypeError):pass

    # Milliliters for water or known liquid densities
    if unit == 'ml' and qty is not None:
        try:
            q_num = float(qty)
            density = canonical.get('density_g_per_ml') if canonical else None
            if canonical and canonical.get('flags',{}).get('requires_dilution') and liquid_stock(ing,canonical):
                if math.isfinite(q_num) and q_num>0:return q_num*POLICY['stock']['density_g_per_ml'],'resolved','Brodo liquido: densità 1 g/ml dichiarata nella policy (euristica)'
            if canonical and canonical.get('special_source') == 'water':
                return q_num * 1.0, 'resolved', 'Conversione ml -> g per acqua (densità 1.0 g/ml)'
            elif density and density > 0:
                return (
                    q_num * density,
                    'proposed_conversion',
                    f'Conversione ml -> g con densità documentata {density} g/ml (richiede conferma)',
                )
            else:
                return None, 'needs_review', 'Quantità in ml senza densità accertata'
        except (ValueError, TypeError):
            pass

    # Piece / Clove / Tablespoon units: documented reference weights requiring explicit review
    if unit in ['clove', 'piece', 'count', 'tbsp', 'tsp']:
        # Documented conversion lookup
        std_key = None
        if unit == 'clove':
            std_key = 'clove_garlic'
        elif unit in ['piece', 'count']:
            if canonical and canonical.get('id') == 'uovo_gallina_intero':
                std_key = 'piece_egg'
            elif canonical and canonical.get('id') == 'uovo_tuorlo':
                std_key = 'piece_egg_yolk'
            elif canonical and canonical.get('id') == 'uovo_albume':
                std_key = 'piece_egg_white'
            elif canonical and canonical.get('id') == 'cipolla_cruda':
                std_key = 'piece_onion'
        elif unit == 'tbsp' and canonical and canonical.get('id') == 'olio_oliva_extravergine':
            std_key = 'tbsp_olive_oil'

        if std_key and std_key in conversions:
            conv = conversions[std_key]
            try:
                q_val = float(qty) if qty is not None else 1.0
                est_grams = q_val * conv['grams']
                return est_grams, 'proposed_conversion', f"Stima documentata ({conv['provenance']}), richiede revisione"
            except (ValueError, TypeError):
                pass
        return None, 'needs_review', f'Unità non ponderale ({unit}) priva di peso verificato'

    if unit in ['totaste', 'pinch', 'slice', 'sprig', 'zest']:
        return None, 'needs_review', f'Quantità qualitativa o a piacere ({unit}): richiede revisione'

    return None, 'needs_review', f'Quantità non convertibile (qty={qty}, unit={unit})'


def approval_compatible(ing, canonical, qualifiers, approval, crea_foods, specific=False, recipe=None):
    """A shared approval cannot override evidence from the actual occurrence."""
    if (canonical or {}).get('flags',{}).get('requires_dilution') and approval.get('source')=='CREA' and approval.get('id')=='503010':return False
    if approval.get('reviewed') is not True or approval.get('state_checked') is not True:
        return False
    if approval.get('source')=='condiment':return approval.get('id')=='trace' and trace_allowed(ing,canonical,recipe or {},approval.get('grams_override',ing.get('grams_whole_recipe')))
    if approval.get('source')=='stock':return approval.get('id')=='cube_1_50' and liquid_stock(ing,canonical)
    if (canonical or {}).get('flags',{}).get('requires_dilution') and approval.get('source')=='water':return False
    text = fold(
        ' '.join(
            str(x or '')
            for x in [
                ing.get('name'),
                ing.get('note'),
                (ing.get('source_nutrition_reference') or {}).get('description'),
            ]
        )
    )
    if re.search(r'\b(frying|fry|fried|deep frying|discarded|powder|powdered|dehydrated)\b', text):
        return False
    if re.search(r'\b(and|or)\b', fold(ing.get('name', ''))):
        return False
    if any(v == 'multiple' for v in qualifiers.values()):
        return False
    if approval['source'] == 'CREA':
        food = crea_foods.get(approval['id'])
        if not food or any(not food.get(n) for n in NUTRIENTS):
            return False
        food_name = fold(food['name'])
        cooked = qualifiers.get('cooking_state') == 'cooked'
        if cooked and not re.search(r'\b(cotto|cotte|cotti|cotta|bollito|bollite)\b', food_name):
            return False
        if qualifiers.get('cooking_state') == 'raw' and re.search(
            r'\b(cotto|cotte|cotti|cotta|bollito|bollite)\b', food_name
        ):
            return False
        if qualifiers.get('processing_state') == 'dry' and re.search(r'\b(fresco|freschi|fresche|fresca)\b', food_name):
            return False
        if (
            qualifiers.get('grain_type') == 'whole'
            and food.get('category') == 'Cereali e derivati'
            and 'integrale' not in food_name
        ):
            return False
        if (
            not specific
            and qualifiers.get('processing_state') == 'canned'
            and not any(x in food_name for x in ['scatola', 'conserv', 'salamoia'])
        ):
            return False
    return True


def _process_ingredient(
    ing: dict, recipe: dict, dictionary: dict, approved_data: dict, crea_foods: dict, db_off: sqlite3.Connection
) -> dict:
    """Process a single ingredient occurrence."""
    rec_id = recipe['id']
    ing_key = str(ing['key'])
    name = ing.get('name', '')
    note = ing.get('note', '')
    ref = ing.get('source_nutrition_reference') or {}
    usda_desc = ref.get('description', '')

    qualifiers = extract_qualifiers(name, note, usda_desc, dictionary.get('qualifiers', {}))
    canonical = find_canonical_ingredient(ing, dictionary)

    safe_dictionary=dict(dictionary)
    approval=approved_data.get('canonical_approvals',{}).get((canonical or {}).get('id'))
    excluded_name=canonical and re.sub(r'\s+',' ',fold(name)) in approved_data.get('_raw_names_excluded',{}).get(canonical['id'],[])
    if not approval or excluded_name or not approval_compatible(ing,canonical,qualifiers,approval,crea_foods,recipe=recipe):safe_dictionary['_approved_conversion_canonicals']=set()
    grams, qty_status, qty_note = evaluate_quantity(ing, canonical, safe_dictionary)

    # 1. Check Recipe Override in approved mappings
    rec_overrides = approved_data.get('recipe_overrides', {}).get(rec_id, {})
    if ing_key in rec_overrides and approval_compatible(
        ing, canonical, qualifiers, rec_overrides[ing_key], crea_foods, specific=True, recipe=recipe
    ):
        appr = rec_overrides[ing_key]
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': canonical['id'] if canonical else 'custom_override',
            'canonical_name': canonical['display_name_it'] if canonical else appr.get('label', name),
            'qualifiers': qualifiers,
            'match_status': 'approved',
            'confidence': 'verified',
            'reviewed': True,
            'state_checked': True,
            'selected_candidate': {
                'source': appr['source'],
                'id': appr['id'],
                'label': appr.get('label', ''),
                'reviewed': True,
                'state_checked': True,
                'reason': 'Revisione specifica approvata per la ricetta',
            },
            'candidates': [appr],
            'grams': appr.get('grams_override', grams),
            'quantity_status': 'resolved'
            if isinstance(appr.get('grams_override'), (int, float))
            and not isinstance(appr.get('grams_override'), bool)
            and math.isfinite(appr['grams_override'])
            and appr['grams_override'] > 0
            else qty_status,
            'quantity_note': qty_note,
            'note': 'Approvato da override specifico di ricetta',
        }

    excluded=bool(canonical and re.sub(r'\s+',' ',fold(name)) in approved_data.get('_raw_names_excluded',{}).get(canonical['id'],[]))
    if excluded:
        return dict(ingredient_key=ing_key,original_name=name,canonical_id=canonical['id'],canonical_name=canonical['display_name_it'],qualifiers=qualifiers,match_status='needs_review',confidence='none',reviewed=False,state_checked=False,selected_candidate=None,candidates=[],grams=grams,quantity_status=qty_status,quantity_note=qty_note,note='Nome escluso esplicitamente dai batch: non eredita approvazione canonica.',approval_excluded=True)
    if trace_allowed(ing,canonical,recipe,grams):
        candidate=dict(source='condiment',id='trace',label=name,category='condimento',state='in traccia, 0 kcal dichiarate',reviewed=True,state_checked=True,declared_kcal=0,reason=POLICY['trace_condiment']['note'])
        return dict(ingredient_key=ing_key,original_name=name,canonical_id=(canonical or {}).get('id','trace:'+fold(name)),canonical_name=(canonical or {}).get('display_name_it',name),qualifiers=qualifiers,match_status='approved',confidence='declared',reviewed=True,state_checked=True,selected_candidate=candidate,candidates=[candidate],grams=grams,quantity_status='resolved' if grams is not None else 'trace',quantity_note=qty_note,note=candidate['reason'],category='condimento',declared_kcal=0)
    if liquid_stock(ing,canonical):
        candidate=dict(source='stock',id='cube_1_50',label='Brodo liquido da dado diluito 1:50',category='brodo',state='liquido, diluizione dichiarata 1:50',reviewed=True,state_checked=True,reason=POLICY['stock']['note'],dilution=POLICY['stock'])
        # A dedicated explicitly reviewed liquid source takes precedence.
        specific=rec_overrides.get(ing_key)
        generic=approved_data.get('canonical_approvals',{}).get(canonical['id'])
        if not generic or not approval_compatible(ing,canonical,qualifiers,generic,crea_foods,recipe=recipe):
            return dict(ingredient_key=ing_key,original_name=name,canonical_id=canonical['id'],canonical_name=canonical['display_name_it'],qualifiers=qualifiers,match_status='approved',confidence='declared_proxy',reviewed=True,state_checked=True,selected_candidate=candidate,candidates=[candidate],grams=grams,quantity_status=qty_status,quantity_note=qty_note,note=candidate['reason'],category='brodo')

    # 2. Check Canonical Approval
    if canonical:
        cid = canonical['id']
        can_approvals = approved_data.get('canonical_approvals', {})
        if cid in can_approvals and approval_compatible(ing, canonical, qualifiers, can_approvals[cid], crea_foods, recipe=recipe):
            appr = can_approvals[cid]
            return {
                'ingredient_key': ing_key,
                'original_name': name,
                'canonical_id': cid,
                'canonical_name': canonical['display_name_it'],
                'qualifiers': qualifiers,
                'match_status': 'approved',
                'confidence': 'verified',
                'reviewed': True,
                'state_checked': True,
                'selected_candidate': {
                    'source': appr['source'],
                    'id': appr['id'],
                    'label': appr.get('label', ''),
                    'reviewed': True,
                    'state_checked': True,
                    'reason': appr.get('note', 'Regola canonica approvata riutilizzata'),
                },
                'candidates': [appr],
                'grams': grams,
                'quantity_status': qty_status,
                'quantity_note': qty_note,
                'note': f"Approvato tramite regola canonica riutilizzabile: {cid}",
            }

    # 3. Special Source: Water
    if canonical and canonical.get('special_source') == 'water':
        cand = {
            'source': 'water',
            'id': 'water',
            'name': 'Acqua pura',
            'match_type': 'exact',
            'confidence': 'high',
            'reason': 'Fonte speciale acqua potabile documentata',
            'reviewed': False,
            'state_checked': False,
        }
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': canonical['id'],
            'canonical_name': canonical['display_name_it'],
            'qualifiers': qualifiers,
            'match_status': 'proposed_exact',
            'confidence': 'high',
            'reviewed': False,
            'state_checked': False,
            'selected_candidate': cand,
            'candidates': [cand],
            'grams': grams,
            'quantity_status': qty_status,
            'quantity_note': qty_note,
            'note': 'Proposta esatta per acqua (fonte water)',
        }

    # 4. Handle Composite / Unabsorbed Oil Flags
    if canonical and canonical.get('flags', {}).get('composite'):
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': canonical['id'],
            'canonical_name': canonical['display_name_it'],
            'qualifiers': qualifiers,
            'match_status': 'ambiguous',
            'confidence': 'low',
            'reviewed': False,
            'state_checked': False,
            'selected_candidate': None,
            'candidates': [],
            'grams': grams,
            'quantity_status': qty_status,
            'quantity_note': qty_note,
            'note': 'Ingrediente composito (es. sale e pepe): richiede separazione o revisione',
        }

    if canonical and canonical.get('flags', {}).get('unabsorbed_oil'):
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': canonical['id'],
            'canonical_name': canonical['display_name_it'],
            'qualifiers': qualifiers,
            'match_status': 'needs_review',
            'confidence': 'low',
            'reviewed': False,
            'state_checked': False,
            'selected_candidate': None,
            'candidates': [],
            'grams': grams,
            'quantity_status': qty_status,
            'quantity_note': qty_note,
            'note': 'Olio per friggere: assorbimento effettivo non inferibile, richiede revisione manuale',
        }

    if canonical and canonical.get('flags', {}).get('requires_dilution'):
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': canonical['id'],
            'canonical_name': canonical['display_name_it'],
            'qualifiers': qualifiers,
            'match_status': 'needs_review',
            'confidence': 'low',
            'reviewed': False,
            'state_checked': False,
            'selected_candidate': None,
            'candidates': match_crea_candidates(canonical, qualifiers, crea_foods) if canonical else [],
            'grams': grams,
            'quantity_status': qty_status,
            'quantity_note': qty_note,
            'note': 'Brodo liquido pronto: non equiparabile a dado concentrato senza diluizione, richiede revisione manuale',
        }

    # 5. Search CREA candidates
    crea_cands = match_crea_candidates(canonical, qualifiers, crea_foods) if canonical else []

    # 6. Search OFF candidates
    off_cands = search_off_candidates(canonical, qualifiers, db_off) if (canonical and db_off) else []

    all_cands = crea_cands + off_cands

    # Classify match status and confidence
    if not canonical:
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': None,
            'canonical_name': name,
            'qualifiers': qualifiers,
            'match_status': 'missing',
            'confidence': 'none',
            'reviewed': False,
            'state_checked': False,
            'selected_candidate': None,
            'candidates': [],
            'grams': grams,
            'quantity_status': qty_status,
            'quantity_note': qty_note,
            'note': 'Ingrediente non censito nel dizionario canonico',
        }

    if any(c.get('is_ambiguous') for c in all_cands):
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': canonical['id'],
            'canonical_name': canonical['display_name_it'],
            'qualifiers': qualifiers,
            'match_status': 'ambiguous',
            'confidence': 'low',
            'reviewed': False,
            'state_checked': False,
            'selected_candidate': all_cands[0] if all_cands else None,
            'candidates': all_cands,
            'grams': grams,
            'quantity_status': qty_status,
            'quantity_note': qty_note,
            'note': 'Ambiguità di stato rilevata (es. crudo vs cotto / alternative multiple)',
        }

    if any(c['match_type'] == 'exact' for c in all_cands):
        exact_cand = next(c for c in all_cands if c['match_type'] == 'exact')
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': canonical['id'],
            'canonical_name': canonical['display_name_it'],
            'qualifiers': qualifiers,
            'match_status': 'proposed_exact',
            'confidence': 'high',
            'reviewed': False,
            'state_checked': False,
            'selected_candidate': exact_cand,
            'candidates': all_cands,
            'grams': grams,
            'quantity_status': qty_status,
            'quantity_note': qty_note,
            'note': exact_cand['reason'],
        }

    if any(c['match_type'] in ['proxy', 'brand_candidate'] for c in all_cands):
        proxy_cand = all_cands[0]
        return {
            'ingredient_key': ing_key,
            'original_name': name,
            'canonical_id': canonical['id'],
            'canonical_name': canonical['display_name_it'],
            'qualifiers': qualifiers,
            'match_status': 'proposed_proxy',
            'confidence': 'medium',
            'reviewed': False,
            'state_checked': False,
            'selected_candidate': proxy_cand,
            'candidates': all_cands,
            'grams': grams,
            'quantity_status': qty_status,
            'quantity_note': qty_note,
            'note': proxy_cand['reason'],
        }

    return {
        'ingredient_key': ing_key,
        'original_name': name,
        'canonical_id': canonical['id'],
        'canonical_name': canonical['display_name_it'],
        'qualifiers': qualifiers,
        'match_status': 'missing',
        'confidence': 'none',
        'reviewed': False,
        'state_checked': False,
        'selected_candidate': None,
        'candidates': [],
        'grams': grams,
        'quantity_status': qty_status,
        'quantity_note': qty_note,
        'note': 'Nessun alimento CREA o OFF compatibile individuato',
    }


def process_ingredient(ing,recipe,dictionary,approved_data,crea_foods,db_off):
    result=_process_ingredient(ing,recipe,dictionary,approved_data,crea_foods,db_off)
    candidate=result.get('selected_candidate')
    if candidate and candidate['source'] in ('condiment','stock'):
        policy=POLICY['trace_condiment' if candidate['source']=='condiment' else 'stock']
        metadata=dict(category=policy['category'],reason=policy['note'])
        if candidate['source']=='condiment':
            metadata['declared_kcal']=0
            if result['grams'] is None:result['quantity_status']='trace'
        else:metadata['dilution']=policy
        candidate.update(metadata)
        result['candidates']=[dict(c,**metadata) if (c['source'],c['id'])==(candidate['source'],candidate['id']) else c for c in result['candidates']]
        result.update(category=policy['category'],source_quantity=ing.get('quantity'),source_unit=ing.get('unit'))
    return result


def process_recipes(
    recipes_db_path: Path,
    crea_path: Path,
    off_db_path: Path,
    dict_path: Path,
    approved_path: Path,
    limit: int = None,
    cuisine_filter: str = None,
    conversions_path: Path = DEFAULT_CONVERSIONS,
) -> list:
    """Stream and process recipes from SQLite database."""
    crea_foods = load_crea(crea_path)
    dictionary = load_dictionary(dict_path)
    approved_data = load_approved_mappings(approved_path)
    dictionary['_approved_conversions']=load_conversions(conversions_path)
    dictionary['_approved_conversion_canonicals']=set(approved_data.get('canonical_approvals',{}))
    db_off = sqlite3.connect(off_db_path) if off_db_path.exists() else None

    processed = []
    with sqlite3.connect(recipes_db_path) as db:
        query = "SELECT id, source, title, cuisine, payload FROM recipes"
        args = []
        if cuisine_filter:
            query += " WHERE cuisine_id = ?"
            args.append(fold(cuisine_filter).replace(' ', '-'))
        query += " ORDER BY title, id"
        if limit:
            query += f" LIMIT {int(limit)}"

        for row in db.execute(query, args):
            recipe = json.loads(row[4])
            ingredients_results = []
            for ing in recipe.get('ingredients', []):
                res = process_ingredient(ing, recipe, dictionary, approved_data, crea_foods, db_off)
                ingredients_results.append(res)

            all_approved = bool(ingredients_results) and all(
                i['match_status'] == 'approved' for i in ingredients_results
            )
            all_proposed = bool(ingredients_results) and all(
                i['match_status'] in ['approved', 'proposed_exact', 'proposed_proxy'] for i in ingredients_results
            )
            all_quantities_resolved = bool(ingredients_results) and all(
                (i['quantity_status'] == 'resolved' and i['grams'] is not None) or (i['quantity_status']=='trace' and i['selected_candidate']['source']=='condiment') for i in ingredients_results
            )
            solver_ready = all_approved and all_quantities_resolved

            processed.append(
                {
                    'id': recipe['id'],
                    'source': recipe['source'],
                    'title': recipe['title'],
                    'cuisine': recipe.get('cuisine'),
                    'servings': recipe.get('servings'),
                    'source_url': recipe.get('source_url'),
                    'license': recipe.get('license'),
                    'attribution': recipe.get('attribution'),
                    'ingredients': ingredients_results,
                    'all_approved': all_approved,
                    'all_proposed': all_proposed,
                    'all_quantities_resolved': all_quantities_resolved,
                    'solver_ready': solver_ready,
                }
            )

    if db_off:
        db_off.close()
    return processed


def build_review_queue(processed_recipes: list, priority_recipe_ids=()) -> list:
    """Organize pending and completed ingredient reviews grouped by canonical ingredient."""
    groups = collections.defaultdict(
        lambda: {
            'canonical_id': None,
            'canonical_name': None,
            'occurrences': 0,
            'recipes': [],
            'candidates': [],
            'statuses': set(),
            'ambiguities': [],
            'raw_names': set(),
        }
    )

    for rec in processed_recipes:
        for ing in rec['ingredients']:
            cid = ing['canonical_id'] or f"unmapped:{fold(ing['original_name'])}"
            g = groups[cid]
            g['canonical_id'] = cid
            g['canonical_name'] = ing['canonical_name']
            g['occurrences'] += 1
            g['statuses'].add(ing['match_status'])
            g['raw_names'].add(ing['original_name'])
            g['recipes'].append(
                {
                    'recipe_id': rec['id'],
                    'recipe_title': rec['title'],
                    'ingredient_key': ing['ingredient_key'],
                    'original_name': ing['original_name'],
                    'grams': ing['grams'],
                    'quantity_status': ing['quantity_status'],
                }
            )
            if ing['candidates']:
                for c in ing['candidates']:
                    c_key = f"{c['source']}:{c['id']}"
                    if not any(f"{x['source']}:{x['id']}" == c_key for x in g['candidates']):
                        g['candidates'].append(c)
            if ing['match_status'] == 'ambiguous':
                g['ambiguities'].append(
                    {'recipe_id': rec['id'], 'original_name': ing['original_name'], 'note': ing['note']}
                )

    queue = []
    for cid, g in groups.items():
        primary_status = (
            'approved'
            if 'approved' in g['statuses'] and len(g['statuses']) == 1
            else (
                'ambiguous'
                if 'ambiguous' in g['statuses']
                else (
                    'missing'
                    if 'missing' in g['statuses']
                    else ('proposed_exact' if 'proposed_exact' in g['statuses'] else 'proposed_proxy')
                )
            )
        )
        queue.append(
            {
                'canonical_id': cid,
                'canonical_name': g['canonical_name'],
                'occurrences': g['occurrences'],
                'recipes_count': len(g['recipes']),
                'primary_status': primary_status,
                'raw_names': sorted(list(g['raw_names'])),
                'candidates': g['candidates'],
                'sample_recipes': g['recipes'][:5],
                'ambiguity_count': len(g['ambiguities']),
            }
        )

    priority_recipe_ids=set(priority_recipe_ids)
    for item in queue:
        item['preferred_recipe_priority']=item['primary_status']!='approved' and any(r['recipe_id'] in priority_recipe_ids for r in groups[item['canonical_id']]['recipes'])
    queue.sort(key=lambda x: (not x['preferred_recipe_priority'],-x['occurrences'], x['canonical_name']))
    return queue


def build_report(processed_recipes: list, review_queue: list) -> dict:
    """Generate statistical summary of matching and quantity status."""
    total_recipes = len(processed_recipes)
    total_ingredients = sum(len(r['ingredients']) for r in processed_recipes)

    status_counts = collections.Counter()
    qty_counts = collections.Counter()
    for r in processed_recipes:
        for i in r['ingredients']:
            status_counts[i['match_status']] += 1
            qty_counts[i['quantity_status']] += 1

    canonical_status_counts = collections.Counter(item['primary_status'] for item in review_queue)

    recipes_all_approved = sum(r['all_approved'] for r in processed_recipes)
    recipes_all_proposed = sum(r['all_proposed'] for r in processed_recipes)
    recipes_all_quantities_resolved = sum(r['all_quantities_resolved'] for r in processed_recipes)
    recipes_solver_ready = sum(r['solver_ready'] for r in processed_recipes)

    return {
        'total_recipes': total_recipes,
        'total_ingredient_occurrences': total_ingredients,
        'total_canonical_groups': len(review_queue),
        'ingredient_statuses': dict(status_counts),
        'ingredient_quantities': dict(qty_counts),
        'canonical_group_statuses': dict(canonical_status_counts),
        'recipes_all_associations_approved': recipes_all_approved,
        'recipes_all_associations_proposed': recipes_all_proposed,
        'recipes_all_quantities_resolved': recipes_all_quantities_resolved,
        'recipes_solver_ready': recipes_solver_ready,
        'recipes_pending_review': total_recipes - recipes_solver_ready,
        'recipes_with_trace_condiments':sum(any(i['selected_candidate'] and i['selected_candidate']['source']=='condiment' for i in r['ingredients']) for r in processed_recipes),
        'recipes_with_declared_stock_dilution':sum(any(i['selected_candidate'] and i['selected_candidate']['source']=='stock' for i in r['ingredients']) for r in processed_recipes),
        'excluded_occurrences':sum(i.get('approval_excluded',False) for r in processed_recipes for i in r['ingredients']),
        'special_sources_policy':POLICY,
    }


def print_report(report: dict):
    """Print readable summary report to stdout."""
    print("=" * 70)
    print(" RAPPORTO ASSOCIAZIONE INGREDIENTI RICETTE E CATALOGHI")
    print("=" * 70)
    print(f"Ricette totali esaminate:               {report['total_recipes']}")
    print(f"Istanze ingredienti totali:             {report['total_ingredient_occurrences']}")
    print(f"Gruppi canonici / equivalenze:          {report['total_canonical_groups']}")
    print("-" * 70)
    print("Stato associazioni per istanza ingrediente:")
    for status, cnt in report['ingredient_statuses'].items():
        pct = (cnt / report['total_ingredient_occurrences'] * 100) if report['total_ingredient_occurrences'] else 0
        print(f"  • {status:25s}: {cnt:5d} ({pct:5.1f}%)")
    print("-" * 70)
    print("Stato quantitativo ingredienti:")
    for status, cnt in report['ingredient_quantities'].items():
        pct = (cnt / report['total_ingredient_occurrences'] * 100) if report['total_ingredient_occurrences'] else 0
        print(f"  • {status:25s}: {cnt:5d} ({pct:5.1f}%)")
    print("-" * 70)
    print("Gruppi canonici (riutilizzo revisione):")
    for status, cnt in report['canonical_group_statuses'].items():
        print(f"  • {status:25s}: {cnt:5d} gruppi")
    print("-" * 70)
    print("Riepilogo Ricette:")
    print(f"  • Ricette con tutte le associazioni approvate: {report['recipes_all_associations_approved']}")
    print(f"  • Ricette con tutte le associazioni proposte:  {report['recipes_all_associations_proposed']}")
    print(f"  • Ricette con tutti i pesi espliciti risolti:  {report['recipes_all_quantities_resolved']}")
    print(f"  • Ricette PRONTE per il solver (100% OK):     {report['recipes_solver_ready']}")
    print(f"  • Ricette in attesa di revisione / pesi:       {report['recipes_pending_review']}")
    print("=" * 70)


def export_solver_recipes(processed_recipes: list, output_path: Path):
    """Export only recipes with 100% approved associations and resolved weights to solver format."""
    ready_recipes = [r for r in processed_recipes if r['solver_ready']]
    exported_data = {'recipes': []}

    for r in ready_recipes:
        servings = float(r.get('servings', 1) or 1)
        recipe_entry = {
            'id': r['id'],
            'title': r['title'],
            'cuisine_id': fold(r.get('cuisine', '')).replace(' ', '-'),
            'source': r['source'],
            'source_url': r.get('source_url'),
            'license': r.get('license'),
            'attribution': r.get('attribution'),
            'reference_note': f"Ricetta approvata offline con tutte le associazioni controllate e pesi verificati. Servings: {servings}.",
            'ingredients': [],
            'trace_condiments': [],
        }
        for ing in r['ingredients']:
            cand = ing['selected_candidate']
            if ing.get('quantity_status')=='trace':
                recipe_entry['trace_condiments'].append(dict(key=ing['ingredient_key'],name=ing['original_name'],source='condiment',id='trace',category='condimento',declared_kcal=0,grams=None,source_quantity=ing.get('source_quantity'),source_unit=ing.get('source_unit'),reviewed=True,state_checked=True,note=ing['note']));continue
            grams = float(ing['grams'])
            recipe_entry['ingredients'].append(
                {
                    'key': ing['ingredient_key'],
                    'name': ing['original_name'],
                    'grams_per_reference_portion': round(grams / servings, 2),
                    'state': cand.get('state', ing.get('qualifiers', {}).get('cooking_state', 'unspecified')),
                    'candidates': [
                        {
                            'source': cand['source'],
                            'id': cand['id'],
                            'reviewed': True,
                            'state_checked': True,
                            'label': cand.get('label') or cand.get('name', ''),
                            **{k:cand[k] for k in ('category','declared_kcal','reason','dilution') if k in cand},
                        }
                    ],
                }
            )
        exported_data['recipes'].append(recipe_entry)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(exported_data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Esportate {len(exported_data['recipes'])} ricette pronte per il solver in: {output_path}")


def export_recipe_mappings(processed_recipes: list, output_dir: Path):
    """Export per-recipe mapping JSON files for calculate_recipe_nutrients.py."""
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for r in processed_recipes:
        mapping = {}
        for ing in r['ingredients']:
            cand = ing.get('selected_candidate')
            if cand:
                mapping[ing['ingredient_key']] = {
                    'source': cand['source'],
                    'id': cand['id'],
                    'reviewed': ing['reviewed'] and ing.get('quantity_status') in ('resolved','trace'),
                    'state_checked': ing['state_checked'],
                    'grams_override': ing.get('grams'),
                    'quantity_status': ing.get('quantity_status'),
                    **{k:cand[k] for k in ('category','declared_kcal','reason','dilution') if k in cand},
                }
        safe_id = r['id'].replace(':', '_').replace('/', '_')
        target_file = output_dir / f"{safe_id}.json"
        target_file.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        count += 1
    print(f"Esportati {count} file mapping ricette in: {output_dir}")


def approve_canonical(
    canonical_id: str,
    source: str,
    food_id: str,
    label: str,
    approved_path: Path,
    note: str = None,
    approved_by: str = None,
):
    """Record an approved mapping for a canonical ingredient, propagating across all recipes."""
    approved_data = load_approved_mappings(approved_path)
    canonical_approvals = approved_data.setdefault('canonical_approvals', {})

    canonical_approvals[canonical_id] = {
        'source': source,
        'id': food_id,
        'label': label or food_id,
        'state': 'verificato',
        'reviewed': True,
        'state_checked': True,
        'approved_by': approved_by or 'baseline_rule',
        'note': note or f"Approvazione per {canonical_id} -> {source}:{food_id}",
    }
    save_approved_mappings(approved_data, approved_path)
    print(
        f"Approvazione salvata per '{canonical_id}': {source}:{food_id} ({label}) [by: {approved_by or 'baseline_rule'}]"
    )


def load_conversions(path):
    data=json.loads(Path(path).read_text()) if Path(path).exists() else {'conversions':{}}
    for canonical,units in data['conversions'].items():
        for unit,row in units.items():
            if not isinstance(row.get('grams'),(int,float)) or isinstance(row['grams'],bool) or not math.isfinite(row['grams']) or not 0<row['grams']<=10000 or not row.get('source') or not row.get('approved_by'):raise ValueError('Conversione approvata incompleta: '+canonical+' '+unit)
    return data['conversions']


def approve_conversion(canonical,unit,grams,source,author,path=DEFAULT_CONVERSIONS,approved_path=DEFAULT_APPROVED):
    if canonical not in load_approved_mappings(approved_path).get('canonical_approvals',{}):raise ValueError('Prima approvare l’associazione del canonico')
    if unit not in ('ml','l','liter','litre','piece','count','clove','tbsp','tsp','slice','sprig','cup'):raise ValueError('Unità di conversione non supportata')
    grams=float(grams)
    if not math.isfinite(grams) or not 0<grams<=10000 or not isinstance(source,str) or not source.strip() or not isinstance(author,str) or not author.strip():raise ValueError('Servono grammi positivi, fonte e autore espliciti')
    data=load_conversions(path);data.setdefault(canonical,{})[unit]=dict(grams=grams,source=source.strip(),approved_by=author.strip(),approved_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.json.tmp');temporary.write_text(json.dumps(dict(version='ingredient-unit-conversions-v1',conversions=data),ensure_ascii=False,indent=2)+'\n');temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipes-db', type=Path, default=DEFAULT_RECIPES)
    parser.add_argument('--crea-file', type=Path, default=DEFAULT_CREA)
    parser.add_argument('--off-db', type=Path, default=DEFAULT_OFF)
    parser.add_argument('--dict-file', type=Path, default=DEFAULT_DICT)
    parser.add_argument('--approved-file', type=Path, default=DEFAULT_APPROVED)

    parser.add_argument('--sample', type=int, help='Analizza un campione di N ricette')
    parser.add_argument('--cuisine', type=str, help='Filtra per cucina (es. Italian)')
    parser.add_argument('--report', action='store_true', default=True, help='Stampa rapporto statistico')
    parser.add_argument('--report-file', type=Path, help='Salva rapporto in formato JSON')
    parser.add_argument('--review-queue', type=Path, help='Salva coda di revisione organizzata per ingrediente')
    parser.add_argument(
        '--export-solver', type=Path, help='Esporta ricette con associazioni approvate nel formato per solver'
    )
    parser.add_argument(
        '--export-mappings', type=Path, help='Esporta file mapping ricette per calculate_recipe_nutrients.py'
    )

    parser.add_argument(
        '--approve',
        nargs=3,
        metavar=('CANONICAL_ID', 'SOURCE', 'FOOD_ID'),
        help='Registra una revisione approvata per un ingrediente canonico',
    )
    parser.add_argument('--approve-label', type=str, default='', help='Etichetta per l\'alimento approvato')
    parser.add_argument('--approve-by', type=str, default='baseline_rule', help='Autore o fonte dell\'approvazione')
    parser.add_argument('--approve-note', type=str, default=None, help='Nota o motivazione dell\'approvazione')

    parser.add_argument('--approve-conversion',nargs=3,metavar=('CANONICO','UNITA','GRAMMI'))
    parser.add_argument('--conversions-file',type=Path,default=DEFAULT_CONVERSIONS)
    parser.add_argument('--conversion-source',type=str)
    parser.add_argument('--conversion-by',type=str)
    parser.add_argument('--recipe-preferences-file',type=Path,help='JSON esportato da GET /api/recipes/preferences: ingredienti delle preferite sospese prima')
    args = parser.parse_args()
    if args.approve_conversion:
        try:approve_conversion(*args.approve_conversion,args.conversion_source,args.conversion_by,args.conversions_file,args.approved_file)
        except (ValueError,TypeError) as exc:parser.error(str(exc))
        return

    # Handle approval command
    if args.approve:
        cid, src, fid = args.approve
        approve_canonical(
            cid, src, fid, args.approve_label, args.approved_file, note=args.approve_note, approved_by=args.approve_by
        )
        return

    # Process recipes
    processed = process_recipes(
        recipes_db_path=args.recipes_db,
        crea_path=args.crea_file,
        off_db_path=args.off_db,
        dict_path=args.dict_file,
        approved_path=args.approved_file,
        limit=args.sample,
        cuisine_filter=args.cuisine,
        conversions_path=args.conversions_file,
    )

    priority=[]
    if args.recipe_preferences_file:
        data=json.loads(args.recipe_preferences_file.read_text())
        if not isinstance(data,dict) or not isinstance(data.get('review_queue'),list):parser.error('File preferenze: serve review_queue[]')
        priority=[r.get('recipe_id') for r in data['review_queue'] if isinstance(r,dict)]
        if any(not isinstance(i,str) for i in priority):parser.error('recipe_id non valido nella coda preferite')
    review_queue = build_review_queue(processed,priority)
    report = build_report(processed, review_queue)

    if args.report:
        print_report(report)

    if args.report_file:
        args.report_file.parent.mkdir(parents=True, exist_ok=True)
        args.report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f"Rapporto salvato in: {args.report_file}")

    if args.review_queue:
        args.review_queue.parent.mkdir(parents=True, exist_ok=True)
        args.review_queue.write_text(json.dumps(review_queue, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f"Coda di revisione salvata in: {args.review_queue} ({len(review_queue)} gruppi canonici)")

    if args.export_solver:
        export_solver_recipes(processed, args.export_solver)

    if args.export_mappings:
        export_recipe_mappings(processed, args.export_mappings)


if __name__ == '__main__':
    main()

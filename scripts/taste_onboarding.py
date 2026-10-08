"""Account-owned preference drafts. Completing explicitly applies supported fields only."""
import copy
import datetime as dt
import math
from daily_meals import defaults as daily_defaults, validate as validate_daily

VERSION = 1
STATES = {'not_started', 'partial', 'deferred', 'completed'}
FIELDS = {'preferred_cuisines', 'excluded_crea_ids', 'preference_note', 'allow_second_bar',
          'afternoon_fruit', 'banana_min_g', 'banana_max_g'}


def answers(profile):
    daily = profile.get('daily_meals') or daily_defaults(bool(profile.get('food_preferences')))
    return {**{k: copy.deepcopy(profile.get(k, [] if k != 'preference_note' else ''))
               for k in ('preferred_cuisines', 'excluded_crea_ids', 'preference_note')},
            **{k: daily[k] for k in ('allow_second_bar', 'afternoon_fruit', 'banana_min_g', 'banana_max_g')}}


def state(profile, new=False):
    return copy.deepcopy(profile.get('taste_onboarding') or dict(
        version=VERSION, revision=0, status='not_started', step=1, welcome=new,
        draft=answers(profile), updated_at=None))


def validate_draft(value, profile, cuisines, food_ids, strict=True):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('Risposte incomplete o non riconosciute')
    for key, allowed, limit in [('preferred_cuisines', cuisines, 150), ('excluded_crea_ids', food_ids, 300)]:
        items = value[key]
        if not isinstance(items, list) or len(items) > limit or any(not isinstance(x, str) or x not in allowed for x in items):
            raise ValueError('Cucine non valide' if key == 'preferred_cuisines' else 'Scegli alimenti CREA presenti nel catalogo')
    if not isinstance(value['preference_note'], str) or len(value['preference_note']) > 2000:
        raise ValueError('La nota deve contenere al massimo 2000 caratteri')
    daily = copy.deepcopy(profile.get('daily_meals') or daily_defaults(bool(profile.get('food_preferences'))))
    daily.update({k: value[k] for k in ('allow_second_bar', 'afternoon_fruit', 'banana_min_g', 'banana_max_g')})
    if strict:
        validate_daily(daily)
    else:
        if any(type(value[k]) is not bool for k in ('allow_second_bar', 'afternoon_fruit')):
            raise ValueError('Opzione abitudini non valida')
        if any(isinstance(value[k], bool) or not isinstance(value[k], (int, float)) or not math.isfinite(value[k]) or not 0 <= value[k] <= 10000 for k in ('banana_min_g', 'banana_max_g')):
            raise ValueError('Porzioni nella bozza non valide')
    result = copy.deepcopy(value)
    for key in ('preferred_cuisines', 'excluded_crea_ids'):
        result[key] = list(dict.fromkeys(result[key]))
    return result


def transition(profile, payload, cuisines, food_ids):
    current = state(profile)
    if not isinstance(payload, dict) or set(payload) != {'revision', 'action', 'step', 'draft'}:
        raise ValueError('Richiesta preferenze non valida')
    if type(payload['revision']) is not int or payload['revision'] != current['revision']:
        raise RuntimeError('Le preferenze sono cambiate in un’altra sessione. Ricarica prima di salvare; le risposte restano visibili.')
    if type(payload['step']) is not int or payload['step'] not in (1, 2, 3):
        raise ValueError('Passo non valido')
    action = payload['action']
    if action not in ('draft', 'defer', 'complete'):
        raise ValueError('Azione non valida')
    draft = validate_draft(payload['draft'], profile, cuisines, food_ids, strict=action == 'complete')
    updated = copy.deepcopy(profile)
    if action == 'complete':
        updated.update({k: copy.deepcopy(draft[k]) for k in ('preferred_cuisines', 'excluded_crea_ids', 'preference_note')})
        daily = copy.deepcopy(profile.get('daily_meals') or daily_defaults(bool(profile.get('food_preferences'))))
        daily.update({k: draft[k] for k in ('allow_second_bar', 'afternoon_fruit', 'banana_min_g', 'banana_max_g')})
        updated['daily_meals'] = daily
    updated['taste_onboarding'] = dict(version=VERSION, revision=current['revision'] + 1,
        status={'draft': 'partial', 'defer': 'deferred', 'complete': 'completed'}[action],
        step=payload['step'], welcome=False, draft=draft, updated_at=dt.datetime.now(dt.timezone.utc).isoformat())
    return updated


def profile_changed(profile):
    """Invalidate an open wizard after another profile editor saves."""
    current = state(profile)
    current['revision'] += 1
    if current['status'] in ('completed', 'not_started'):
        current['draft'] = answers(profile)
    profile['taste_onboarding'] = current

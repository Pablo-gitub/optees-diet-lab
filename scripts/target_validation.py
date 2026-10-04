"""Informational energy consistency checks, independent of solver constraints."""
import math


def target_warnings(targets):
    keys = ['kcal_100g', 'protein_g_100g', 'carbs_available_g_100g', 'fat_g_100g']
    values = [targets[key]['target'] for key in keys]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values) or values[0] == 0:
        raise ValueError('Bersagli nutrizionali non validi')
    kcal, protein, carbs, fat = values
    macro = 4 * protein + 4 * carbs + 9 * fat
    relative = abs(macro - kcal) / kcal
    if relative <= 0.10 + 1e-12:
        return []
    return [dict(code='targets_inconsistent', kcal_target=kcal, macro_kcal=macro,
                 relative_difference=relative,
                 message=f'I macro bersaglio valgono {macro:g} kcal; il bersaglio energetico è {kcal:g} kcal (scarto oltre il 10%).')]


def profile_target_warnings(profile):
    daily = profile.get('daily_meals', {})
    scope = 'daily' if daily.get('enabled') else 'main_meals'
    targets = daily['targets'] if scope == 'daily' else profile['targets']
    return [dict(warning, scope=scope) for warning in target_warnings(targets)]

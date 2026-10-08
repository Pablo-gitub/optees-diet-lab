"""Versioned milestone contract; runtime persistence lives in progress_dashboard.

Adapter returns the first outstanding definition; it never evaluates health data,
reorders milestones or infers a skip from a later achievement.
"""
import copy
import datetime as dt
import math

STATES = {'pending', 'achieved', 'skipped'}
METRICS = {'weight_kg', 'body_fat_pct', 'sessions_per_week'}


def validate(value):
    if not isinstance(value, dict) or set(value) != {'version', 'items'} or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Schema milestone non valido')
    items = value['items']
    if not isinstance(items, list) or len(items) > 30:
        raise ValueError('Elenco milestone non valido')
    ids = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {'id', 'metric', 'target', 'comparison', 'state', 'desired_date', 'window_weeks'}:
            raise ValueError('Milestone incompleta')
        identifier = item['id']
        if not isinstance(identifier, str) or not identifier or len(identifier) > 80 or identifier in ids:
            raise ValueError('Identità milestone non valida')
        ids.add(identifier)
        metric = item['metric']
        if metric not in METRICS or item['state'] not in STATES or item['comparison'] not in {'at_most', 'at_least'}:
            raise ValueError('Criterio milestone non valido')
        target = item['target']
        if isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target):
            raise ValueError('Valore milestone non valido')
        low, high = {'weight_kg': (30, 300), 'body_fat_pct': (3, 70), 'sessions_per_week': (1, 14)}[metric]
        if not low <= target <= high:
            raise ValueError('Valore milestone fuori intervallo')
        if metric == 'sessions_per_week' and (type(target) is not int or item['comparison'] != 'at_least'):
            raise ValueError('Criterio attività non valido')
        window = item['window_weeks']
        if type(window) is not int or not 1 <= window <= 52 or (metric != 'sessions_per_week' and window != 1):
            raise ValueError('Finestra milestone non valida')
        if item['desired_date'] is not None:
            if not isinstance(item['desired_date'], str):raise ValueError('Data milestone non valida')
            try:dt.date.fromisoformat(item['desired_date'])
            except ValueError:raise ValueError('Data milestone non valida')
    return copy.deepcopy(value)


def active_definition(value):
    """Ordered adapter: later achieved milestones do not bypass a pending one."""
    validated = validate(value)
    return next((item for item in validated['items'] if item['state'] == 'pending'), None)

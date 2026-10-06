"""Reviewed local activity catalogue; never performs a network lookup."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def catalog():
    return copy.deepcopy(json.loads((ROOT/'config/activity-catalog.json').read_text()))

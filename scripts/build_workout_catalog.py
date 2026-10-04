"""Build local draft sessions; source labels and model assumptions stay separate."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EQUIPMENT = {
    "dumbbell": "manubri",
    "barbell": "bilanciere",
    "ez_bar": "bilanciere_curvo",
    "flat_bench": "panca",
    "pull_up_bar": "barra_trazioni",
    "dip_station": "parallele",
    "ab_wheel": "ab_wheel",
    "ab_crunch_machine": "crunch_machine",
    "rower": "vogatore_acqua",
    "stationary_bike": "cyclette",
    "treadmill": "tapis_roulant_inclinabile",
    "elliptical": "ellittica",
}
# Only these exercises have an explicit prerequisite review for draft templates.
REVIEWED = {
    "dumbbell-floor-press": ["manubri"],
    "dumbbell-deadlift": ["manubri"],
    "bodyweight-squat": [],
    "push-up": [],
    "plank": [],
    "inverted-row": ["barra_trazioni"],
    "stationary-bike": ["cyclette"],
    "rowing-machine": ["vogatore_acqua"],
    "incline-treadmill-walk": ["tapis_roulant_inclinabile"],
    "elliptical-trainer": ["ellittica"],
}


def build(source, personal, output):
    raw = source.read_bytes()
    rows = json.loads(raw)["exercises"]
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source exercise IDs")
    profile = json.loads(personal.read_text())
    available = set(profile["equipment"])
    catalog = []
    for row in rows:
        key = row["id"]
        equipment = row.get("equipment")
        # An absent single equipment field is insufficient to guarantee feasibility.
        candidate = equipment is None or EQUIPMENT.get(equipment) in available
        reviewed = key in REVIEWED
        requirements = REVIEWED.get(key)
        feasible = reviewed and set(requirements).issubset(available)
        if key == "inverted-row":
            feasible = feasible and profile["requirements"].get("australian_pullups_setup_verified", False)
        catalog.append(
            {
                "source": "repdb",
                "source_id": key,
                "name": row["name_en"],
                "source_equipment": equipment,
                "source_difficulty": row.get("difficulty"),
                "source_met": row.get("met"),
                "primary_muscles": row.get("primary_muscles", []),
                "secondary_muscles": row.get("secondary_muscles", []),
                "equipment_candidate": candidate,
                "requirements_reviewed": reviewed,
                "requirements": requirements,
                "equipment_feasible": feasible,
                "variant_note": "Piedi a terra, barra regolabile" if key == "inverted-row" else None,
            }
        )
    index = {x["source_id"]: x for x in catalog}
    from workout_sessions import build_sessions
    templates, unavailable = build_sessions(index)
    result = {
        "model_version": "workout-sessions-v2",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "coefficients": {"primary_muscle_per_set": 1.0, "secondary_muscle_per_set": 0.5},
        "assumptions": "Coefficients and durations are explicit heuristics, not validated efficacy scores."
        " MET retained as source metadata; not used to predict calories or body changes.",
        "catalog": catalog,
        "templates": templates,
        "unavailable_sessions": unavailable,
        "protocols_sha256": hashlib.sha256((ROOT / "config/workout-protocols.json").read_bytes()).hexdigest(),
        "pending_custom_equipment": ["aqua_bag", "aqua_tank"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--equipment", type=Path, default=ROOT / "data/personal/equipment.json")
    args = parser.parse_args()
    result = build(
        ROOT / "dataset/repdb/raw/exercises.json", args.equipment, ROOT / "data/personal/workout_catalog.json"
    )
    print(
        f"{len(result['catalog'])} exercises; "
        f"{sum(x['equipment_candidate'] for x in result['catalog'])} equipment candidates; "
        f"{len(result['templates'])} draft templates"
    )

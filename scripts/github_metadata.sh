#!/usr/bin/env bash
# Imposta descrizione e tag del repository GitHub in un solo passaggio.
# Uso: scripts/github_metadata.sh <proprietario/repository>   es. Pablo-gitub/optees-diet-lab
# Richiede gh autenticato; il repository deve già esistere.
set -euo pipefail

repo="${1:?Indica il repository, es. Pablo-gitub/optees-diet-lab}"

description="Personal diet & training planner built as a case study for Optees: weekly meal plans and workouts optimised with MILP (Pareto, min-max, bandit), food diary with presumed meals, Monday check-in and safe recalibration. FastAPI + SQLite + vanilla JS."

topics=(
  optimization operations-research mixed-integer-programming milp
  multi-objective-optimization pareto multi-armed-bandit
  nutrition meal-planner diet-planner fitness workout-planner food-diary
  fastapi sqlite mcp
)

args=(--description "$description" --enable-wiki=false --enable-projects=false)
for topic in "${topics[@]}"; do args+=(--add-topic "$topic"); done

gh repo edit "$repo" "${args[@]}"

echo "Fatto. Controllo:"
gh repo view "$repo" --json description,repositoryTopics \
  --jq '.description, ([.repositoryTopics[].name] | join(", "))'

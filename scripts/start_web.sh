#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec /home/paolo/anaconda3/envs/optees/bin/python -m uvicorn web.app:app --host "${DIET_WEB_HOST:-127.0.0.1}" --port "${DIET_WEB_PORT:-8765}"

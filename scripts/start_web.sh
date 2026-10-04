#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Local machine settings (DIET_PYTHON, OPTEES_COMMAND, ...), excluded from Git.
if [ -f .env ]; then set -a; . ./.env; set +a; fi
exec "${DIET_PYTHON:-python}" -m uvicorn web.app:app --host "${DIET_WEB_HOST:-127.0.0.1}" --port "${DIET_WEB_PORT:-8765}"

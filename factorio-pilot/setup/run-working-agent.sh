#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
cd "$FACTORIO_PILOT_HOME"
export FLE_GETPATH_MAX_ATTEMPTS=20
exec .venv/bin/python "$pilot_source"/tools/working_agent.py "$@"

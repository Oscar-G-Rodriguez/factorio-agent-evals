#!/usr/bin/env bash
set -euo pipefail
cd /home/osci2/factorio-pilot
export FLE_GETPATH_MAX_ATTEMPTS=20
exec .venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/working_agent.py "$@"

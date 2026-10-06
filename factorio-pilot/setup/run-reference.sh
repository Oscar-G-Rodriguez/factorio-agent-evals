#!/usr/bin/env bash
set -euo pipefail
docker compose -f /home/osci2/factorio-pilot/cluster/compose.yaml restart factorio_0
runuser -u osci2 -- bash -c '
  cd /home/osci2/factorio-pilot
  export FLE_GETPATH_MAX_ATTEMPTS=20
  sleep 3
  exec .venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/reference_factory.py
'

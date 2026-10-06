#!/usr/bin/env bash
set -euo pipefail
for repetition in 1 2; do
  for policy in history structured-memory; do
    docker compose -f /home/osci2/factorio-pilot/cluster/compose.yaml restart factorio_0
    runuser -u osci2 -- bash -c '
      cd /home/osci2/factorio-pilot
      export FLE_GETPATH_MAX_ATTEMPTS=20
      sleep 3
      exec .venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/run_agent.py --mode "$1" --steps 32 --seed 42 --context-policy "$2"
    ' task-agent "$([ "$policy" = history ] && echo baseline || echo intervention)" "$policy"
  done
done

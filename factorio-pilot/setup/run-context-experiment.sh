#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ $(id -u) -ne 0 ]]; then
  echo 'Run as root to restart the local container; the agent runs as the runtime owner.' >&2
  exit 1
fi
for repetition in 1 2; do
  for policy in history structured-memory; do
    docker compose -f "$pilot_compose" restart factorio_0
    mode=intervention
    if [[ "$policy" == history ]]; then mode=baseline; fi
    pilot_as_runtime_owner bash -c '
      set -euo pipefail
      cd "$FACTORIO_PILOT_HOME"
      export FLE_GETPATH_MAX_ATTEMPTS=20
      sleep 3
      exec "$PILOT_PYTHON" "$PILOT_SOURCE/tools/run_agent.py" --mode "$1" --steps 32 --seed 42 --context-policy "$2"
    ' task-agent "$mode" "$policy"
  done
done

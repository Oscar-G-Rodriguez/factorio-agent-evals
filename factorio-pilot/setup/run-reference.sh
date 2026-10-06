#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ $(id -u) -ne 0 ]]; then
  echo 'Run as root to restart the local container; the reference runs as the runtime owner.' >&2
  exit 1
fi
docker compose -f "$pilot_compose" restart factorio_0
pilot_as_runtime_owner bash -c '
  set -euo pipefail
  cd "$FACTORIO_PILOT_HOME"
  export FLE_GETPATH_MAX_ATTEMPTS=20
  sleep 3
  exec "$PILOT_PYTHON" "$PILOT_SOURCE/tools/reference_factory.py"
'

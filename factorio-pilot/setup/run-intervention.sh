#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ $(id -u) -ne 0 ]]; then
  echo 'Run as root to restart the local container; the agent runs as the runtime owner.' >&2
  exit 1
fi
docker compose -f "$pilot_compose" restart factorio_0
pilot_as_runtime_owner bash -c '
  set -euo pipefail
  cd "$FACTORIO_PILOT_HOME"
  export FLE_GETPATH_MAX_ATTEMPTS=20
  "$PILOT_PYTHON" -c "import socket,time; deadline=time.monotonic()+30
while True:
 try:
  s=socket.create_connection((\"127.0.0.1\",27000),timeout=1); s.close(); break
 except OSError:
  if time.monotonic()>deadline: raise
  time.sleep(0.2)"
  exec "$PILOT_PYTHON" "$PILOT_SOURCE/tools/run_agent.py" --mode intervention --steps 32 --seed 42
'

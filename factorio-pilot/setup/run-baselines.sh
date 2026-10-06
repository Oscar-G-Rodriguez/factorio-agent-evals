#!/usr/bin/env bash
set -euo pipefail
if [[ $(id -u) -ne 0 ]]; then
  echo 'Root is used only to restart the project container. Agent runs as osci2.' >&2
  exit 1
fi
project=/home/osci2/factorio-pilot
for seed in 42 43; do
  # The server starts the same bundled scenario afresh; this also resets terrain.
  docker compose -f "$project/cluster/compose.yaml" restart factorio_0
  runuser -u osci2 -- /bin/bash -c '
    set -euo pipefail
    cd /home/osci2/factorio-pilot
    export FLE_GETPATH_MAX_ATTEMPTS=20
    .venv/bin/python -c "import socket,time; deadline=time.monotonic()+30
while True:
 try:
  s=socket.create_connection((\"127.0.0.1\",27000),timeout=1); s.close(); break
 except OSError:
  if time.monotonic()>deadline: raise
  time.sleep(0.2)"
    exec .venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/run_agent.py --mode baseline --steps 32 --seed "$1"
  ' task-agent "$seed"
done

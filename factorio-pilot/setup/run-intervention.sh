#!/usr/bin/env bash
set -euo pipefail
docker compose -f /home/osci2/factorio-pilot/cluster/compose.yaml restart factorio_0
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
  exec .venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/run_agent.py --mode intervention --steps 32 --seed 42
'

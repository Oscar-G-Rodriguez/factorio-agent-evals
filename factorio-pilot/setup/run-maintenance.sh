#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
pilot_home="${FACTORIO_PILOT_HOME:-$HOME/factorio-pilot}"
export FACTORIO_PILOT_HOME="$pilot_home"

if [[ ! -x "$pilot_home/.venv/bin/python" ]]; then
  echo "Missing Python environment: $pilot_home/.venv/bin/python" >&2
  exit 2
fi
if [[ ! -f "$pilot_home/artifacts/starting-state.json" ]]; then
  echo "Missing starting state: $pilot_home/artifacts/starting-state.json" >&2
  exit 2
fi
if [[ ! -d "$pilot_home/runs" ]]; then
  echo "Missing runs directory: $pilot_home/runs" >&2
  exit 2
fi

cd "$pilot_home"
exec "$pilot_home/.venv/bin/python" "$script_dir/../tools/maintenance_agent.py" "$@"

#!/usr/bin/env bash
# Source this file from a launcher to locate code and local runtime storage.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
pilot_source="$(cd -- "$script_dir/.." && pwd)"
if [[ -z "${FACTORIO_PILOT_HOME:-}" ]]; then
  if [[ $(id -u) -eq 0 ]]; then
    if [[ -z "${FACTORIO_PILOT_USER:-}" ]]; then
      echo 'Set FACTORIO_PILOT_HOME or FACTORIO_PILOT_USER for root launchers.' >&2
      return 1
    fi
    pilot_user_home="$(getent passwd "$FACTORIO_PILOT_USER" | cut -d: -f6)"
    if [[ -z "$pilot_user_home" ]]; then
      echo 'FACTORIO_PILOT_USER does not exist in this Linux environment.' >&2
      return 1
    fi
    export FACTORIO_PILOT_HOME="$pilot_user_home/factorio-pilot"
  else
    export FACTORIO_PILOT_HOME="$HOME/factorio-pilot"
  fi
fi
pilot_python="$FACTORIO_PILOT_HOME/.venv/bin/python"
pilot_compose="$FACTORIO_PILOT_HOME/cluster/compose.yaml"

pilot_as_runtime_owner() {
  local pilot_user
  pilot_user="${FACTORIO_PILOT_USER:-$(stat -c %U "$FACTORIO_PILOT_HOME")}"
  if [[ "$pilot_user" == root || "$pilot_user" == UNKNOWN ]]; then
    echo 'Set FACTORIO_PILOT_USER to the ordinary account that owns the runtime.' >&2
    return 1
  fi
  runuser -u "$pilot_user" -- env "FACTORIO_PILOT_HOME=$FACTORIO_PILOT_HOME" "PILOT_SOURCE=$pilot_source" "PILOT_PYTHON=$pilot_python" "$@"
}

#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
"$FACTORIO_PILOT_HOME/.venv/bin/python" \
  "$pilot_source"/tools/download_model.py

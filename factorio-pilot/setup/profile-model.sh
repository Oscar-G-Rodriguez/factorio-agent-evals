#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
cd "$FACTORIO_PILOT_HOME"
export PATH="/usr/local/cuda-12.8/bin:/usr/lib/wsl/lib:$PATH"
.venv/bin/python "$pilot_source"/tools/profile_model.py

#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
cd "$FACTORIO_PILOT_HOME"
export PATH=/usr/local/cuda-12.8/bin:$PATH
export CUDA_HOME=/usr/local/cuda-12.8
export MAX_JOBS=2
export TORCH_CUDA_ARCH_LIST=12.0
exec .venv/bin/python "$pilot_source"/tools/check_rmsnorm.py "$@"

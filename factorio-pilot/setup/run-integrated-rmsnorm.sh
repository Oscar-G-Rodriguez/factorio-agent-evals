#!/usr/bin/env bash
# Offline K02 validation/timing; never connects to or resets a Factorio server.
set -euo pipefail
if [[ $(id -u) -eq 0 ]]; then
  echo 'Run K02 as the ordinary account that owns the configured runtime.' >&2
  exit 1
fi
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="$CUDA_HOME/bin:$PATH"
export MAX_JOBS=2
export TORCH_CUDA_ARCH_LIST=12.0
export TORCHINDUCTOR_COMPILE_THREADS=1
exec "$pilot_python" "$pilot_source/tools/check_integrated_rmsnorm.py" "$@"

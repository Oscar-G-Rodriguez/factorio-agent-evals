#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
project=$FACTORIO_PILOT_HOME
"$project/.venv/bin/python" "$pilot_source"/tools/cuda_review.py --stage correctness
mkdir -p "$project/build" "$project/artifacts"
export PATH="/usr/local/cuda-12.8/bin:/usr/lib/wsl/lib:$PATH"
nvcc -O2 -lineinfo -arch=sm_120 \
  "$pilot_source"/cuda/smoke.cu \
  -o "$project/build/cuda_smoke"
"$project/build/cuda_smoke" | tee "$project/artifacts/cuda-smoke.txt"
for tool in memcheck racecheck initcheck synccheck; do
  compute-sanitizer --tool "$tool" --error-exitcode 1 "$project/build/cuda_smoke" \
    2>&1 | tee "$project/artifacts/cuda-$tool.txt"
done

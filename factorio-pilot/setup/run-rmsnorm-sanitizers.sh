#!/usr/bin/env bash
# Only after explicit approval and activation of the Windows debugging interface.
set -euo pipefail
cd /home/osci2/factorio-pilot
export PATH=/usr/local/cuda-12.8/bin:$PATH
export CUDA_HOME=/usr/local/cuda-12.8
export MAX_JOBS=2
export TORCH_CUDA_ARCH_LIST=12.0
for tool in memcheck racecheck initcheck synccheck; do
  compute-sanitizer --tool "$tool" --error-exitcode 1 \
    .venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/check_rmsnorm.py --tests-only \
    2>&1 | tee "artifacts/rmsnorm-$tool.txt"
done

#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ $(id -u) -eq 0 ]]; then
  echo 'Run as the ordinary project user, not root.' >&2
  exit 1
fi
project=$FACTORIO_PILOT_HOME
python="$project/.venv/bin/python"
mkdir -p "$project/artifacts"
"$python" -m pip install --upgrade pip
"$python" -m pip install 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cu128
"$python" -m pip install 'transformers>=4.51,<5' accelerate \
  'factorio-learning-environment @ git+https://github.com/JackHopkins/factorio-learning-environment.git@e2a829d22a635a9a111d21bf5523e09e903ae145' ninja
"$python" -m pip check
"$python" -m pip freeze > "$project/artifacts/requirements-tested.txt"
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="$CUDA_HOME/bin:/usr/lib/wsl/lib:$PATH"
"$python" "$pilot_source"/tools/check_environment.py --output "$project/artifacts/preflight-linux.json"

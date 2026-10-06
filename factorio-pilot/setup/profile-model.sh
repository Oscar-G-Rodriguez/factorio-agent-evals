#!/usr/bin/env bash
set -euo pipefail
cd /home/osci2/factorio-pilot
export PATH="/usr/local/cuda-12.8/bin:/usr/lib/wsl/lib:$PATH"
.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/profile_model.py

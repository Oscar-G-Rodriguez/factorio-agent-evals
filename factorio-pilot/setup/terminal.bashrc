source /home/osci2/.bashrc
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="$CUDA_HOME/bin:/usr/lib/wsl/lib:$PATH"
cd /home/osci2/factorio-pilot
source .venv/bin/activate
printf '\nFactorio pilot terminal: Ubuntu, project Python, CUDA 12.8.\nKeep this shell open while the local server runs.\n\n'

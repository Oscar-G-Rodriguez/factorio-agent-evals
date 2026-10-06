#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if [[ $(id -u) -ne 0 ]]; then
  echo 'Run this setup as root inside the project Ubuntu distribution.' >&2
  exit 1
fi
source /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then
  echo 'This setup is scoped to Ubuntu 24.04.' >&2
  exit 1
fi

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl python3-venv python3-dev build-essential cmake \
  ninja-build git pkg-config

install -m 0755 -d /etc/apt/keyrings
curl --fail --silent --show-error --location \
  https://download.docker.com/linux/ubuntu/gpg \
  --output /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

install -m 0755 -d /var/tmp/factorio-pilot-setup
curl --fail --silent --show-error --location \
  https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb \
  --output /var/tmp/factorio-pilot-setup/cuda-keyring.deb
dpkg -i /var/tmp/factorio-pilot-setup/cuda-keyring.deb
apt-get update

cuda_packages=(cuda-nvcc-12-8 cuda-cudart-dev-12-8 cuda-cccl-12-8 cuda-sanitizer-12-8)
apt-get --simulate install --no-install-recommends "${cuda_packages[@]}" \
  > /var/tmp/factorio-pilot-setup/cuda-install-plan.txt
if grep -Eq '^Inst (nvidia-driver|nvidia-dkms|nvidia-kernel|cuda-drivers)' \
  /var/tmp/factorio-pilot-setup/cuda-install-plan.txt; then
  echo 'Unexpected Linux GPU driver dependency; stop and inspect the package plan.' >&2
  exit 1
fi
apt-get install -y --no-install-recommends \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
  "${cuda_packages[@]}"
systemctl start docker
docker version
docker run --rm hello-world
/usr/local/cuda-12.8/bin/nvcc --version
/usr/local/cuda-12.8/bin/compute-sanitizer --version

# Model-generated game programs will run under an ordinary Linux user.
# No sudo membership, password exemption, or docker group access is added.
if ! id osci2 >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash osci2
fi
install -d -o osci2 -g osci2 /home/osci2/factorio-pilot
runuser -u osci2 -- python3 -m venv /home/osci2/factorio-pilot/.venv
echo 'Linux tools installed. Project virtual environment created for osci2.'

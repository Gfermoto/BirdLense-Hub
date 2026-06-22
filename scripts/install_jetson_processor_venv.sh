#!/usr/bin/env bash
# Jetson Nano JP4.6 (L4T r32.7): processor = Python 3.6 + CUDA torch + TensorRT (как l4t-pytorch).
# Web/MCP — micromamba python3.11; процессор — /opt/jetson-processor (python3.6).
set -euo pipefail

VENV="${JETSON_PROCESSOR_VENV:-/opt/jetson-processor}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REQ="${JETSON_PROCESSOR_REQUIREMENTS:-${ROOT}/app/processor/requirements-jetson.txt}"
if [[ ! -f "${REQ}" ]]; then
  REQ="/tmp/processor-requirements.jetson.txt"
fi
L4T_PYTORCH_IMAGE="${JETSON_L4T_PYTORCH_IMAGE:-nvcr.io/nvidia/l4t-pytorch:r32.7.1-pth1.10-py3}"
CUDA_LIB="${CUDA_HOME:-/usr/local/cuda}/lib64"
TEGRA_LIB="/usr/lib/aarch64-linux-gnu/tegra"

export LD_LIBRARY_PATH="${CUDA_LIB}:${TEGRA_LIB}:${LD_LIBRARY_PATH:-}"

_cuda_torch_ok() {
  [[ -x "${VENV}/bin/python" ]] || return 1
  "${VENV}/bin/python" -c "import torch; assert torch.cuda.is_available()" 2>/dev/null
}

if _cuda_torch_ok; then
  echo "jetson-processor-venv: CUDA torch OK (${VENV})"
  exit 0
fi

if [[ "${JETSON_SKIP_CUDA_VERIFY:-0}" == "1" ]]; then
  _skip_verify=1
else
  _skip_verify=0
fi

echo "=== Jetson processor venv (python3.6 + CUDA 10.2) ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  python3.6 python3.6-dev python3.6-venv python3.6-distutils \
  libopenblas-dev libgomp1 libopenmpi2 libopenmpi-dev git curl \
  >/dev/null

rm -rf "${VENV}"
python3.6 -m venv --system-site-packages "${VENV}"
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -m pip install -U "pip<22" wheel setuptools

echo "=== CUDA stack from ${L4T_PYTORCH_IMAGE} ==="
_py_site="${VENV}/lib/python3.6/site-packages"
mkdir -p "${_py_site}"

_copy_from_l4t_pytorch() {
  local cid
  cid="$(docker create "${L4T_PYTORCH_IMAGE}")"
  docker cp "${cid}:/usr/local/lib/python3.6/dist-packages/torch" "${_py_site}/" 2>/dev/null || true
  docker cp "${cid}:/usr/local/lib/python3.6/dist-packages/torchvision" "${_py_site}/" 2>/dev/null || true
  for egg in torch torchvision; do
    docker cp "${cid}:/usr/local/lib/python3.6/dist-packages/${egg}-"*.egg-info "${_py_site}/" 2>/dev/null || true
  done
  mkdir -p "${VENV}/lib/python3.6/dist-packages"
  docker cp "${cid}:/usr/lib/python3.6/dist-packages/tensorrt" "${VENV}/lib/python3.6/dist-packages/" 2>/dev/null || true
  docker rm "${cid}" >/dev/null
}

if command -v docker >/dev/null 2>&1 && [[ "${JETSON_SKIP_CUDA_VERIFY:-0}" != "1" ]]; then
  if docker image inspect "${L4T_PYTORCH_IMAGE}" >/dev/null 2>&1 || docker pull "${L4T_PYTORCH_IMAGE}"; then
    _copy_from_l4t_pytorch
  fi
fi

# Хост Jetson: tensorrt уже в /usr/lib/python3.6/dist-packages (bind-mount в compose).
if [[ -d /usr/lib/python3.6/dist-packages/tensorrt ]]; then
  mkdir -p "${VENV}/lib/python3.6/dist-packages"
  ln -sfn /usr/lib/python3.6/dist-packages/tensorrt "${VENV}/lib/python3.6/dist-packages/tensorrt" 2>/dev/null || true
fi

if ! _cuda_torch_ok; then
  if [[ "${_skip_verify}" == "1" ]]; then
    echo "WARN: CUDA torch not verified yet (torch layers copied in next Dockerfile stage)" >&2
  else
    echo "ERROR: CUDA torch not available in ${VENV}. Need ${L4T_PYTORCH_IMAGE} or host tegra+cuda libs." >&2
    exit 2
  fi
fi

echo "torch: $("${VENV}/bin/python" -c 'import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda)')"

echo "=== processor requirements (py3.6) ==="
pip install --no-cache-dir -r "${REQ}"

if ! "${VENV}/bin/python" -c "import tensorrt" 2>/dev/null; then
  echo "WARN: tensorrt python missing — mount /usr/lib/python3.6/dist-packages/tensorrt in compose" >&2
fi

echo "jetson-processor-venv: OK"

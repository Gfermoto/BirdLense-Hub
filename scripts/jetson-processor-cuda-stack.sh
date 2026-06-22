#!/usr/bin/env bash
# Hotfix: CUDA PyTorch + TensorRT python 3.6 в running birdlense (JP4.6).
# Копируем полный dist-packages из l4t-pytorch — частичный torch даёт SIGILL.
set -euo pipefail

CONTAINER="${BIRDLENSE_CONTAINER:-birdlense}"
IMAGE="${JETSON_L4T_PYTORCH_IMAGE:-nvcr.io/nvidia/l4t-pytorch:r32.7.1-pth1.10-py3}"
DEST="/opt/jetson-cuda-py36"
STACK="/tmp/jp-dist"

mkdir -p "${STACK}"
if [[ ! -f "${STACK}/torch/__init__.py" ]]; then
  cid="$(docker create "${IMAGE}")"
  rm -rf "${STACK}"
  docker cp "${cid}:/usr/local/lib/python3.6/dist-packages" "${STACK}"
  docker cp "${cid}:/usr/lib/python3.6/dist-packages/tensorrt" "${STACK}/tensorrt"
  docker rm "${cid}" >/dev/null
fi

docker exec -u root "${CONTAINER}" bash -c 'export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq libopenmpi2 libopenblas-base python3-pip curl 2>/dev/null || apt-get install -y -qq libopenmpi2 libopenblas-base python3-pip curl'
docker exec -u root "${CONTAINER}" bash -c 'if ! /usr/bin/python3.6 -m pip --version >/dev/null 2>&1; then curl -fsSL https://bootstrap.pypa.io/pip/3.6/get-pip.py -o /tmp/get-pip.py && /usr/bin/python3.6 /tmp/get-pip.py; fi'
docker exec -u root "${CONTAINER}" rm -rf "${DEST}"
docker cp "${STACK}" "${CONTAINER}:${DEST}"

docker exec "${CONTAINER}" env \
  PYTHONPATH="${DEST}:/usr/lib/python3.6/dist-packages" \
  LD_LIBRARY_PATH="/usr/local/cuda/lib64:/usr/lib/aarch64-linux-gnu/tegra:/usr/lib/aarch64-linux-gnu" \
  /usr/bin/python3.6 -c "import torch,tensorrt; assert torch.cuda.is_available(); print('OK', torch.__version__, tensorrt.__version__)"

echo "jetson-processor-cuda-stack: OK (${CONTAINER}, PYTHONPATH=${DEST})"

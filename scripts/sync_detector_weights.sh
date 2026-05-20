#!/usr/bin/env bash
# Проверка и (опционально) восстановление весов бинарного детектора NABirds + OpenVINO IR.
# Вызывается: make sync-models, deploy.sh (перед docker compose up на сервере).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WEIGHTS_DIR="${WEIGHTS_DIR:-${REPO_ROOT}/app/processor/models/detection/weights}"
OV_DIR="${WEIGHTS_DIR}/best_NABirds_openvino_model"
PT="${WEIGHTS_DIR}/best_NABirds.pt"
EXPORT="${EXPORT:-0}"
CHECK_ONLY="${CHECK_ONLY:-0}"

usage() {
  cat <<'EOF'
Usage: sync_detector_weights.sh [--check] [--export-if-missing]

  --check              только проверка (exit 1 если чего-то нет)
  --export-if-missing  при отсутствии IR запустить export_nabirds_to_openvino.py (нужен ultralytics)

Env:
  WEIGHTS_DIR  каталог weights (по умолчанию app/processor/models/detection/weights)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --export-if-missing) EXPORT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

missing=()
[[ -f "${PT}" ]] || missing+=("${PT}")
[[ -f "${OV_DIR}/best.xml" ]] || missing+=("${OV_DIR}/best.xml")
[[ -f "${OV_DIR}/best.bin" ]] || missing+=("${OV_DIR}/best.bin")
[[ -f "${OV_DIR}/metadata.yaml" ]] || missing+=("${OV_DIR}/metadata.yaml")

if [[ ${#missing[@]} -eq 0 ]]; then
  echo "sync_detector_weights: OK (${OV_DIR})"
  exit 0
fi

echo "sync_detector_weights: missing:" >&2
printf '  %s\n' "${missing[@]}" >&2

if [[ "${EXPORT}" == "1" && -f "${PT}" ]]; then
  echo "sync_detector_weights: exporting OpenVINO (FP32, imgsz=640)..." >&2
  if ! python3 "${SCRIPT_DIR}/export_nabirds_to_openvino.py" --imgsz 640 --precision fp32; then
    echo "sync_detector_weights: export failed" >&2
    exit 1
  fi
  missing=()
  [[ -f "${OV_DIR}/best.xml" ]] || missing+=("${OV_DIR}/best.xml")
  [[ -f "${OV_DIR}/best.bin" ]] || missing+=("${OV_DIR}/best.bin")
  if [[ ${#missing[@]} -eq 0 ]]; then
    echo "sync_detector_weights: OK after export"
    exit 0
  fi
fi

echo "sync_detector_weights: commit best_NABirds_openvino_model/ or run with --export-if-missing" >&2
exit 1

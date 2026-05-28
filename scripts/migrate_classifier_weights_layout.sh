#!/usr/bin/env bash
# Flatten classifier weights to detector-style layout (#516).
# Result: {variant}.pt + {variant}_openvino_model/ only — no legacy/, no variant/ subdirs.
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
W="${ROOT}/app/processor/models/classification/weights"
VARIANT="${BIRDLENSE_BIRDER_VARIANT:-convnext_v2_tiny_eu-common256px}"

mkdir -p "${W}"

_flatten_dir() {
  local dir="$1"
  [[ -d "${dir}" ]] || return 0
  if [[ -f "${dir}/${VARIANT}.pt" ]]; then
    mv -n "${dir}/${VARIANT}.pt" "${W}/${VARIANT}.pt" 2>/dev/null || true
  fi
  if [[ -f "${dir}/class_labels.txt" ]]; then
    mkdir -p "${W}/${VARIANT}_openvino_model"
    cp -a "${dir}/class_labels.txt" "${W}/${VARIANT}_openvino_model/" 2>/dev/null || true
  fi
  if [[ -f "${dir}/birdlense_manifest.json" ]]; then
    mkdir -p "${W}/${VARIANT}_openvino_model"
    cp -a "${dir}/birdlense_manifest.json" "${W}/${VARIANT}_openvino_model/" 2>/dev/null || true
  fi
  if [[ -f "${dir}/${VARIANT}.json" ]]; then
    mkdir -p "${W}/${VARIANT}_openvino_model"
    cp -a "${dir}/${VARIANT}.json" "${W}/${VARIANT}_openvino_model/" 2>/dev/null || true
  fi
  if [[ -d "${dir}" ]]; then
  shopt -s nullglob
  remain=("${dir}"/*)
  shopt -u nullglob
  if [[ ${#remain[@]} -eq 0 ]]; then
    rmdir "${dir}" 2>/dev/null || true
  fi
  fi
}

OV="${W}/${VARIANT}_openvino_model"
mkdir -p "${OV}"

# Old birder_* or bare variant subdir
_flatten_dir "${W}/birder_${VARIANT//-/_}"
_flatten_dir "${W}/${VARIANT}"

# Stray metadata in empty variant dir -> openvino bundle
if [[ -d "${W}/${VARIANT}" ]]; then
  for f in class_labels.txt birdlense_manifest.json "${VARIANT}.json"; do
    [[ -f "${W}/${VARIANT}/${f}" && ! -f "${OV}/${f}" ]] && mv "${W}/${VARIANT}/${f}" "${OV}/"
  done
  rm -rf "${W}/${VARIANT}"
fi

# Rename openvino bundles
if [[ -d "${W}/birder_${VARIANT//-/_}_openvino" && ! -d "${W}/${VARIANT}_openvino_model" ]]; then
  mv "${W}/birder_${VARIANT//-/_}_openvino" "${W}/${VARIANT}_openvino_model"
fi
if [[ -d "${W}/${VARIANT}_openvino" && ! -d "${W}/${VARIANT}_openvino_model" ]]; then
  mv "${W}/${VARIANT}_openvino" "${W}/${VARIANT}_openvino_model"
fi

# Remove clutter
rm -rf "${W}/legacy"
rm -f "${W}/class_names.txt" "${W}/class_labels.txt"
rm -rf "${W}/birds_classifier_efficientnetb2" "${W}/birds_classifier_efficientnetb2_openvino"
rm -f "${W}/best.pt" "${W}/best_openvino_model"
rm -rf "${W}/best_openvino_model" 2>/dev/null || true

echo "Expected:"
echo "  ${W}/${VARIANT}.pt"
echo "  ${W}/${VARIANT}_openvino_model/openvino_model.xml"
ls -la "${W}/" 2>/dev/null || true

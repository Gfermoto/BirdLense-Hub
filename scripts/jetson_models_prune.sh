#!/usr/bin/env bash
# Keep only Jetson runtime model artifacts (user allowlist). Dry-run by default.
set -euo pipefail

MODELS_ROOT="${1:-app/processor/models}"
DRY="${JETSON_PRUNE_DRY_RUN:-1}"

cd "$(dirname "$0")/.."

keep=(
  "detection/trapper_ai_v02_2024/trapper_ai_v02_2024.engine"
  "detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx"
  "detection/trapper_ai_v02_2024/trapper_ai_v02_2024.pt"
  "detection/trapper_ai_v02_2024/trapper_ai_v02_2024.yaml"
  "reid/ornimetrics/reid_embedder.onnx"
  "welfare/ornimetrics/embedder.onnx"
  "welfare/ornimetrics/welfare_scorer.npz"
)

keep_prefixes=(
  "classification/chriamue_bird_species_classifier/"
)

is_kept() {
  local rel="$1"
  local k p
  for k in "${keep[@]}"; do
    [[ "$rel" == "$k" ]] && return 0
  done
  for p in "${keep_prefixes[@]}"; do
    [[ "$rel" == "$p"* ]] && return 0
  done
  return 1
}

echo "Models root: $MODELS_ROOT (DRY_RUN=$DRY)"
find "$MODELS_ROOT" -type f | sort | while read -r f; do
  rel="${f#${MODELS_ROOT}/}"
  if is_kept "$rel"; then
    echo "KEEP  $rel"
  else
    echo "REMOVE $rel"
    [[ "$DRY" == "0" ]] && rm -f "$f"
  fi
done

if [[ "$DRY" == "0" ]]; then
  find "$MODELS_ROOT" -type d -empty -delete 2>/dev/null || true
fi

echo "Allowlist (exact):"
printf '  %s\n' "${keep[@]}"
echo "Allowlist (prefix):"
printf '  %s*\n' "${keep_prefixes[@]}"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="two_stage"
CHECK_ONLY=0
RELEASE_TAG="${RELEASE_TAG:-weights/v1}"
LEGACY_ASSET="yolo11n.pt"
LEGACY_DEST="${ROOT}/app/yolo11n.pt"
DETECTOR_ZIP="${DETECTOR_ZIP:-${ROOT}/app/processor/models/detection/nabirds_yolo11n_binary.zip}"
DETECTOR_DEST="${ROOT}/app/processor/models/detection/weights/best.pt"
CLASSIFIER_DEST="${ROOT}/app/processor/models/classification/weights/best.pt"
# Пин ревизии HF (не main): иначе при обновлении ветки ломается CHECKSUMS/CI.
CLASSIFIER_URL="${CLASSIFIER_URL:-https://huggingface.co/gfermoto/birdlense-birds-eu/resolve/c6af5aa595cbb1198a61bcf2f3f9c2adc3772dc9/best.pt}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/fetch-processor-weights.sh
  ./scripts/fetch-processor-weights.sh --legacy-single-stage
  ./scripts/fetch-processor-weights.sh --check-only

Options:
  --legacy-single-stage  Download compatibility-only app/yolo11n.pt from GitHub Release.
  --check-only           Do not download anything; only verify active two-stage paths.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --legacy-single-stage)
      MODE="legacy"
      ;;
    --check-only)
      CHECK_ONLY=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

cd "$(git rev-parse --show-toplevel)"

ensure_dir() {
  mkdir -p "$(dirname "$1")"
}

fetch_legacy_single_stage() {
  ensure_dir "$LEGACY_DEST"
  tmpdir="$(mktemp -d)"
  echo "Fetching legacy compatibility asset ${LEGACY_ASSET} from ${RELEASE_TAG}..."
  gh release download "$RELEASE_TAG" --repo "Gfermoto/BirdLense-Hub" --pattern "$LEGACY_ASSET" --dir "$tmpdir"
  downloaded="$tmpdir/$LEGACY_ASSET"
  if [[ ! -f "$downloaded" ]]; then
    echo "ERROR: legacy asset not found in release: ${LEGACY_ASSET}" >&2
    rm -rf "$tmpdir"
    exit 3
  fi
  echo "Verifying checksum against CHECKSUMS..."
  expected="$(awk '/  app\/yolo11n\.pt$/ {print $1}' CHECKSUMS)"
  actual="$(sha256sum "$downloaded" | awk '{print $1}')"
  if [[ -z "$expected" ]]; then
    echo "ERROR: CHECKSUMS entry missing for app/yolo11n.pt" >&2
    rm -rf "$tmpdir"
    exit 4
  fi
  if [[ "$expected" != "$actual" ]]; then
    echo "ERROR: checksum mismatch for legacy asset" >&2
    echo "expected=$expected" >&2
    echo "actual=$actual" >&2
    rm -rf "$tmpdir"
    exit 5
  fi
  mv "$downloaded" "$LEGACY_DEST"
  rm -rf "$tmpdir"
  echo "Legacy asset ready: $LEGACY_DEST"
}

ensure_two_stage_detector() {
  if [[ -s "$DETECTOR_DEST" ]]; then
    echo "Detector weights already present: $DETECTOR_DEST"
    return
  fi
  if [[ -s "$DETECTOR_ZIP" ]]; then
    echo "Extracting detector weights from $DETECTOR_ZIP..."
    ensure_dir "$DETECTOR_DEST"
    unzip -j -o "$DETECTOR_ZIP" weights/best.pt -d "$(dirname "$DETECTOR_DEST")"
    return
  fi
  echo "ERROR: missing detector weights." >&2
  echo "Expected: $DETECTOR_DEST" >&2
  echo "Provide the zip artifact at: $DETECTOR_ZIP" >&2
  exit 6
}

ensure_two_stage_classifier() {
  if [[ -s "$CLASSIFIER_DEST" ]]; then
    echo "Classifier weights already present: $CLASSIFIER_DEST"
    return
  fi
  echo "Downloading EU classifier weights..."
  ensure_dir "$CLASSIFIER_DEST"
  tmp="$(mktemp)"
  curl -fsSL --retry 3 --retry-connrefused --retry-delay 5 -o "$tmp" "$CLASSIFIER_URL"
  echo "Verifying classifier checksum against CHECKSUMS..."
  expected="$(awk '/  app\/processor\/models\/classification\/weights\/best\.pt$/ {print $1}' "${ROOT}/CHECKSUMS")"
  actual="$(sha256sum "$tmp" | awk '{print $1}')"
  if [[ -z "$expected" ]]; then
    echo "ERROR: CHECKSUMS entry missing for app/processor/models/classification/weights/best.pt" >&2
    rm -f "$tmp"
    exit 7
  fi
  if [[ "$expected" != "$actual" ]]; then
    echo "ERROR: checksum mismatch for classifier weights" >&2
    echo "expected=$expected" >&2
    echo "actual=$actual" >&2
    rm -f "$tmp"
    exit 8
  fi
  mv "$tmp" "$CLASSIFIER_DEST"
}

if [[ "$MODE" == "legacy" ]]; then
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    if [[ -s "$LEGACY_DEST" ]]; then
      echo "Legacy compatibility asset present: $LEGACY_DEST"
      exit 0
    fi
    echo "Legacy compatibility asset missing: $LEGACY_DEST" >&2
    exit 1
  fi
  fetch_legacy_single_stage
  exit 0
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  missing=0
  if [[ ! -s "$DETECTOR_DEST" ]]; then
    echo "Missing detector weights: $DETECTOR_DEST" >&2
    missing=1
  fi
  if [[ ! -s "$CLASSIFIER_DEST" ]]; then
    echo "Missing classifier weights: $CLASSIFIER_DEST" >&2
    missing=1
  fi
  if [[ "$missing" -ne 0 ]]; then
    exit 1
  fi
  echo "Two-stage weights present:"
  echo "  detector: $DETECTOR_DEST"
  echo "  classifier: $CLASSIFIER_DEST"
  exit 0
fi

ensure_two_stage_detector
ensure_two_stage_classifier

echo "Two-stage weights ready:"
echo "  detector:   $DETECTOR_DEST"
echo "  classifier: $CLASSIFIER_DEST"
echo "Validate rollout artifacts with: make validate-weights"
echo "Legacy compatibility asset is optional: use --legacy-single-stage for app/yolo11n.pt"

#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="$HERE/../app/processor/models"
mkdir -p "$DEST_DIR"
RELEASE_TAG="${1:-weights/v1}"
# asset name in the release
ASSET_NAME="${2:-yolo11n.pt}"
REPO="Gfermoto/BirdLense-Hub"

tmpfile="$(mktemp)"
echo "Fetching release ${RELEASE_TAG} asset ${ASSET_NAME} from ${REPO}..."
gh release download "$RELEASE_TAG" --repo "$REPO" --pattern "$ASSET_NAME" --dir "$(dirname "$tmpfile")"
downloaded="$(dirname "$tmpfile")/$ASSET_NAME"
if [ ! -f "$downloaded" ]; then
  # fallback: try name without path
  downloaded="$ASSET_NAME"
fi
if [ ! -f "$downloaded" ]; then
  echo "ERROR: asset not found after download attempt: $downloaded" >&2
  exit 2
fi

echo "Verifying checksum against CHECKSUMS..."
cd "$(git rev-parse --show-toplevel)"
grep -F "  app/yolo11n.pt" CHECKSUMS >/dev/null 2>&1 || { echo "CHECKSUMS entry missing"; exit 3; }
expected="$(grep -F \"  app/yolo11n.pt\" CHECKSUMS | awk '{print $1}')"
actual="$(sha256sum "$downloaded" | awk '{print $1}')"
if [ \"$expected\" != \"$actual\" ]; then
  echo \"Checksum mismatch: expected $expected got $actual\" >&2
  exit 4
fi

echo "Checksum OK. Moving to $DEST_DIR/$ASSET_NAME"
mv "$downloaded" "$DEST_DIR/$ASSET_NAME"
echo "Done."
#!/usr/bin/env bash
# Положить two_stage .pt в дерево processor/ (веса в .gitignore — не из git).
# Использование: из корня репозитория: ./scripts/fetch-processor-weights.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DET="${ROOT}/app/processor/models/detection/weights"
CLS="${ROOT}/app/processor/models/classification/weights"
ZIP="${ROOT}/app/processor/models/detection/nabirds_yolo11n_binary.zip"
HF_URL="https://huggingface.co/gfermoto/birdlense-birds-eu/resolve/main/best.pt"

mkdir -p "$DET" "$CLS"

if [[ ! -s "${DET}/best.pt" ]]; then
  echo "Распаковка бинарного детектора из ${ZIP}..."
  unzip -j -o "$ZIP" weights/best.pt -d "$DET/"
else
  echo "Уже есть ${DET}/best.pt — пропуск."
fi

if [[ ! -s "${CLS}/best.pt" ]]; then
  echo "Загрузка EU-классификатора (best.pt)..."
  curl -fsSL -o "${CLS}/best.pt" "$HF_URL"
else
  echo "Уже есть ${CLS}/best.pt — пропуск."
fi

echo "Готово: two_stage ожидает эти пути (или задайте свои в user_config.yaml)."

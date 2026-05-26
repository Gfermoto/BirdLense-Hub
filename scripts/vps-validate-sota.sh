#!/usr/bin/env bash
# VPS validation for SOTA-10..12 (+ optional SOTA-13 smoke) before enabling ReID gallery on prod.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Public DEPLOY_URL for browser/MCP; on VPS itself use loopback (hairpin to public IP often times out).
: "${DEPLOY_URL:?Set DEPLOY_URL (e.g. http://185.218.111.196:8085)}"
VERIFY_URL="${VPS_VERIFY_URL:-${DEPLOY_URL}}"
: "${SOTA_GOLDEN_CLIP_1819:?Set path to golden clip 1819 mp4 on VPS}"
SOTA_GOLDEN_CLIP_1816="${SOTA_GOLDEN_CLIP_1816:-$SOTA_GOLDEN_CLIP_1819}"
FRAME_STEP="${SOTA_BENCHMARK_FRAME_STEP:-6}"
MAX_RUNTIME="${SOTA_BENCHMARK_MAX_RUNTIME_SEC:-600}"
ARTIFACTS="${ARTIFACTS_DIR:-$REPO_ROOT/.artifacts/vps-sota}"

mkdir -p "$ARTIFACTS"
export SOTA_GOLDEN_CLIP_1819 SOTA_GOLDEN_CLIP_1816

echo "== BirdLense VPS SOTA validation =="
echo "DEPLOY_URL=$DEPLOY_URL"
echo "VERIFY_URL=$VERIFY_URL"
echo "CLIP_1819=$SOTA_GOLDEN_CLIP_1819"

echo "== 1/4 verify stack =="
make verify DEPLOY_URL="$VERIFY_URL"

echo "== 2/4 benchmark SOTA golden clips =="
make benchmark-sota \
  SKIP_IF_MISSING=0 \
  FRAME_STEP="$FRAME_STEP" \
  WRITE_REPORT="$ARTIFACTS/benchmark_sota.json"

echo "== 3/4 benchmark trackers (ByteTrack vs BoT-SORT) =="
make benchmark-trackers \
  CLIP="$SOTA_GOLDEN_CLIP_1819" \
  FRAME_STEP="$FRAME_STEP" \
  WRITE_REPORT="$ARTIFACTS/benchmark_trackers.json"

echo "== 4/4 ReID gallery API smoke (flags still off in yaml) =="
curl -sf "$VERIFY_URL/api/ui/health" >/dev/null
curl -sf "$VERIFY_URL/api/ui/reid/gallery/status" -H "Cookie: ${BIRDLENSE_SESSION_COOKIE:-}" || true

echo "Reports: $ARTIFACTS"
echo "PASS: review JSON reports, then enable processor.reid_gallery_* on prod if desired."

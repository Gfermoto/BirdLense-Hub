#!/usr/bin/env bash
# VPS validation for SOTA-10..12 (+ optional SOTA-13 smoke) before enabling ReID gallery on prod.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BIRDLENSE_CONTAINER="${BIRDLENSE_CONTAINER:-birdlense}"

# Public DEPLOY_URL for browser/MCP; on VPS itself use loopback (hairpin to public IP often times out).
: "${DEPLOY_URL:?Set DEPLOY_URL (e.g. http://185.218.111.196:8085)}"
VERIFY_URL="${VPS_VERIFY_URL:-${DEPLOY_URL}}"
: "${SOTA_GOLDEN_CLIP_1819:?Set path to golden clip 1819 mp4 on VPS}"
SOTA_GOLDEN_CLIP_1816="${SOTA_GOLDEN_CLIP_1816:-$SOTA_GOLDEN_CLIP_1819}"
FRAME_STEP="${SOTA_BENCHMARK_FRAME_STEP:-6}"
MAX_RUNTIME="${SOTA_BENCHMARK_MAX_RUNTIME_SEC:-600}"
ARTIFACTS="${ARTIFACTS_DIR:-$REPO_ROOT/.artifacts/vps-sota}"

mkdir -p "$ARTIFACTS"

# Map host path under app/ → /app/... inside the running Hub container.
to_container_clip() {
  local host_path="$1"
  if [[ "$host_path" == /app/* ]]; then
    printf '%s\n' "$host_path"
    return
  fi
  if [[ "$host_path" == "$REPO_ROOT/app/"* ]]; then
    printf '/app/%s\n' "${host_path#"$REPO_ROOT/app/"}"
    return
  fi
  echo "FAIL: clip must live under $REPO_ROOT/app/ (got $host_path)" >&2
  exit 1
}

CLIP_1819_C="$(to_container_clip "$SOTA_GOLDEN_CLIP_1819")"
CLIP_1816_C="$(to_container_clip "$SOTA_GOLDEN_CLIP_1816")"

docker_benchmark_setup() {
  docker cp "$REPO_ROOT/scripts/benchmark_sota.py" "$BIRDLENSE_CONTAINER:/tmp/benchmark_sota.py"
  docker cp "$REPO_ROOT/scripts/benchmark_trackers.py" "$BIRDLENSE_CONTAINER:/tmp/benchmark_trackers.py"
  docker cp "$REPO_ROOT/scripts/fetch_golden_clips.py" "$BIRDLENSE_CONTAINER:/tmp/fetch_golden_clips.py"
  docker exec "$BIRDLENSE_CONTAINER" mkdir -p /benchmarks
  docker cp "$REPO_ROOT/benchmarks/." "$BIRDLENSE_CONTAINER:/benchmarks/"
}

echo "== BirdLense VPS SOTA validation =="
echo "DEPLOY_URL=$DEPLOY_URL"
echo "VERIFY_URL=$VERIFY_URL"
echo "CLIP_1819(host)=$SOTA_GOLDEN_CLIP_1819"
echo "CLIP_1819(container)=$CLIP_1819_C"

echo "== 1/4 verify stack =="
make verify DEPLOY_URL="$VERIFY_URL"

echo "== 2/4 benchmark SOTA golden clips (inside $BIRDLENSE_CONTAINER) =="
docker_benchmark_setup
docker exec \
  -e SOTA_GOLDEN_CLIP_1816="$CLIP_1816_C" \
  -e SOTA_GOLDEN_CLIP_1819="$CLIP_1819_C" \
  -e SOTA_BENCHMARK_FRAME_STEP="$FRAME_STEP" \
  -e SOTA_BENCHMARK_MAX_RUNTIME_SEC="$MAX_RUNTIME" \
  "$BIRDLENSE_CONTAINER" \
  python /tmp/benchmark_sota.py \
    --manifest /benchmarks/golden_clips.json \
    --baseline /benchmarks/golden_baseline.json \
    --db /app/data/db/birdlense.db \
    --clip-1816 "$CLIP_1816_C" \
    --clip-1819 "$CLIP_1819_C" \
    --frame-step "$FRAME_STEP" \
    --max-runtime-sec "$MAX_RUNTIME" \
    --write-report /tmp/benchmark_sota_report.json
docker cp "$BIRDLENSE_CONTAINER:/tmp/benchmark_sota_report.json" "$ARTIFACTS/benchmark_sota.json"

echo "== 3/4 benchmark trackers (ByteTrack vs BoT-SORT) =="
docker exec \
  -e SOTA_BENCHMARK_FRAME_STEP="$FRAME_STEP" \
  -e SOTA_BENCHMARK_MAX_RUNTIME_SEC="$MAX_RUNTIME" \
  "$BIRDLENSE_CONTAINER" \
  python /tmp/benchmark_trackers.py \
    --clip "$CLIP_1819_C" \
    --presets "${TRACKER_PRESETS:-bytetrack_birdlense,botsort_birdlense}" \
    --frame-step "$FRAME_STEP" \
    --write-report /tmp/benchmark_trackers_report.json
docker cp "$BIRDLENSE_CONTAINER:/tmp/benchmark_trackers_report.json" "$ARTIFACTS/benchmark_trackers.json"

echo "== 4/4 ReID gallery API smoke (flags still off in yaml) =="
curl -sf "$VERIFY_URL/api/ui/health" >/dev/null
curl -sf "$VERIFY_URL/api/ui/reid/gallery/status" -H "Cookie: ${BIRDLENSE_SESSION_COOKIE:-}" || true

echo "Reports: $ARTIFACTS"
echo "PASS: review JSON reports, then enable processor.reid_gallery_* on prod if desired."

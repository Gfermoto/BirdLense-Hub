#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-${DEPLOY_URL:-http://127.0.0.1:8085}}"
TIMEOUT_SEC="${TIMEOUT_SEC:-20}"
REQUIRE_STRICT_QUALITY_READY="${REQUIRE_STRICT_QUALITY_READY:-0}"
MIN_SPECIES_MATCHED="${MIN_SPECIES_MATCHED:-520}"
EXPECTED_ALLOWLIST_TOTAL="${EXPECTED_ALLOWLIST_TOTAL:-526}"
REQUIRE_COMPLETE_CARDS="${REQUIRE_COMPLETE_CARDS:-0}"
MAX_ALL_CAPS_MATCHED="${MAX_ALL_CAPS_MATCHED:-0}"
SKIP_TRIGGER_AUDIT="${SKIP_TRIGGER_AUDIT:-0}"
SKIP_YOLO_GOLDEN="${SKIP_YOLO_GOLDEN:-0}"
SKIP_BBOX_PARITY="${SKIP_BBOX_PARITY:-0}"
AUDIT_DAYS="${AUDIT_DAYS:-1}"
AUDIT_CAMERAS="${AUDIT_CAMERAS:-BirdBox,Forest}"
FAIL_ON_PARITY_HOTSPOT="${FAIL_ON_PARITY_HOTSPOT:-0}"

usage() {
  cat <<'EOF'
Usage: scripts/check-quality-gates.sh [--base-url URL]

Quality gate for production smoke:
  - /api/ui/status, /api/ui/readiness
  - /api/ui/system/domain-health
  - /api/ui/system/species-registry/repair-cards/status
  - optional trigger-detector-audit on VPS host

Environment:
  BASE_URL / DEPLOY_URL               API base URL
  BIRDLENSE_UI_API_KEY / MCP_TOKEN    auth for protected API
  REQUIRE_STRICT_QUALITY_READY        1 to fail when strict_quality_ready=false
  MIN_SPECIES_MATCHED                 default 520
  EXPECTED_ALLOWLIST_TOTAL            default 526
  SKIP_TRIGGER_AUDIT                  default 0
  AUDIT_DAYS                          default 1
  AUDIT_CAMERAS                       default BirdBox,Forest
  FAIL_ON_PARITY_HOTSPOT              1 to fail when parity hotspots > 0
  SKIP_YOLO_GOLDEN                    1 to skip yolo golden clips gate (default 0)
  YOLO_GOLDEN_CLIP_1819               mp4 path for regen gate (optional)
  BIRDLENSE_DB                        sqlite path for video 1819 session metrics
  SKIP_BBOX_PARITY                    1 to skip validate_bbox_parity.sh (default 0)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
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
done

curl_args=("-sS" "--max-time" "${TIMEOUT_SEC}")
if [[ -n "${BIRDLENSE_UI_API_KEY:-}" ]]; then
  curl_args+=("-H" "X-Birdlense-Api-Key: ${BIRDLENSE_UI_API_KEY}")
elif [[ -n "${MCP_TOKEN:-}" ]]; then
  curl_args+=("-H" "Authorization: Bearer ${MCP_TOKEN}")
fi

status_json="$(curl "${curl_args[@]}" "${BASE_URL}/api/ui/status")"
readiness_json="$(curl "${curl_args[@]}" "${BASE_URL}/api/ui/readiness")"
domain_json="$(curl "${curl_args[@]}" "${BASE_URL}/api/ui/system/domain-health")"
coverage_json="$(curl "${curl_args[@]}" "${BASE_URL}/api/ui/system/species-registry/repair-cards/status")"

export STATUS_JSON="$status_json"
export READINESS_JSON="$readiness_json"
export DOMAIN_JSON="$domain_json"
export COVERAGE_JSON="$coverage_json"
export REQUIRE_STRICT_QUALITY_READY FAIL_ON_PARITY_HOTSPOT
export MIN_SPECIES_MATCHED EXPECTED_ALLOWLIST_TOTAL REQUIRE_COMPLETE_CARDS MAX_ALL_CAPS_MATCHED

python3 - <<'PY'
import json
import os
import sys

status = json.loads(os.environ["STATUS_JSON"])
readiness = json.loads(os.environ["READINESS_JSON"])
domain = json.loads(os.environ["DOMAIN_JSON"])
coverage = json.loads(os.environ["COVERAGE_JSON"])

require_strict = os.environ.get("REQUIRE_STRICT_QUALITY_READY", "0") == "1"
fail_parity_hotspot = os.environ.get("FAIL_ON_PARITY_HOTSPOT", "0") == "1"
min_species_matched = int(os.environ.get("MIN_SPECIES_MATCHED", "520"))
expected_allow = int(os.environ.get("EXPECTED_ALLOWLIST_TOTAL", "526"))
require_complete = os.environ.get("REQUIRE_COMPLETE_CARDS", "0") == "1"
max_all_caps = int(os.environ.get("MAX_ALL_CAPS_MATCHED", "0"))

errors: list[str] = []
warnings: list[str] = []

for comp in ("processor", "video", "web"):
    if str(status.get(comp) or "").lower() != "ok":
        errors.append(f"status.{comp} != ok ({status.get(comp)!r})")
if "opencv" not in [str(x) for x in (status.get("active_triggers") or [])]:
    warnings.append(f"active_triggers={status.get('active_triggers')!r}")

if not bool(readiness.get("ready")):
    errors.append("readiness.ready=false")

metrics = (domain.get("metrics") or {})
strict_quality = (domain.get("strict_quality") or {})
if require_strict and not bool(strict_quality.get("strict_quality_ready")):
    errors.append("domain.strict_quality.strict_quality_ready=false")
hotspots = int(metrics.get("parity_hotspot_count_24h") or 0)
if hotspots > 0:
    msg = f"parity_hotspot_count_24h={hotspots}"
    (errors if fail_parity_hotspot else warnings).append(msg)

cov = (coverage.get("coverage_now") or {})
allow_total = int(cov.get("allowlist_total") or 0)
species_matched = int(cov.get("species_matched") or 0)
if allow_total < expected_allow:
    errors.append(f"allowlist_total={allow_total} < {expected_allow}")
if species_matched < min_species_matched:
    errors.append(f"species_matched={species_matched} < {min_species_matched}")
complete_cards = int(cov.get("complete_cards") or 0)
missing_image = int(cov.get("missing_image_lines") or 0)
missing_desc = int(cov.get("missing_description_lines") or 0)
all_caps = int(cov.get("all_caps_matched_species") or 0)
if require_complete and complete_cards < allow_total:
    errors.append(
        f"complete_cards={complete_cards} < allowlist_total={allow_total} "
        f"(missing_image_lines={missing_image}, missing_description_lines={missing_desc})"
    )
if all_caps > max_all_caps:
    errors.append(f"all_caps_matched_species={all_caps} > {max_all_caps}")

print("quality-gate: status processor/video/web =", status.get("processor"), status.get("video"), status.get("web"))
print("quality-gate: readiness.ready =", readiness.get("ready"))
print("quality-gate: strict_quality_ready =", strict_quality.get("strict_quality_ready"))
print("quality-gate: parity_hotspot_count_24h =", hotspots)
print("quality-gate: coverage allowlist_total/species_matched =", allow_total, species_matched)
print(
    "quality-gate: complete_cards/missing_image/missing_desc/all_caps =",
    complete_cards,
    missing_image,
    missing_desc,
    all_caps,
)
if warnings:
    print("quality-gate: WARN")
    for w in warnings:
        print(" -", w)
if errors:
    print("quality-gate: FAIL")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("quality-gate: PASS")
PY

if [[ "${SKIP_YOLO_GOLDEN}" != "1" ]]; then
  if python3 "${BASH_SOURCE%/*}/yolo-golden-clips-gate.py"; then
    echo "quality-gate: yolo-golden PASS"
  else
    echo "quality-gate: yolo-golden FAIL" >&2
    exit 1
  fi
fi

if [[ "${SKIP_BBOX_PARITY}" != "1" ]]; then
  if python3 "${BASH_SOURCE%/*}/validate_bbox_parity.py"; then
    echo "quality-gate: bbox-parity PASS"
  else
    echo "quality-gate: bbox-parity FAIL" >&2
    exit 1
  fi
fi

if [[ "${SKIP_TRIGGER_AUDIT}" != "1" ]] && [[ -n "${DEPLOY_HOST:-}" ]]; then
  ssh_port="${DEPLOY_SSH_PORT:-22}"
  remote_dir="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
  audit_raw="$(ssh -p "${ssh_port}" "${DEPLOY_HOST}" \
    "python3 ${remote_dir}/scripts/trigger_detector_audit.py --days ${AUDIT_DAYS} --cameras '${AUDIT_CAMERAS}' --db-path ${remote_dir}/app/data/db/birdlense.db")"
  export AUDIT_JSON="$audit_raw"
  python3 - <<'PY'
import json
import os
import sys

audit = json.loads(os.environ["AUDIT_JSON"])
cameras = audit.get("cameras") or {}
bad = []
for cam, block in cameras.items():
    dominant = str(block.get("dominant_miss_reason") or "none")
    if dominant not in ("none", "trigger_or_schedule"):
        bad.append(f"{cam}:{dominant}")
print("quality-gate: trigger-audit cameras =", ",".join(sorted(cameras.keys())) if cameras else "none")
if bad:
    print("quality-gate: FAIL trigger-audit dominant_miss_reason:", ", ".join(bad))
    sys.exit(1)
print("quality-gate: trigger-audit PASS")
PY
fi

#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8085}"
TIMEOUT_SEC="${TIMEOUT_SEC:-15}"
MAX_HEARTBEAT_AGE_SECONDS="${MAX_HEARTBEAT_AGE_SECONDS:-240}"
REQUIRE_HEARTBEAT_STALE_ZERO="${REQUIRE_HEARTBEAT_STALE_ZERO:-1}"
MAX_HTTP_OVER_1000MS_RATIO="${MAX_HTTP_OVER_1000MS_RATIO:-0.20}"
MIN_HTTP_SAMPLE_COUNT="${MIN_HTTP_SAMPLE_COUNT:-20}"

usage() {
  cat <<'EOF'
Usage: scripts/check-runtime-sli.sh [--base-url URL]

Runtime SLI check (Prometheus metrics):
  - processor heartbeat stale flag and age
  - HTTP request latency distribution (share >1000ms)

Environment overrides:
  BASE_URL                        Default: http://127.0.0.1:8085
  TIMEOUT_SEC                     Default: 15
  MAX_HEARTBEAT_AGE_SECONDS       Default: 240
  REQUIRE_HEARTBEAT_STALE_ZERO    Default: 1 (require stale=0)
  MAX_HTTP_OVER_1000MS_RATIO      Default: 0.20
  MIN_HTTP_SAMPLE_COUNT           Default: 20
  BIRDLENSE_UI_API_KEY / MCP_TOKEN for auth-protected metrics endpoints.
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

curl_args=("-sS" "-L" "--max-time" "${TIMEOUT_SEC}")
if [[ -n "${BIRDLENSE_UI_API_KEY:-}" ]]; then
  curl_args+=("-H" "X-Birdlense-Api-Key: ${BIRDLENSE_UI_API_KEY}")
elif [[ -n "${MCP_TOKEN:-}" ]]; then
  curl_args+=("-H" "Authorization: Bearer ${MCP_TOKEN}")
fi

metrics_body="$(curl "${curl_args[@]}" "${BASE_URL}/metrics")" || {
  echo "runtime-sli: FAIL (${BASE_URL}/metrics unreachable)" >&2
  exit 1
}

export METRICS_BODY="${metrics_body}"
export MAX_HEARTBEAT_AGE_SECONDS REQUIRE_HEARTBEAT_STALE_ZERO
export MAX_HTTP_OVER_1000MS_RATIO MIN_HTTP_SAMPLE_COUNT

python3 - <<'PY'
import os
import re
import sys

body = os.environ.get("METRICS_BODY", "")
max_hb_age = float(os.environ.get("MAX_HEARTBEAT_AGE_SECONDS", "240"))
require_stale_zero = str(os.environ.get("REQUIRE_HEARTBEAT_STALE_ZERO", "1")).strip() == "1"
max_over_1000_ratio = float(os.environ.get("MAX_HTTP_OVER_1000MS_RATIO", "0.20"))
min_http_samples = int(os.environ.get("MIN_HTTP_SAMPLE_COUNT", "20"))

errors: list[str] = []

hb_age = None
hb_stale = None
http_over_1000 = 0.0
http_total = 0.0

for raw in body.splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    m_age = re.match(r"^birdlense_processor_heartbeat_age_seconds\s+([0-9.eE+-]+)$", line)
    if m_age:
        try:
            hb_age = float(m_age.group(1))
        except ValueError:
            pass
        continue
    m_stale = re.match(r'^birdlense_processor_heartbeat_stale\{[^}]*\}\s+([0-9.eE+-]+)$', line)
    if m_stale:
        try:
            hb_stale = float(m_stale.group(1))
        except ValueError:
            pass
        continue
    m_b = re.match(
        r'^birdlense_http_request_duration_ms_bucket\{[^}]*le="([^"]+)"[^}]*\}\s+([0-9.eE+-]+)$',
        line,
    )
    if m_b:
        le = m_b.group(1)
        try:
            val = float(m_b.group(2))
        except ValueError:
            continue
        if le == "1000":
            http_over_1000 = max(0.0, val)
        elif le == "+Inf":
            http_total = max(0.0, val)

if hb_age is None:
    errors.append("missing birdlense_processor_heartbeat_age_seconds")
elif hb_age < 0:
    errors.append(f"heartbeat age invalid: {hb_age}")
elif hb_age > max_hb_age:
    errors.append(f"heartbeat age {hb_age:.3f}s > {max_hb_age:.3f}s")

if hb_stale is None:
    errors.append("missing birdlense_processor_heartbeat_stale")
elif require_stale_zero and hb_stale != 0.0:
    errors.append(f"heartbeat stale flag is {hb_stale} (required 0)")

http_ratio = None
if http_total >= float(min_http_samples):
    slow = max(0.0, http_total - http_over_1000)
    http_ratio = (slow / http_total) if http_total > 0 else 0.0
    if http_ratio > max_over_1000_ratio:
        errors.append(
            f"http slow ratio {http_ratio:.4f} > {max_over_1000_ratio:.4f} "
            f"(samples={int(http_total)})"
        )

status = "PASS" if not errors else "FAIL"
parts = [f"heartbeat_age={hb_age}", f"heartbeat_stale={hb_stale}"]
if http_ratio is None:
    parts.append(f"http_slow_ratio=skip(samples={int(http_total)})")
else:
    parts.append(f"http_slow_ratio={http_ratio:.4f}(samples={int(http_total)})")
print(f"runtime-sli: {status} " + " ".join(parts))
if errors:
    for err in errors:
        print(f"runtime-sli: ERROR {err}", file=sys.stderr)
    sys.exit(1)
PY

#!/usr/bin/env bash
# Nightly/weekly SOTA governance cycle (#582): outcome + reality-check + pipeline profile.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODE="${GOVERNANCE_MODE:-nightly}"  # nightly|weekly
OUTCOME_DB="${OUTCOME_DB_PATH:-app/data/db/birdlense.db}"
LOOKBACK_HOURS="${OUTCOME_LOOKBACK_HOURS:-24}"
FAIL_ON_BLOCKED="${SOTA_FAIL_ON_BLOCKED:-1}"
MANIFEST_JSON="docs/reports/governance/governance_cycle_latest.json"
MANIFEST_MD="docs/reports/governance/governance_cycle_latest.md"

mkdir -p docs/reports/governance docs/reports/perf docs/reports/quality_outcome docs/reports/sota_reality

step_ok=()
step_fail=()

_run_step() {
  local name="$1"
  shift
  echo "governance-cycle: ${name}..."
  if "$@"; then
    step_ok+=("${name}")
    return 0
  fi
  step_fail+=("${name}")
  return 1
}

overall_ok=true

if [[ -f "${OUTCOME_DB}" ]]; then
  _run_step "quality_outcome" python3 ./scripts/report_quality_outcome_metrics.py \
    --db-path "${OUTCOME_DB}" \
    --data-source "local:${OUTCOME_DB}" \
    --lookback-hours "${LOOKBACK_HOURS}" \
    --max-blind-rate "${OUTCOME_MAX_BLIND_RATE:-0.30}" \
    --min-tracks-coverage "${OUTCOME_MIN_TRACKS_COVERAGE:-0.50}" \
    --max-empty-bbox-rate "${OUTCOME_MAX_EMPTY_BBOX_RATE:-0.20}" \
    --min-yolo-frames-with-tracks "${OUTCOME_MIN_YOLO_FRAMES_WITH_TRACKS:-1}" \
    --out-json docs/reports/quality_outcome/quality_outcome_metrics_latest.json \
    --out-md docs/reports/quality_outcome/quality_outcome_metrics_latest.md \
  || overall_ok=false

  _run_step "runtime_pipeline_profile" python3 ./scripts/report_runtime_pipeline_profile.py \
    --db-path "${OUTCOME_DB}" \
    --lookback-hours "${LOOKBACK_HOURS}" \
    --first-bbox-warn-s "${FIRST_BBOX_WARN_S:-5}" \
    --finalize-warn-ms "${FINALIZE_WARN_MS:-5000}" \
    --out-json docs/reports/perf/runtime_pipeline_profile_latest.json \
    --out-md docs/reports/perf/runtime_pipeline_profile_latest.md \
  || overall_ok=false
else
  echo "governance-cycle: skip quality_outcome + runtime_pipeline_profile (no db at ${OUTCOME_DB})"
fi

_fail_flag=""
if [[ "${FAIL_ON_BLOCKED}" == "1" ]]; then
  _fail_flag="--fail-on-blocked"
fi
_run_step "sota_reality_check" python3 ./scripts/report_sota_reality_check.py ${_fail_flag} \
|| overall_ok=false

if [[ "${MODE}" == "weekly" ]]; then
  _run_step "review_board" python3 ./scripts/verify_review_board_governance.py \
    --out-json docs/reports/governance/review_board_latest.json \
    --out-md docs/reports/governance/review_board_latest.md \
  || overall_ok=false
  _run_step "domain_finetune_loop" python3 ./scripts/verify_domain_finetune_loop.py \
    --contract docs/reports/domain_finetune/domain_finetune_contract.json \
    --out-json docs/reports/domain_finetune/domain_finetune_loop_latest.json \
    --out-md docs/reports/domain_finetune/domain_finetune_loop_latest.md \
  || overall_ok=false
fi

python3 - <<'PY' "${MANIFEST_JSON}" "${MANIFEST_MD}" "${MODE}" "${overall_ok}" "${step_ok[*]:-}" "${step_fail[*]:-}"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_json, out_md, mode, overall_ok, ok_steps, fail_steps = sys.argv[1:7]
ok_list = [s for s in ok_steps.split(" ") if s]
fail_list = [s for s in fail_steps.split(" ") if s]
report = {
    "schema": "governance_cycle_report@v1",
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "mode": mode,
    "steps_ok": ok_list,
    "steps_failed": fail_list,
    "acceptance_blocked": bool(fail_list) or overall_ok != "true",
    "ok": overall_ok == "true" and not fail_list,
    "artifacts": {
        "quality_outcome": "docs/reports/quality_outcome/quality_outcome_metrics_latest.json",
        "runtime_pipeline_profile": "docs/reports/perf/runtime_pipeline_profile_latest.json",
        "sota_reality": "docs/reports/sota_reality/sota_reality_check_latest.json",
    },
}
Path(out_json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
lines = [
    "# SOTA Governance Cycle",
    "",
    f"- generated_at: `{report['generated_at']}`",
    f"- mode: `{mode}`",
    f"- ok: `{report['ok']}`",
    f"- acceptance_blocked: `{report['acceptance_blocked']}`",
    "",
    "## Steps OK",
    "",
    f"`{ok_list}`",
    "",
    "## Steps Failed",
    "",
    f"`{fail_list}`",
]
Path(out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

if [[ "${overall_ok}" != "true" ]]; then
  echo "governance-cycle: FAIL (see ${MANIFEST_JSON})" >&2
  exit 1
fi

echo "governance-cycle: OK (${MODE})"

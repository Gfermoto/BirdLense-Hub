# Decision Engine Contract Runbook

## Scope

Runbook for `SOTA-2-01` contract around:

- `detect -> quality -> fusion -> persist`
- `FUSION_NO_ACCEPTED` root-cause visibility
- sticky/stale crop guardrails
- species arbitration traceability

## Daily evidence set

Run from repository root:

```bash
python3 scripts/report_fusion_reject_reason_dashboard.py --days 14
python3 scripts/report_decision_engine_parity_ledger.py --days 14
python3 scripts/parity_daily_hold.py --base-url "${DEPLOY_URL}"
```

Artifacts:

- `docs/reports/reject_reason_dashboard/reject_reason_dashboard_latest.json`
- `docs/reports/reject_reason_dashboard/reject_reason_dashboard_latest.md`
- `docs/reports/decision_engine_parity_ledger/decision_engine_parity_ledger_latest.json`
- `docs/reports/decision_engine_parity_ledger/decision_engine_parity_ledger_latest.md`
- `docs/reports/parity_daily_hold/parity_daily_hold_*.json`
- `docs/reports/parity_daily_hold/parity_daily_hold_*.md`

## Golden pack regression

```bash
python3 -m pytest \
  app/processor/tests/test_decision_engine_golden_pack.py \
  app/processor/tests/test_decision_trace_builder.py \
  app/processor/tests/test_track_geometry.py \
  app/processor/tests/test_opencv_live_overlay.py \
  app/processor/tests/test_recording_no_detection_log.py -q
```

Expected: all green.

## Rollback / mitigation

If reject share spikes or persist drops unexpectedly:

1. Switch to last known-good commit on `dev` and redeploy.
2. Re-run `make verify` and `scripts/parity_daily_hold.py`.
3. Check these indicators:
   - `decision_engine_parity_ledger`: `FUSION_NO_ACCEPTED` share
   - `reject_reason_dashboard`: top reason classes
   - `recording_session_summary.rejected_reason_counts`
4. If `rejected_static_pinned_track` dominates:
   - temporarily relax static filter thresholds in `user_config.yaml`
   - keep `test_track_geometry.py` and `test_opencv_live_overlay.py` green
5. If `rejected_short_track` dominates:
   - lower `processor.min_track_duration` cautiously
   - monitor `decision_engine_parity_ledger` after deploy
6. If `low_confidence` dominates:
   - review detector/classifier thresholds and recent model changes
   - validate on golden pack before rollout

Mitigation target: restore previous `quality_to_persist_ratio` and keep
`verify-stack`/runtime gates green before further tuning.

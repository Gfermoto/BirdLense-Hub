# Runbook Coverage Gate

## Goal

`SOTA-4-03`: guarantee runbook coverage for top incident classes and weekly validation cadence.

## Contract

Gate verifies:

- all incidents from catalog have existing runbook links
- validation cadence is active (`>=1` verification cycle per 7 days)

## Commands

```bash
make runbook-coverage-gate
```

Manual:

```bash
python3 scripts/verify_runbook_coverage.py \
  --catalog docs/reports/runbook_coverage/incident_catalog.json \
  --history docs/reports/runbook_coverage/validation_history.jsonl \
  --record-validation
```

## Deploy integration

`scripts/public/deploy.sh` runs this gate at step `0.51`.

- fail blocks deploy
- temporary bypass only via `BIRDLENSE_SKIP_RUNBOOK_COVERAGE_GATE=1`

## Artifacts

- `docs/reports/runbook_coverage/incident_catalog.json`
- `docs/reports/runbook_coverage/validation_history.jsonl`
- `docs/reports/runbook_coverage/runbook_coverage_latest.json`
- `docs/reports/runbook_coverage/runbook_coverage_latest.md`

## Rollback / mitigation

1. Keep current release unchanged.
2. Fix missing runbook links in incident catalog.
3. Run one validation cycle and re-run gate.
4. Confirm cadence and coverage in `runbook_coverage_latest.json`.

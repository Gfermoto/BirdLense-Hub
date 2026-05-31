# ML Drift Trigger Gate

## Goal

`SOTA-2-03`: detect production ML drift and enforce retrain-trigger policy.

## Contract

Gate compares current observation aggregates vs baseline:

- `binary_positive_rate`
- `mean_confidence`
- `species_entropy`

If any metric delta exceeds threshold and observation count is sufficient, retrain is required.
Deploy is blocked unless explicit override reason is provided.

## Commands

```bash
make ml-drift-trigger-gate
```

Manual:

```bash
python3 scripts/report_ml_drift_triggers.py \
  --baseline docs/reports/ml_drift/ml_drift_baseline.json \
  --observations docs/reports/ml_drift/ml_observations.jsonl
```

## Deploy integration

`scripts/public/deploy.sh` runs this gate at step `0.54`.

- fail blocks deploy
- temporary bypass: `BIRDLENSE_ML_DRIFT_OVERRIDE_REASON=\"...\"`
- hard skip (emergency only): `BIRDLENSE_SKIP_ML_DRIFT_GATE=1`

## Artifacts

- `docs/reports/ml_drift/ml_drift_baseline.json`
- `docs/reports/ml_drift/ml_observations.jsonl`
- `docs/reports/ml_drift/ml_drift_trigger_latest.json`
- `docs/reports/ml_drift/ml_drift_trigger_latest.md`

## Rollback / mitigation

1. Freeze release and open retrain incident.
2. Rebuild/refresh model candidate on latest dataset window.
3. Run golden-set and contract gates for candidate.
4. Re-run drift gate; proceed only after `ok=true` or explicit emergency override.

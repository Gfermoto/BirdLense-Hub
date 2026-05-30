# Golden Set Mandatory Gate

## Purpose

`SOTA-2-02`: model/config changes must pass golden-set checks before deploy.

Gate is enforced in `scripts/public/deploy.sh` (step `0.45`).

## Trigger scope

Gate runs only when diff contains at least one path from the contract scope:

- `app/processor/models/**`
- `app/processor/src/detection_*.py`
- `app/processor/src/decision_maker.py`
- `app/processor/src/detection_quality.py`
- `app/processor/src/detection_fusion.py`
- `app/app_config/default_config.yaml`
- `app/app_config/user_config*.yaml`

## Commands executed by gate

```bash
make validate-pipeline-golden
python3 scripts/stress_test_offline.py --no-yolo
```

Output artifacts:

- `docs/reports/golden_set_gate/golden_set_gate_latest.json`
- `docs/reports/golden_set_gate/golden_set_gate_latest.md`

## Manual run

```bash
python3 scripts/enforce_golden_set_gate.py --enforce
```

Optional refs:

```bash
python3 scripts/enforce_golden_set_gate.py \
  --base-ref HEAD~1 \
  --head-ref HEAD \
  --enforce
```

## Rollback / mitigation

If gate fails:

1. Do not deploy.
2. Inspect gate artifact (`golden_set_gate_latest.json`) and failing command tail.
3. Reproduce locally:
   - `make validate-pipeline-golden`
   - `python3 scripts/stress_test_offline.py --no-yolo`
4. Revert model/config delta or restore last known-good snapshot.
5. Re-run gate and deploy only after `ok=true`.

Temporary bypass (incident-only): `BIRDLENSE_SKIP_GOLDEN_SET_GATE=1`.
Use only with documented incident ticket and rollback plan.

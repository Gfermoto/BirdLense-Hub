# Baseline Snapshot Contract

## Goal

`SOTA-0-01`: reproducible baseline snapshot as single source of truth.

Contract:

- collect parity snapshot (`parity_daily_hold@v1`)
- run two sequential captures
- verify delta on key aggregates `<= 1%`

## Commands

One-shot local/remote baseline contract:

```bash
make baseline-snapshot-contract
```

Manual sequence:

```bash
python3 scripts/parity_daily_hold.py --base-url "${DEPLOY_URL}"
python3 scripts/parity_daily_hold.py --base-url "${DEPLOY_URL}"
python3 scripts/verify_baseline_snapshot_contract.py \
  --snapshot-dir docs/reports/parity_daily_hold
```

## Artifacts

- `docs/reports/parity_daily_hold/parity_daily_hold_*.json`
- `docs/reports/parity_daily_hold/parity_daily_hold_*.md`
- `docs/reports/baseline_snapshot_contract/baseline_snapshot_contract_latest.json`
- `docs/reports/baseline_snapshot_contract/baseline_snapshot_contract_latest.md`

## Rollback / mitigation

If contract check fails:

1. Stop deploy and keep current production image.
2. Inspect diff report in `baseline_snapshot_contract_latest.json`.
3. Check whether config fingerprint changed unexpectedly.
4. Re-run `make verify` and `make baseline-snapshot-contract`.
5. If mismatch persists, revert recent runtime/config changes and rerun.

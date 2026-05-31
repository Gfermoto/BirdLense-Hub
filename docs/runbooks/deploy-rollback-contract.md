# Deploy Rollback Contract

## Goal

`SOTA-5-02`: ensure deploy path is idempotent and rollback path is reproducible.

## Contract

- repeated deploy of same commit must succeed (`pass_rate=1.0`)
- rollback readiness checks must pass:
  - `scripts/restore-config.sh` exists
  - deploy keeps `.bak.deploy-*` backup for `user_config.yaml`
  - deploy script contains restore guidance

## Commands

```bash
python3 scripts/report_deploy_contract.py --record-run --status success --skip-report
python3 scripts/report_deploy_contract.py
```

## Artifacts

- `docs/reports/deploy_contract/deploy_runs.jsonl`
- `docs/reports/deploy_contract/deploy_contract_latest.json`
- `docs/reports/deploy_contract/deploy_contract_latest.md`

## Rollback / mitigation

1. If deploy regresses, stop rollout and keep current container image.
2. Restore config via `make restore-config` or backup `.bak.deploy-*` snapshot.
3. Re-run `make verify` and `python3 scripts/report_deploy_contract.py`.
4. For failed idempotency sample, fix root cause and repeat deploy on same commit.

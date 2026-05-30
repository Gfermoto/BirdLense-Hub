# Health/Readiness Contract

## Goal

`SOTA-1-01`: remove false-green states and enforce consistency across:

- `/api/ui/health`
- `/api/ui/readiness`
- `/api/ui/status`

Contract rule:

- if `health=ok` while `readiness` is not ready or `status.processor!=ok`, treat as false-green and fail gate

## Commands

```bash
make health-readiness-contract
```

Manual:

```bash
python3 scripts/verify_health_readiness_contract.py --base-url "${DEPLOY_URL}"
```

## Deploy integration

`scripts/public/deploy.sh` runs gate at step `0.47`.

- failure blocks deploy
- temporary bypass only via `BIRDLENSE_SKIP_HEALTH_READINESS_GATE=1`

## Artifacts

- `docs/reports/health_readiness_contract/health_readiness_contract_latest.json`
- `docs/reports/health_readiness_contract/health_readiness_contract_latest.md`

## Rollback / mitigation

1. Keep current production release.
2. Check `health_readiness_contract_latest.json` and identify failed check.
3. Run `make verify` and inspect:
   - `/api/ui/readiness` (`processor_heartbeat`, `database`, `cache_backend`)
   - `/api/ui/status` (`web`, `processor`)
4. Fix failing contour and rerun `make health-readiness-contract`.

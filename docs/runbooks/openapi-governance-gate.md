# OpenAPI Governance Gate

## Goal

`SOTA-1-03`: enforce automatic OpenAPI governance via Spectral and CI.

## Contract

Gate verifies:

- `.spectral.yaml` ruleset exists
- `app/web/openapi.yaml` passes Spectral lint

## Commands

```bash
make openapi-governance-gate
```

Manual:

```bash
python3 scripts/verify_openapi_governance.py
```

## CI integration

`.github/workflows/ci-pr.yml` includes `OpenAPI Spectral governance lint` step.

## Artifacts

- `docs/reports/openapi_governance/openapi_governance_latest.json`
- `docs/reports/openapi_governance/openapi_governance_latest.md`

## Rollback / mitigation

1. Fix violations in `app/web/openapi.yaml` or align ruleset in `.spectral.yaml`.
2. Re-run `make openapi-governance-gate`.
3. Re-run full CI contract checks before merge.

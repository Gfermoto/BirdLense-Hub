# Integration Contract Registry Gate

## Goal

`SOTA-6-01`: keep MQTT/edge integration contracts in a formal, validated registry.

## Contract

Gate verifies:

- registry contains all required integration IDs
- registry size meets minimum active integrations threshold
- contract docs for each integration exist
- HTTP integration endpoints are present in OpenAPI contract
- channel/auth modes are valid and controlled

## Commands

```bash
make integration-contract-registry-gate
```

Manual:

```bash
python3 scripts/verify_integration_contract_registry.py \
  --registry docs/reports/integrations/integration_contract_registry.json
```

## Integrations

- CI docs job: `Integration contract registry gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.61`.

## Artifacts

- `docs/reports/integrations/integration_contract_registry.json`
- `docs/reports/integrations/integration_contract_registry_latest.json`
- `docs/reports/integrations/integration_contract_registry_latest.md`

## Rollback / mitigation

1. Add missing required integration IDs to registry.
2. Fix missing docs or endpoint references.
3. Re-run `make integration-contract-registry-gate`.
4. Re-run CI/deploy gates before release.

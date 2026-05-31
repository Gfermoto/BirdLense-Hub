# Scripts Ownership & Lifecycle Gate

## Goal

`SOTA-7-01`: prevent orphan critical scripts by enforcing owner/runbook/lifecycle registry.

## Contract

Gate verifies:

- required critical script IDs are present in registry
- script path exists in repository
- owner is assigned for each tracked script
- runbook exists for each tracked script
- lifecycle value matches allowed policy values
- ownership coverage ratio meets target threshold

## Commands

```bash
make scripts-ownership-gate
```

Manual:

```bash
python3 scripts/verify_scripts_ownership.py \
  --registry docs/reports/tooling/scripts_ownership_registry.json
```

## Integrations

- CI docs job: `Scripts ownership lifecycle gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.63`.

## Artifacts

- `docs/reports/tooling/scripts_ownership_registry.json`
- `docs/reports/tooling/scripts_ownership_latest.json`
- `docs/reports/tooling/scripts_ownership_latest.md`

## Rollback / mitigation

1. Add missing owner/runbook/lifecycle fields to registry rows.
2. Restore missing script or fix path if moved.
3. Re-run `make scripts-ownership-gate`.
4. Re-run CI/deploy gates before release.

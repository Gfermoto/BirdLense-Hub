# UI Contract Guard

## Goal

`SOTA-3-01`: enforce OpenAPI -> generated TS types -> runtime UI contract integrity.

## Contract

Gate verifies:

- OpenAPI codegen succeeds (`npm run codegen:openapi`)
- generated contract file has no drift after codegen (`src/generated/openapi-types.ts`)
- UI typecheck succeeds (`npm run typecheck`)

## Commands

```bash
make ui-contract-guard
```

Manual:

```bash
python3 scripts/verify_ui_contract_guard.py
```

## Deploy integration

`scripts/public/deploy.sh` runs this gate at step `0.53`.

- fail blocks deploy
- temporary bypass only via `BIRDLENSE_SKIP_UI_CONTRACT_GATE=1`

## Artifacts

- `docs/reports/ui_contract/ui_contract_guard_latest.json`
- `docs/reports/ui_contract/ui_contract_guard_latest.md`

## Rollback / mitigation

1. If gate fails on drift, run `npm run codegen:openapi` in `app/ui`.
2. Commit updated `src/generated/openapi-types.ts`.
3. Re-run `npm run typecheck` and `make ui-contract-guard`.

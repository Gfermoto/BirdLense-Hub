# Docs Diataxis Gate

## Goal

`SOTA-4-01`: classify key documentation sections by Diataxis and reduce cross-type confusion.

## Contract

Gate verifies:

- each target page in Diataxis plan exists
- each target page has valid type (`tutorial`, `how-to`, `reference`, `explanation`)
- classification coverage reaches policy target
- cross-type bleed remains under policy threshold

## Commands

```bash
make docs-diataxis-gate
```

Manual:

```bash
python3 scripts/verify_docs_diataxis.py \
  --plan docs/reports/docs_diataxis/diataxis_plan.json
```

## Integrations

- CI docs job: `Docs Diataxis governance gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.58`.

## Artifacts

- `docs/reports/docs_diataxis/diataxis_plan.json`
- `docs/reports/docs_diataxis/docs_diataxis_latest.json`
- `docs/reports/docs_diataxis/docs_diataxis_latest.md`

## Rollback / mitigation

1. Fix invalid or missing target pages in plan.
2. Reclassify pages with wrong Diataxis type.
3. Re-run `make docs-diataxis-gate` and docs checks.

# ML Technical Debt Scorecard Gate

## Goal

`SOTA-2-05`: enforce ML technical debt governance with a formal 28-check scorecard.

## Contract

Gate verifies:

- scorecard contains at least required check count
- each check has assigned owner
- status values use approved vocabulary
- risk values use approved vocabulary
- duplicate check IDs are forbidden
- open high-risk items do not exceed policy threshold

## Commands

```bash
make ml-technical-debt-scorecard-gate
```

Manual:

```bash
python3 scripts/verify_ml_technical_debt_scorecard.py \
  --scorecard docs/reports/ml_debt/ml_technical_debt_scorecard.json
```

## Integrations

- CI docs job: `ML technical debt scorecard gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.65`.

## Artifacts

- `docs/reports/ml_debt/ml_technical_debt_scorecard.json`
- `docs/reports/ml_debt/ml_technical_debt_scorecard_latest.json`
- `docs/reports/ml_debt/ml_technical_debt_scorecard_latest.md`

## Rollback / mitigation

1. Fix duplicate/missing owner/status/risk in scorecard rows.
2. Reduce open high-risk items or document closure plan.
3. Re-run `make ml-technical-debt-scorecard-gate`.
4. Re-run CI/deploy gates before release.

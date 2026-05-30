# Error Budget Policy & Gate

## Goal

`SOTA-0-02`: enforce release governance with automatic error-budget gate.

Policy (v1):

- rolling window: `28d`
- budget: `100%` points
- warning zone: `>=80%`
- exhausted: `>=100%` -> release blocked

Primary signal source: `GET /api/ui/system/domain-health`.

## Scoring model

- each critical SLO breach: `+45%`
- each warning breach: `+15%`
- `slo_dashboard.status.ok=false`: `+20%`
- each `per_camera_warn_count_24h`: `+5%` (cap 4 cameras)
- `recording_artifact_failures=true`: `+10%`

## Commands

```bash
make error-budget-gate
```

Manual:

```bash
python3 scripts/error_budget_gate.py --base-url "${DEPLOY_URL}"
```

## Deploy integration

`scripts/public/deploy.sh` runs error-budget gate at step `0.46`.

- gate fail (`exhausted`): deploy blocked
- emergency override: set `BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON` (non-empty)

## Artifacts

- `docs/reports/error_budget_gate/error_budget_gate_latest.json`
- `docs/reports/error_budget_gate/error_budget_gate_latest.md`

## Rollback / mitigation

If gate starts blocking releases unexpectedly:

1. Keep current production release; do not force deploy.
2. Inspect `error_budget_gate_latest.json` for dominant cost contributors.
3. Execute recovery runbook for breached SLO (`docs/runbooks/runtime-slo-stability.md`).
4. Re-run `make verify` and `make error-budget-gate`.
5. Emergency-only: use override reason, publish incident note, and follow-up fix issue.

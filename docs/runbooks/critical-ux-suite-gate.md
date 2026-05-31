# Critical UX Suite Gate

## Goal

`SOTA-3-03`: guarantee reliability coverage for critical user flows.

## Contract

Gate verifies:

- critical flow contract exists (`timeline`, `settings`, `live`, `system`, `overview`)
- each critical flow is mapped to a smoke Playwright test
- aggregate smoke pass-rate from history stays above threshold

## Commands

```bash
make critical-ux-suite-gate
```

Manual:

```bash
python3 scripts/verify_critical_ux_suite.py \
  --contract docs/reports/e2e_critical/critical_flows.json \
  --history docs/reports/e2e_critical/smoke_history.jsonl
```

## Integrations

- CI: `ci-pr.yml` E2E job runs critical UX suite verifier before smoke.
- Deploy: `scripts/public/deploy.sh` gate step `0.57`.

## Artifacts

- `docs/reports/e2e_critical/critical_flows.json`
- `docs/reports/e2e_critical/smoke_history.jsonl`
- `docs/reports/e2e_critical/critical_ux_suite_latest.json`
- `docs/reports/e2e_critical/critical_ux_suite_latest.md`

## Rollback / mitigation

1. Add missing smoke coverage for any uncovered critical flow.
2. Stabilize failing critical flow tests before release.
3. Re-run `make critical-ux-suite-gate` and E2E smoke.

# Playwright Anti-Flake Program

## Goal

`SOTA-3-02`: reduce flaky E2E via deterministic Playwright policy and quarantine discipline.

## Contract

Gate verifies:

- no `.only()` in committed e2e tests
- no hard waits above policy (`waitForTimeout <= 500ms`)
- Playwright CI config contract:
  - `workers: process.env.CI ? 1`
  - `retries: process.env.CI ? 2 : 0`
  - `trace: 'on-first-retry'`
- quarantine registry schema validity
- aggregate flaky rate from history stays within threshold

## Commands

```bash
make playwright-anti-flake-gate
```

Manual:

```bash
python3 scripts/verify_playwright_antiflake.py \
  --quarantine docs/reports/e2e_flake/quarantine_tests.json \
  --history docs/reports/e2e_flake/flaky_history.jsonl
```

## Integrations

- CI: `ci-pr.yml` E2E job runs anti-flake verifier before smoke.
- Deploy: `scripts/public/deploy.sh` gate step `0.56`.

## Artifacts

- `docs/reports/e2e_flake/quarantine_tests.json`
- `docs/reports/e2e_flake/flaky_history.jsonl`
- `docs/reports/e2e_flake/playwright_antiflake_latest.json`
- `docs/reports/e2e_flake/playwright_antiflake_latest.md`

## Rollback / mitigation

1. Fix violations (`.only`, hard waits, config drift).
2. Quarantine unstable tests with owner/reason/expiry.
3. Re-run `make playwright-anti-flake-gate` and E2E smoke.
4. Unquarantine only after deterministic pass on repeated runs.

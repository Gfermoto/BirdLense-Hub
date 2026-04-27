# Wave 2: critical path coverage

## Test suites detected
- UI: Vitest (`app/ui/src/**/*.test.*`).
- Web API: pytest under `app/web/tests`.
- Processor: pytest/unittest under `app/processor/tests`.
- E2E: Playwright under `app/e2e` (also used in docker-tests CI).

## Execution result
- UI vitest/web pytest/processor light tests: see `wave2-tests.md`.
- Python coverage: see `coverage-report.txt`.
- No explicit failure markers in targeted test logs.
- Python coverage TOTAL: `TOTAL                                                  20131   7633    62%`
- UI coverage: `@vitest/coverage-v8` added and `npm run coverage` executed; raw output in `ui-coverage-report.txt`.

## Critical paths assessment
- Covered: settings/auth gates, OpenAPI contract, system routes, processor smoke, UI route/component tests, timeline/favorites critical UI flows (per detected tests).
- Risk: production-like full-stack E2E coverage depends on Docker stack and test assets; keep `docker-tests` required in CI.
- Risk: UI coverage threshold is not enforced yet; add threshold policy before strict release gate.
- Flaky tests: no repeat/flaky detector found in repo; CI history should be reviewed if instability appears.

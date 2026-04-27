# Manual Intervention Required

No manual intervention is required for the critical/high production readiness items.

## Follow-up: Full-Project Coverage Expansion

The requested minimum gate is statements/lines 80%, branches 70%, functions 80%, with a hard minimum of 70% when adapted to current coverage.

Critical production hardening gates are now blocking in CI:

- UI CSRF client gate: 95.16% statements/lines, 70.58% branches, 100% functions.
- Python CSRF/auth startup gate: 92% total.

Full-project measured coverage is still below the long-term floor:

- Python web+processor: 62% line coverage from the prior coverage report.
- UI Vitest: 12.79% statements/lines, 45.38% branches, 20.29% functions from `coverage/coverage-summary.json`.

CI now runs both full coverage reporting and blocking critical coverage gates. `.review-automation/coverage-gap.md` lists the highest-value missing tests for broadening the full-project gate.

## Developer plan

1. Add focused UI route tests for Overview, Library, System, Settings, empty/error states, and CSRF bootstrap.
2. Add Python tests for low-coverage services listed in `.review-automation/coverage-gap.md`.
3. Expand blocking thresholds from the critical hardening surface to full project once totals reach at least 70%.

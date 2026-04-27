# Manual Intervention Required

## Coverage threshold gate

The requested minimum gate is statements/lines 80%, branches 70%, functions 80%, with a hard minimum of 70% when adapted to current coverage.

Current measured coverage is below that floor:

- Python web+processor: 62% line coverage from the prior coverage report.
- UI Vitest: 12.79% statements/lines, 45.38% branches, 20.29% functions from `coverage/coverage-summary.json`.

Tests were explicitly out of scope for this hardening pass, so enabling a blocking 70% threshold now would intentionally break CI. CI now runs coverage reporting, and `.review-automation/coverage-gap.md` lists the highest-value missing tests.

## Developer plan

1. Add focused UI route tests for Overview, Library, System, Settings, empty/error states, and CSRF bootstrap.
2. Add Python tests for low-coverage services listed in `.review-automation/coverage-gap.md`.
3. Enable blocking thresholds once totals reach at least 70%:
   - Vitest: `coverage.thresholds` in `app/ui/vitest.config.ts`.
   - Python: `coverage report --fail-under=70` in CI.

# Production Readiness

Verdict: **УСЛОВНО ГОТОВ**.

The codebase passes core lint/type/test/security checks after automatic fixes, and `main`/`dev` workflow is healthy. Production release is acceptable for a controlled/self-hosted deployment only if the required environment gates below are set and the listed high-priority risks are tracked.

## Top 5 before public production

1. **Enable strict production auth:** set `BIRDLENSE_ENV=production` and `BIRDLENSE_STRICT_API_AUTH=1`; verify `FLASK_SECRET_KEY` and `PROCESSOR_SECRET` are non-empty.
2. **CSRF decision:** add explicit CSRF protection for cookie-auth mutations or enforce non-cookie API-key/Bearer auth for production automation.
3. **Fix UI accessibility headings:** axe reports missing/incorrect heading hierarchy on major routes.
4. **Keep coverage gates:** Python total coverage observed at ~62%; UI coverage script/provider added, but thresholds still need policy.
5. **Run real secret scanner in CI:** current fallback regex is noisy; add Gitleaks config and required check.

## Automatic fixes applied

- UI Prettier formatting across affected `app/ui/src` files.
- `npm audit fix` for UI PostCSS moderate vulnerability.
- Added `@vitest/coverage-v8@3.2.4` and `npm run coverage` for UI coverage.
- Fixed Overview runtime crash when `/api/ui/overview` returns incomplete/invalid data during API outage/dev-server review.
- Added release checklist to `README.md`.

## Evidence

Artifacts: `.review-automation/`:
- `step0-preparation.md`
- `wave0-automatic-issues.md`, `wave0-post-autofix.md`
- `wave1-static-analysis.md`, `static-analysis-raw.log`
- `wave2-tests.md`, `coverage-report.txt`, `ui-coverage-report.txt`, `wave2-critical-paths.md`
- `wave3-ui-report.md`, `screenshots/`, `logs/ui-review-results.json`
- `wave4-security-production.md`
- `critical-issues.md`, `manual-fixes-required.md`

Pending environment/config suggestions: `.pending-changes.md`.

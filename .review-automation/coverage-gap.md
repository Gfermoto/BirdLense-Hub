# Coverage gap

Target policy for production hardening:

- statements/lines: 80% desired, **70% minimum gate**
- branches: **70% minimum gate**
- functions: 80% desired, **70% minimum gate**

Critical production hardening gate now enforced in CI:

| Area | Lines/statements | Branches | Functions | Status |
|---|---:|---:|---:|---|
| UI CSRF client (`src/api/client.ts`) | 95.16% | 70.58% | 100% | blocking gate passes |
| Python CSRF/auth startup | 92% total | n/a | n/a | blocking gate passes |

Current full-project measured coverage:

| Area | Lines/statements | Branches | Functions | Status |
|---|---:|---:|---:|---|
| Python web+processor (`make test-coverage`) | 62% lines | n/a | n/a | below 70% gate |
| UI Vitest (`npm run coverage`) | 12.73% statements/lines | 45.38% | 20.29% | below 70% gate |

Full-project threshold should become blocking once these gaps are closed. Until then, CI reports full coverage and blocks regressions in the critical production hardening surface.

## Highest-value missing test areas

1. UI route/data-state tests for `Overview`, `Library`, `System`, `Settings`, API failure/empty states.
2. Web service coverage below 50%: `species_image_proxy_service`, `species_tuning_targets_service`, `system_spectrogram_regen_service`, `system_sqlite_admin_api_service`, `telegram_proxy_service`, `weather_service`.
3. Processor best-effort cleanup/error paths currently hidden behind broad `except/pass` blocks.
4. E2E happy-path smoke for production strict auth + CSRF token bootstrap.

## Next implementation plan

- Add focused tests for one critical route/page per PR until Python >=70% and UI >=70%.
- Then expand blocking thresholds from `coverage:critical` / `test-coverage-critical` to full-project coverage.

# Coverage gap

Target policy for production hardening:

- statements/lines: 80% desired, **70% minimum gate**
- branches: **70% minimum gate**
- functions: 80% desired, **70% minimum gate**

Current measured coverage:

| Area | Lines/statements | Branches | Functions | Status |
|---|---:|---:|---:|---|
| Python web+processor (`make test-coverage`) | 62% lines | n/a | n/a | below 70% gate |
| UI Vitest (`npm run coverage`) | 12.73% statements/lines | 45.38% | 20.29% | below 70% gate |

The threshold cannot be enabled as a blocking CI gate without first adding tests (explicitly out of scope for this task). CI now runs coverage reporting; make the gate blocking once these gaps are closed.

## Highest-value missing test areas

1. UI route/data-state tests for `Overview`, `Library`, `System`, `Settings`, API failure/empty states.
2. Web service coverage below 50%: `species_image_proxy_service`, `species_tuning_targets_service`, `system_spectrogram_regen_service`, `system_sqlite_admin_api_service`, `telegram_proxy_service`, `weather_service`.
3. Processor best-effort cleanup/error paths currently hidden behind broad `except/pass` blocks.
4. E2E happy-path smoke for production strict auth + CSRF token bootstrap.

## Next implementation plan

- Add focused tests for one critical route/page per PR until Python >=70% and UI >=70%.
- Then enable blocking thresholds in `vitest.config.ts` and `coverage report --fail-under=70` in CI.

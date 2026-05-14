# Public Release Hardening Backlog

Цель: зафиксировать baseline-аудит и приоритеты перед публичным релизом.

## Scope baseline (Wave 1)

- Проверены домены: `app/processor`, `app/web`, `app/ui`, `docs`, `scripts`, `.github/workflows`.
- Сверены runtime-контракты, OpenAPI, UI API-слой, CI parity и release-gate документация.

## Prioritized backlog

| Priority | Domain | Problem | Risk | Wave |
|---|---|---|---|---|
| P0 | API contract | В `openapi.yaml` нет `/metrics`, `/api/metrics`, `/api/metrics/summary` при существующих route | External API desync | 3 |
| P0 | DX/docs | В `README.md` для разработчиков указан `make test`/`make test-web` из корня, но цели находятся в `app/Makefile` | Broken first-run for contributors | 3 |
| P1 | Runtime consistency | Логика production-runtime была продублирована в нескольких модулях (`auth`, `processor_routes`, `settings_access_service`, `config`, `readiness`) | Divergent security/runtime behavior | 2 |
| P1 | CI parity | `scripts/ci-full-local.sh` не покрывал весь CI-путь (`ui coverage`, `verify-strict-quality` в docker хвосте) | False-green local preflight | 5 |
| P1 | Docs consistency | `docs/TESTING.md` / `docs/CI_AND_QUALITY.md` отставали от реального `ci-pr.yml` | Inaccurate release gate | 3 |
| P2 | Project hygiene | Требуется release-классификация открытых issue и исключение `#243/#250/#376` из blocker scope | Noisy release board | 4 |
| P2 | Open-source prep | В `docs/OPEN_SOURCE_PREP.md` оставались незакрытые пункты перед паблик-релизом | Incomplete public readiness narrative | 3 |

## Dependencies and execution order

1. `Wave 2` runtime cleanup first: минимизирует расхождение поведения между средами.
2. `Wave 3` docs/API sync next: делает контракт и документацию достоверными для внешних пользователей.
3. `Wave 4` issue/board sync after code/docs updates: triage уже по актуальному состоянию.
4. `Wave 5` verification gate last: финальная валидация по обновлённым проверкам и документации.

## Explicit out-of-scope constraints

- Issues `#243`, `#250`, `#376`: не менять содержимое задач; только пометка как `waiting-for-field-test` и исключение из release-blockers.

# Public Release Checklist

[Русский](./PUBLIC_RELEASE_CHECKLIST.ru.md)

Единый pre/post-release чеклист для публичного релиза BirdLense Hub.

---

## Pre-release (must pass)

1. Из корня репозитория:
   - `make ci-local`
   - `make ci-local-docker`
2. Контракт и типы:
   - `cd app/ui && npm run codegen:openapi`
   - `git diff --exit-code -- src/generated/openapi-types.ts`
3. Runtime gate на целевом URL:
   - `BASE_URL=http://YOUR_HOST:8085 make verify`
   - `BASE_URL=http://YOUR_HOST:8085 ./scripts/verify-release.sh`
4. Security gates:
   - `BIRDLENSE_ENV=production`
   - `BIRDLENSE_STRICT_API_AUTH=1`
   - non-empty `FLASK_SECRET_KEY`
   - non-empty `PROCESSOR_SECRET`
5. Docs consistency:
   - `mkdocs build --strict`
   - OpenAPI paths для `/metrics`, `/api/metrics`, `/api/metrics/summary` присутствуют и соответствуют runtime

## Pre-release issue triage

- Пройти открытые issue и пометить: `release-blocker`, `post-release`, `research`, `waiting-test`.
- Для `#243`, `#250`, `#376`: оставить как `waiting-for-field-test`, исключить из release-blockers.

## Post-deploy smoke (5–10 min)

1. `GET /api/ui/health` -> `ok`
2. `GET /api/ui/readiness` -> `ready: true`
3. `GET /api/ui/status` -> web/processor не в error
4. Открыть UI:
   - `Library` (загрузка карточек)
   - `System` (readiness + metrics/history)
   - `Timeline` (фильтры/сортировка работают)
5. Проверить Prometheus paths:
   - `GET /metrics`
   - `GET /api/metrics`
   - `GET /api/metrics/summary`

## Release report template

- Что изменено (код, docs, CI, ops)
- Что проверено (команды + статус)
- Остаточные риски
- Что отложено (включая `#243/#250/#376`)

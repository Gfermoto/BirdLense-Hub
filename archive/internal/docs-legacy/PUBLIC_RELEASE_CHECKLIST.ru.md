# Чеклист публичного релиза

[English](./PUBLIC_RELEASE_CHECKLIST.md)

Единый pre/post-release чеклист для публичного релиза BirdLense Hub.

---

## До релиза (обязательно)

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
   - непустой `FLASK_SECRET_KEY`
   - непустой `PROCESSOR_SECRET`
5. Консистентность доков:
   - `mkdocs build --strict`
   - в OpenAPI есть `/metrics`, `/api/metrics`, `/api/metrics/summary`, и это соответствует runtime

## Триаж issue перед релизом

- Пройти открытые issue и разнести по: `release-blocker`, `post-release`, `research`, `waiting-test`.
- Для `#243`, `#250`, `#376`: оставить как `waiting-for-field-test`, исключить из release-blockers.

## Smoke после деплоя (5–10 мин)

1. `GET /api/ui/health` -> `ok`
2. `GET /api/ui/readiness` -> `ready: true`
3. `GET /api/ui/status` -> web/processor не в error
4. Проверить UI:
   - `Library` (карточки загружаются)
   - `System` (readiness + metrics/history)
   - `Timeline` (фильтры/сортировка работают)
5. Проверить Prometheus пути:
   - `GET /metrics`
   - `GET /api/metrics`
   - `GET /api/metrics/summary`

## Шаблон release report

- Что изменено (код, docs, CI, ops)
- Что проверено (команды + статус)
- Остаточные риски
- Что отложено (включая `#243/#250/#376`)

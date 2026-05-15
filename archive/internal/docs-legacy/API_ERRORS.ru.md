# Формат ошибок API и security baseline

[English](./API_ERRORS.md)

Кратко для новых маршрутов `/api/ui/*`: что ждёт SPA и куда смотреть по безопасности.

## Типовые JSON

| Паттерн | Пример | HTTP | Где встречается |
|---------|--------|------|------------------|
| Строка ошибки | `{ "error": "..." }` | 4xx/5xx | Много legacy |
| Успех | `{ "ok": true, ... }` | 200 | Часть maintenance |

**Для новых ручек:** стабильный **код** + человекочитаемая строка; клиент тянет i18n. Спецификация — [OpenAPI](./project/openapi.md).

## OpenAPI

После правок схемы: `npm run codegen:openapi` в `app/ui`; CI ловит дрейф.

## Security

| Проверка | Где |
|----------|-----|
| Bandit + pip-audit | `make ci-local`, игнор PYSEC — [CI_AND_QUALITY](./CI_AND_QUALITY.ru.md). |
| Секреты | не коммитить `.env`; шаблоны в `app/.env.example`. |
| CORS | `CORS_ORIGINS` для публичного URL — [DEPLOY_SERVER](./DEPLOY_SERVER.ru.md). |

Трекинг: [BirdLense-Hub#331](https://github.com/Gfermoto/BirdLense-Hub/issues/331).

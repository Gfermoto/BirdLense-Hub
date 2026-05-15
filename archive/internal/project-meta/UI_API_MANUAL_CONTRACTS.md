# UI API: ручные типы и отличия от OpenAPI (#343)

Сгенерированные типы: `app/ui/src/generated/openapi-types.ts` (из `app/web/openapi.yaml`).

Ниже — эндпоинты и ответы, где UI **держит отдельный TS-тип** или **обходит слабую схему в YAML**, и почему.

| Область | Маршрут / модуль | Почему не «только OpenAPI» |
|--------|-------------------|----------------------------|
| Камеры | `GET /cameras` (`camerasHealth.ts`) | В спецификации тело `200` — `{ [key: string]: unknown }`; реальный контракт — `{ cameras: CameraRow[] }`. Экспорт **`CameraRow`**. |
| Кормушка | `GET /feed/info` (`birdFoodFeed.ts`) | В YAML ответ `application/json` — index-signature `unknown`; карточка кормушки богаче. Тип ответа описан **вручную** в `fetchFeedInfo`. |
| Observability | `GET /system/observability` (`systemAuditMetrics.ts`) | Крупный агрегированный JSON без выделенной схемы в `components`; тип **`ObservabilityPayload`** поддерживается вручную. |
| Dataset / file-test | часть ответов | Бинарные/файловые потоки и редкие поля — по необходимости вручную; при появлении схем в YAML — перенос в `components`. |

При добавлении маршрута в Hub: сначала обновить **`openapi.yaml`**, перегенерировать типы, затем заменить ручной тип на `paths[...]` / `components['schemas'][...]`, если схема стала точной.

См. также: [OpenAPI specification](openapi.md).

## React Query (`queryKey`)

Новые ключи кэша — **только** через фабрики в `app/ui/src/api/queryKeys.ts` (`queryKeys.*`); в компонентах не вводить `queryKey: ['строка', …]` (ловит ESLint `no-restricted-syntax` в `app/ui/eslint.config.js`, [#359](https://github.com/Gfermoto/BirdLense-Hub/issues/359)). Исключение: копирование уже типизированного ключа, например `{ queryKey: [...key] }` в `invalidateLocalSpeciesCaches.ts`.

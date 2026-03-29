# Верификация качества (операторам и мейнтейнерам)

Краткий журнал автоматических проверок перед возвратом к roadmap. Полный цикл — см. [CONTRIBUTING.ru.md](../CONTRIBUTING.ru.md), [TESTING.ru.md](./TESTING.ru.md).

## 2026-03-29 — критический фикс UI

| Проверка | Результат |
|----------|-----------|
| Кнопки «предыдущая / следующая запись» на `/videos/:id` | Исправлен `ReferenceError` (`listReturnState` не был объявлён); см. [CHANGELOG.md](../CHANGELOG.md) [Unreleased] |
| `make test-web` (Docker, `app/`) | 100 passed |
| `npm run build` (`app/ui`) | OK |

**Рекомендуется вручную на стенде:** открыть ролик с Timeline → шаг prev/next → «Назад» возвращает в список; прямой заход по URL без `state` — навигация между роликами работает, «Назад» в браузере — по истории.

**Вне объёма автопрогона:** weekly E2E Playwright, полный `make docs` при изменении MkDocs.

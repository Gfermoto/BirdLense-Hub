# Definition of Done (ворота релиза) — BirdLense Hub

[English](./DEFINITION_OF_DONE.md)

Одна страница **перед** тегом релиза, merge стабилизации или заявлением «хаб в продакшене». Расширенный чеклист (domain health, registry, секреты CI): [RELEASE_READINESS](./RELEASE_READINESS.ru.md).

---

## Обязательно (автоматика)

1. Из **корня репозитория**: `make ci-local` — успешное завершение (Bandit, pip-audit, Ruff, `pytest web/tests/`, drift OpenAPI codegen, UI Vitest + typecheck + lint + `vite build`, скрипт покрытия Settings UI, MkDocs `--strict`).  
   - Жёстче: `make ci-local-docker` (тесты в образе + Playwright smoke; нужны Docker, веса, **Node ≥ 22**).
2. Staging/прод URL: `BASE_URL=https://ваш-хаб/ make verify` или `scripts/verify-stack.sh --base-url …` — **`verify-stack: PASS`**.

## Ручной смоук ~5 минут (оператор)

На **том же** билде, что и релиз:

| # | Проверка | Ок? |
|---|-----------|-----|
| 1 | **Library** — недавние клипы открываются, нет вечного спиннера. | ☐ |
| 2 | **System** — readiness **ready** (или только осознанные optional-пробелы). | ☐ |
| 3 | **Настройки → Процессор** (admin) — сохранить безопасное изменение, успех без ошибки. | ☐ |
| 4 | Поток/тест — **один** цикл motion/записи без перезапуска процессора по кругу. | ☐ |
| 5 | Если важен Frigate/MQTT — один проход событий (или явно «пропуск» с записью в release notes). | ☐ |

## Документирование релиза

- [ ] Запись в `CHANGELOG.md` (видимые изменения, миграции, ключи конфига).
- [ ] При смене поведения/операций — строка в [RUNBOOKS](./RUNBOOKS.ru.md) или [DEPLOY_SERVER](./DEPLOY_SERVER.ru.md), если операторам нужно действие.

---

**Не входит в эти ворота:** roadmap фич, ML-бенчмарки, монетизация — в Issues / Projects отдельно.

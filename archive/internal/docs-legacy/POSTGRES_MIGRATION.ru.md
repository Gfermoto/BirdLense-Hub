# PostgreSQL для BirdLense Hub — операторский гайд

[English](./POSTGRES_MIGRATION.md)

Единый источник правды по запуску **веб-БД** Hub на PostgreSQL при более высокой конкурентной записи (многокамерные установки). Связанный эпик: [#424](https://github.com/Gfermoto/BirdLense-Hub/issues/424) (трек **B3**).

---

## Когда нужен PostgreSQL

| Ситуация | Рекомендация |
|----------|----------------|
| Один хаб, умеренная нагрузка | По умолчанию достаточно **SQLite** в `DATA_DIR/db/birdlense.db` |
| Много параллельной записи (камеры, UI, автоматизация) | Задайте **`DATABASE_URL`** на PostgreSQL и настройте пул |
| HA / внешние бэкапы по политике | PostgreSQL + ваш стандартный ops-стек |

Приложение Flask использует SQLAlchemy и миграции **Alembic** (`app/web/migrations/`). При старте `create_app()` вызывает `db.create_all()`, затем **`upgrade()`** — один и тот же путь для SQLite и PostgreSQL (см. [ARCHITECTURE.ru.md](./ARCHITECTURE.ru.md) § База данных).

---

## Compose и окружение

**Пример стека** (Postgres 16 + Redis + hub): [`app/docker-compose.stack.example.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/docker-compose.stack.example.yml).

Запуск:

```bash
cd app
docker compose -f docker-compose.yml -f docker-compose.stack.example.yml up -d
```

В **`app/.env`** (деплой файл не перезаписывает):

| Переменная | Назначение |
|------------|------------|
| `DATABASE_URL` | например `postgresql+psycopg://birdlense:SECRET@postgres:5432/birdlense` |
| `SQLALCHEMY_POOL_SIZE` | Размер пула (по умолчанию `5` в `app/web/config.py`) |
| `SQLALCHEMY_MAX_OVERFLOW` | Доп. соединения сверх пула (по умолчанию `15`) |

Реализация: `app/web/config.py` — различие опций движка SQLite vs не-SQLite.

См. также [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) → переменные окружения.

---

## Отдельный SQLite процессора (`birdlense.db`)

**Процессор** по-прежнему использует файл **`DATA_DIR/db/birdlense.db`** для локальной диагностики и персистенции BirdNET FIFO (если включено). Этот файл **не заменяется** переменной `DATABASE_URL`.

Следствия:

- Строки **BirdNET FIFO**, которые процессор пишет в SQLite, при Hub только на PostgreSQL **без общего sqlite-файла** могут быть отключены или ограничены — см. [CHANGELOG](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) и [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) (BirdNET / `DATABASE_URL`).
- Используйте **`detection.species_mapping`** в YAML, если строки из MQTT нельзя сопоставить через каталог SQLite — [TROUBLESHOOTING.ru.md](./TROUBLESHOOTING.ru.md).

---

## Сценарии развёртывания

### A. Greenfield PostgreSQL (пустая БД)

1. Поднять Postgres, создать роль/БД (как в `DATABASE_URL`).
2. Прописать `DATABASE_URL` и параметры пула в `app/.env`.
3. Запустить стек (`docker compose` как выше).
4. На первом старте применятся миграции; проверить **`GET /api/ui/readiness`** и **`/api/ui/status`**.

### B. Перенос данных с существующего SQLite (только Hub БД)

В репозитории **нет** официального «одной кнопки» переноса SQLite→Postgres. Типичный операторский путь:

1. **Бэкап** текущего SQLite (System → резервная копия или копия `data/db/birdlense.db`).
2. **Окно обслуживания**: остановить запись (остановить хаб или режим обслуживания).
3. Создать **пустую** PostgreSQL БД со схемой на актуальной ревизии:
   - указать `DATABASE_URL` на Postgres и один раз поднять хаб, чтобы Alembic дошёл до head, **или** выполнить контролируемый `flask db upgrade` в образе по внутренней процедуре.
4. **Массовая загрузка** исторических строк своим инструментом (`pgloader`, ETL, миграции вендора). Сверить объёмы и внешние ключи; прогнать смоки приложения.

Риски: отличия типов (JSON/JSONB — ревизия Alembic `004_birdnet_fifo_event`), большие бинарные поля, порядок зависимых таблиц. Лучше проверять на **staging**-клоне до продакшена.

Если стоимость миграции выше выгоды — оставайтесь на **SQLite**, пока нагрузка не потребует Postgres, или заведите **новый** Postgres-хаб, а старый SQLite архив оставьте только для чтения.

---

## Проверки

После смены `DATABASE_URL`:

- `make verify` / `scripts/verify-stack.sh --base-url ...`
- опционально `scripts/check-runtime-sli.sh` после деплоя (см. `.github/workflows/deploy.yml`).

---

## См. также

- [DEPLOY_SERVER.ru.md](./DEPLOY_SERVER.ru.md) · [INSTALL.ru.md](./INSTALL.ru.md)
- [PUBLIC_RECORDINGS.ru.md](./PUBLIC_RECORDINGS.ru.md)
- [RUNBOOKS.ru.md](./RUNBOOKS.ru.md)

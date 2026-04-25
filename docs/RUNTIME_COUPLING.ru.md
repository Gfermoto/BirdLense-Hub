# Связность runtime (один контейнер)

Как образ **BirdLense** связывает web, processor и `PYTHONPATH`, и как ослаблять связность без поломки стандартного install path. Рядом с [ARCHITECTURE.ru.md](./ARCHITECTURE.ru.md) и [TROUBLESHOOTING.ru.md](./TROUBLESHOOTING.ru.md). Трекер: [issue #347](https://github.com/Gfermoto/BirdLense-Hub/issues/347).

[English](./RUNTIME_COUPLING.md)

---

## Инвентаризация `PYTHONPATH` (контейнер)

| Шаг | `PYTHONPATH` | Каталог / команда |
| ----- | ---------------- | ------------------- |
| Gunicorn | `/app` | `cd /app/web` → `gunicorn … app:app` |
| MCP (опционально) | `/app` | `python3 /app/web/birdlense_mcp.py …` |
| Цикл processor | `/app:/app/web` | `python /app/processor/src/main.py` |

**`/app`** — корневые модули образа (`ebird_region_core.py`, `shared/`, дерево `processor/`). **`/app/web`** на пути processor оставлен для совместимости ([#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128)); в текущем дереве под `app/processor/` не должно быть прямых `from services.*` — перед удалением `/app/web` из entrypoint нужен повторный аудит и CI.

---

## Границы web ↔ processor

| Направление | Механизм | Примечание |
| ------------- | ---------- | ------------ |
| **Processor → web** | HTTP к `API_URL_BASE` | Ingest, notify, activity log; секрет `PROCESSOR_SECRET` |
| **Web → код processor** | Файловая система + `sys.path`, не импорт `web` из processor | `fusion_training_service` добавляет `processor/src` для `fusion_*` |
| **Общий код** | `app/shared/` → `/app/shared/` | Пример: `dataset_saver` → `shared.detection_crop_contract` |

**Кандидаты в `app/shared/`** — при появлении второго потребителя или упрощении тестов; вынос `fusion_*` — отдельный крупный рефакторинг.

---

## Health: «web ok» vs «processor ok»

| Проба | Смысл |
| ------- | -------- |
| **`GET /api/ui/health`** | Отвечает процесс gunicorn/Flask; **без** проверки БД/диска. |
| **`GET /api/ui/readiness`** | БД, доступность `data/` и `app_config/`, компоненты; **503**, если не готов. |
| **Processor** | Отдельного HTTP health в образе по умолчанию нет; логи, live/MJPEG, успешные `POST /api/processor/*`. |

Текущий `healthcheck` в Compose — **`/api/ui/health`** на **8000** внутри контейнера (как ожидание в `entrypoint.sh`).

---

## Профиль Compose `dev-split` (черновик)

Цель — опциональная мульти-сервисная схема для dev **без** изменения дефолтного `docker compose up` (без второго `-f` — как сейчас).

**Статус:** только контракт; боевой образ по-прежнему один CMD. Проверка слияния с основным compose:

```bash
cd app
docker compose -f docker-compose.yml -f docker-compose.dev-split.example.yml config
```

Файл **`app/docker-compose.dev-split.example.yml`** пока содержит только блок расширения **`x-`** (метаданные), без **`services`**. Позже сюда можно добавить сервисы с **`profiles: ["dev-split"]`**, когда образ позволит разнести роли.

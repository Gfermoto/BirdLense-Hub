# Структура репозитория

Где что лежит в монорепозитории BirdLense Hub. **Версия релиза** — корневой файл `VERSION` (дублируется в `mkdocs.yml`, `app/ui/package.json`, `app/web/openapi.yaml`; проверка — `scripts/check-docs-version.py`).

[English](./REPOSITORY_LAYOUT.md)

---

## Корень репозитория

| Путь | Назначение |
|------|------------|
| **`app/`** | Рабочий стек: Docker Compose, **web** (Flask API), **processor** (детекция), **ui** (React/Vite). Обычно: `cd app && make local` / `make start` — см. [LOCAL_DEV.ru](./LOCAL_DEV.ru.md). |
| **`docs/`** | Документация для операторов и разработчиков; исходники **MkDocs**. Оглавление: [README.ru](./README.ru.md). |
| **`scripts/`** | Деплой (`deploy.sh`, `deploy.local.sh.example`), диагностика, датасеты, скрипты GitHub Project, верификация. |
| **`mkdocs.yml`**, **`overrides/`** | Статический сайт документации (GitHub Pages). Сборка: `make docs-site` или [Documentation.ru](./Documentation.ru.md). |
| **`Makefile`** (корень) | `deploy`, `docs-site`, Telegram proxy, `restore-config` и т.д. Сборка/запуск приложения — в `app/Makefile`. |
| **`VERSION`** | Текущая semver-версия хаба (единый источник для проверок версии). |
| **`examples/`** | Примеры конфигов (например правила Prometheus), приложение их само не подхватывает. |
| **`wiki-source/`** | Заготовки / автоматизация для GitHub Wiki — см. [WIKI_AUTOMATION.ru](./WIKI_AUTOMATION.ru.md). |
| **`screenshots/`** | Картинки для доков и статей. |
| **`docs/article/`** | Черновики внешних публикаций (например Хабр); не часть рантайма. |
| **`datasets/`** | Опциональная локальная выгрузка датасетов (корень в `.gitignore`). См. [DATASETS.ru](./DATASETS.ru.md) и `scripts/datasets/`. |

---

## Внутри `app/`

| Путь | Назначение |
|------|------------|
| **`app/web/`** | Flask, REST API, OpenAPI (`openapi.yaml`). Точка входа: `app.py` → **`create_app()`** (фабрика); CORS/PRAGMA — `flask_extensions.py`; старт БД/registry/cleanup — `app_startup.py`. Обработчики: `routes/` — `ui_routes.register_routes`, доменные `ui_*_routes`, `ui_system_*`, `processor_routes` ([ARCHITECTURE.ru.md](./ARCHITECTURE.ru.md)). **Миграции:** `migrations/` (Alembic, Flask-Migrate). **Сервисы:** `services/` (доменная логика; тонкие роуты — [ROADMAP.ru](./ROADMAP.ru.md), техдолг). |
| **`app/processor/`** | Конвейер детекции, YOLO/Ultralytics; тяжёлые веса — см. `.gitignore`. **`src/`:** `main.py`, `processor_bootstrap.py`, `detection_stack.py`, `detection_strategy.py` (ABC), **`interfaces.py`** (`DetectionStrategyProtocol` для типизации `FrameProcessor` и тестов без YOLO), `frame_processor.py`, MQTT/запись; **`tests/`** — в т.ч. `test_detection_strategy_protocol.py`. |
| **`app/ui/`** | Фронтенд React 19 + Vite 6; артефакт `npm run build` отдаёт web-слой (см. [LOCAL_DEV.ru](./LOCAL_DEV.ru.md)). |
| **`app/app_config/`** | **Поставляемые** дефолты и шаблоны. Файл **`user_config.yaml`** создаётся на инсталляции и **не** коммитится — см. [CONFIGURATION.ru](./CONFIGURATION.ru.md). |
| **`app/data/`** | SQLite, записи, локальное состояние — при деплое по умолчанию не затирается; см. [INSTALL.ru](./INSTALL.ru.md). |

---

## Порядок (для контрибьюторов)

- Не коммить **отладочные дампы** и разовые json/txt в **корень репозитория**. Типичные маски уже в **`.gitignore`**; временное — в `/tmp` или локальную папку вне репо.
- **Конфиг:** рабочий `user_config.yaml` и данные — под `app/`, а не пустой дубликат `app_config/` в корне.
- **Код vs доки:** рантайм в `app/`; тексты и гайды в `docs/`.

---

## См. также

- [Индекс документации](./README.ru.md) — три входа (запуск / интеграции / разработка).
- [ARCHITECTURE.ru](./ARCHITECTURE.ru.md) — как связаны компоненты.
- Корневой [README.ru](https://github.com/Gfermoto/BirdLense-Hub/blob/main/README.ru.md) — кратко для читателей.

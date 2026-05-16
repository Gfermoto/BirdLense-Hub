<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Hub Logo">
</p>

# BirdLense Hub

[![Version](https://img.shields.io/badge/version-0.3.7-blue.svg)](./CHANGELOG.md) [English](./README.md) · [Contributing](./CONTRIBUTING.md) [RU](./CONTRIBUTING.ru.md) · [Security](./SECURITY.md) [RU](./SECURITY.ru.md)

### Краткое описание

Канонические формулировки для **About** на GitHub, зеркал и анонсов: **[SHORT_DESCRIPTION.ru.md](./SHORT_DESCRIPTION.ru.md)** · **[English](./SHORT_DESCRIPTION.md)**

Мониторинг птиц у кормушек, в саду и на площадках: компьютерное зрение и аудио для детекции, идентификации, записи и анализа визитов — для орнитологии, гражданской науки и операторов, которые держат данные на своём железе. Docker на x86; интеграции с Go2RTC, Frigate, BirdNET по MQTT. Ядро обработки без облака вендора.

**Документация:** [Обзор](./docs/ru/overview.ru.md) · [Индекс RU](./docs/ru/index.md) · [Полный индекс](./docs/index.md) · [Сайт (Pages)](https://gfermoto.github.io/BirdLense-Hub/)

**Сообщество:** [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions) · [Issues](https://github.com/Gfermoto/BirdLense-Hub/issues)

### Модели

Два компонента: **детектор** (птица или грызун Rodent в кадре) и **классификатор** (вид птицы).

| Компонент | Версия | Дообучено на | Примечание |
|-----------|--------|--------------|------------|
| **Детектор** | YOLO11n | NABirds + COCO birds + OIDv4 squirrel | Бинарный bird/rodent (веса могут содержать класс squirrel; хаб нормализует в Rodent) — **не меняется** при EU-обучении |
| **Классификатор** | YOLO11n-cls | birds-525 + iNaturalist (≈490) | EU по умолчанию; US/NABirds — опциональный резерв |

**Текущая модель:** EU (birds-525 + iNaturalist Europe, ~491 вид). US (NABirds) — резерв в `best_US.pt`.

**EU-модель:** классификатор обучен на merged_cls → [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged). Веса: [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu). Обучение: [TRAINING.md](./archive/internal/docs-legacy/TRAINING.md). Детектор не меняется.

**Каталог видов:** приведение к классам классификатора — `species.catalog_allowlist_file`, опционально `catalog_strict_ingest`, скрипт `scripts/datasets/dump_classifier_allowlist.py`, массовая чистка `POST /api/ui/system/species-catalog/reconcile`; см. [конфигурация](./docs/ru/configuration.ru.md).

**Модели:** two-stage — `detection/weights/best.pt` (бинарник, zip из форка [AleksandrRogachev94/BirdLense → `app/processor`](https://github.com/AleksandrRogachev94/BirdLense/tree/main/app/processor)) и `classification/weights/best.pt` (EU, [HF `gfermoto/birdlense-birds-eu`](https://huggingface.co/gfermoto/birdlense-birds-eu)). Скачивание: `scripts/fetch-processor-weights.sh`. Рядом с классификатором — `class_names.txt`. `app/yolo11n.pt` — legacy (`--legacy-single-stage`).

<details>
<summary>📷 Скриншоты</summary>
<br>
<p align="center">
  <img src="screenshots/dashboard1.jpg" width="800" alt="Дашборд">
</p>
<p align="center">
  <img src="screenshots/dashboard2.jpg" width="800" alt="Активность">
</p>
<p align="center">
  <img src="screenshots/video-details.jpg" width="800" alt="Детали видео">
</p>
</details>

## Возможности

### Основное
- **Видео** — поток с IP-камер через [Go2RTC](https://github.com/AlexxIT/Go2RTC), оверлеи детекций в реальном времени
- **Детекция птиц** — кастомный YOLO + ByteTrack, двухэтапная стратегия (бинарный детектор + классификатор видов)
- **Аудио** — [BirdNET](https://github.com/kahst/BirdNET-Analyzer) через MQTT (BirdNET-Pi/Go)
- **Триггеры** — OpenCV motion, события Frigate, MQTT binary, ESPHome
- **Таймлайн** — дата + время суток (Утро, День, Вечер, Ночь 22–06), воспроизведение видео, спектрограммы, визиты видов
- **UI** — React, Material UI, i18n (en/ru/zh), адаптивный, PWA (установка на экран, офлайн)
- **Погода** — OpenWeather или Home Assistant
- **Уведомления** — Telegram Bot API
- **MCP** — опциональный [Model Context Protocol](https://modelcontextprotocol.io/) для **авторизованных клиентов** (автоматизация, интеграции; см. [MCP setup](./docs/ru/mcp-setup.ru.md))

### Аналитика и экспорт
- **CSV/JSON** — скачать визиты для анализа в Excel/Python
- **eBird** — формат чеклиста для импорта в eBird.org
- **Сравнение с регионом** — ваши виды vs топ eBird региона (карточка на Overview)
- **PDF-отчёт** — месячная сводка: виды, топ-5, графики
- **Prometheus** — метрики `/metrics` для Grafana

### Гражданская наука
- **iNaturalist** — экспорт в один клик: кадр из видео → inaturalist.org/observations/upload
- **Неизвестные** — детекции с низкой уверенностью; фильтр по дате и времени суток (как в Записях)

### Интеграции
- **Webhook** — POST при каждой детекции (IFTTT, Zapier)
- **Песни птиц** — Xeno-canto на странице вида
- **Confidence по виду** — ниже порог для редких птиц
- **Исследования** — сбор датасетов, дообучение (см. [docs](./docs))

## Быстрый старт

**Docker (бесплатный образ):**
```bash
docker pull ghcr.io/gfermoto/birdlense-hub:latest
# или docker-compose — см. docs/user/install.md
```
UI: http://localhost:8085

**Установка:** [install](./docs/user/install.md) | **Сценарии:** [scenarios](./docs/user/scenarios.md) | **Возможности:** [features](./docs/user/features.md) | **Индекс:** [docs](./docs/ru/index.md)

Для одношагового запуска: **`./install.sh`** из корня репозитория (или **`make install`**). Скрипт ставит Docker при необходимости, создаёт `app/.env`, поднимает стек и проверяет health/readiness/status. Готовый образ: **`./install.sh --pull`** или **`make install-pull`**.

## Обучение baseline «поведения» (логистика, не YOLO)

### Готовые демо-веса (уже в репозитории и в Docker-образе)

Файл **`app/processor/models/behavior/behavior_logistic_export@v1.json`** коммитится в git и попадает в сборку. В **`default_config.yaml`** путь по умолчанию: **`models/behavior/behavior_logistic_export@v1.json`** (относительно корня `app/processor/`). Включите baseline в настройках и перезапустите процессор — **отдельно «скачивать веса» не нужно**, если вы не затирали этот путь в `user_config.yaml`.

Это **не** модель под вашу кормушку, а проверка цепочки; свои веса — только после обучения на своих CSV (ниже).

Это **отдельная маленькая модель** (файл JSON `behavior_logistic_export@v1`): по статистике кадров/детекций решает класс вроде `feeding` / `flying`. **Скачать готовую с Hugging Face нельзя** — классы и признаки ваши. Ниже — минимальный рецепт.

**Важно про интерфейс хаба:** разметить тысячи кадров для датасета или нажать «обучить» в UI **нельзя** — такого экрана нет. В UI доступны только: **включить/выключить** baseline, **путь к JSON**, пороги уверенности, и на **странице ролика** — ручная правка **уже записанной** метки для этой записи. Полный цикл обучения — на машине разработчика/оператора (CSV → `make …`).

### Что у вас должно быть на диске

1. **Папка с CSV** (можно вложенные каталоги). Скрипт берёт **все `*.csv`** рекурсивно.
2. **Имя файла** = условный ключ ролика (например `20250601_120000.csv` → ключ `20250601_120000`).
3. В **каждой строке CSV минимум 6 колонок** (нумерация с нуля). Скрипт для поведения использует только:
   - **колонка 4** — целое **id поведения** (должен совпасть с таксономией; по умолчанию `2` = feeding, `3` = flying и т.д. — см. `DEFAULT_TAXONOMY` в `scripts/ml_behavior_dataset_manifest.py`);
   - **колонка 5** — строка **id субъекта/трека** (хоть `a` в каждой строке);
   - **колонка 6** (если есть) — **название вида** (для признаков; можно пусто).

Столбцы 0–3 скрипт не интерпретирует для поведения — заполните нулями/временем, как удобно, лишь бы строка была длиной ≥ 6.

### Команды (скопировать и подставить пути)

Из **корня репозитория** BirdLense на машине, где стоит Python:

```bash
cd /путь/к/BirdLense

# 1) Манифест из ваших CSV
export ANNOTATIONS_ROOT=/абсолютный/путь/к/папке/с_csv
export OUT=/tmp/behavior_dataset_manifest.json
make ml-build-behavior-dataset

# 2) Обучение (один раз: pip install scikit-learn)
pip install 'scikit-learn>=1.3,<2'
export MANIFEST=/tmp/behavior_dataset_manifest.json
export EXPORT=/tmp/behavior_logistic_export@v1.json
export PRED=/tmp/behavior_predictions.json
make ml-train-behavior-baseline
```

В конце появится файл **`EXPORT`** — это и есть веса для хаба.

### Подключить к хабу

1. Скопируйте `EXPORT` на сервер в каталог процессора, например `app/processor/models/behavior/moi_vesa.json`.
2. **Настройки** → аккордеон **Процессор** → блок **«Распознавание поведения»** (`/settings#processor-behavior`): укажите путь **относительно корня `app/processor/`**, например `models/behavior/moi_vesa.json`.
3. Включите baseline, **сохраните**, **перезапустите контейнер процессора**.

Если своих CSV пока нет: в репозитории уже лежит демо-JSON; пересборка демо одной командой: **`make ml-train-behavior-synthetic-fixture`** (нужен `scikit-learn`). Подробнее: `app/processor/models/behavior/README.md`.

## Разработчикам

- **Окружение:** [локальная разработка](./docs/ru/local-dev.ru.md) — Docker, **Node.js 22** для `app/ui` (`.nvmrc`, `engines` в `package.json`), отдельный venv для MkDocs.
- **Тесты и CI:** [тестирование](./docs/ru/testing.ru.md) — `cd app && make test`, `cd app && make test-web`, E2E; тесты процессора требовательны к RAM.
- **Участие:** [CONTRIBUTING.ru.md](./CONTRIBUTING.ru.md).

### Первый прогон CI (как в Actions)

1. **Node.js ≥ 22** (`app/ui/package.json` → `engines`, `app/ui/.nvmrc`).
2. Из корня: **`make ci-local`** — при необходимости создаёт **`.venv-ci`** и запускает [`scripts/ci-full-local.sh`](./scripts/ci-full-local.sh) (тот же сценарий, что и [`.github/workflows/ci-pr.yml`](./.github/workflows/ci-pr.yml)).
3. Только web pytest (как в CI, `PYTHONPATH`):

```bash
cd app && PYTHONPATH="${PWD}:${PWD}/web" ../.venv-ci/bin/python -m pytest web/tests/ -q --tb=short
```

**Карта экранов настроек:** [RU](./archive/internal/docs-legacy/UI_SETTINGS_MAP.ru.md) · [EN](./archive/internal/docs-legacy/UI_SETTINGS_MAP.md)

## Требования

- **Docker** — x86/amd64
- **Go2RTC** — видеопотоки (отдельно или в Frigate), `http://IP:1984`
- **MQTT** (опционально) — события Frigate, детекции BirdNET

## Структура

| Путь | Описание |
|------|----------|
| [app/](./app) | Приложение (UI, API, processor) — один контейнер |
| [docs/](./docs) | Архитектура, конфиг, API, деплой, MCP |
| [scripts/](./scripts) | Деплой, restore-config, датасеты, проверка |

## Команды

Из корня репозитория:

| Команда | Описание |
|---------|----------|
| `make deploy` | Деплой на сервер (требуется `scripts/deploy.local.sh`) |
| `make verify` | Проверка `health` + `readiness` + `status` на `BASE_URL` или localhost |
| `make ci-local` | `scripts/ci-full-local.sh` — Bandit, pip-audit, Ruff, полный `pytest web/tests/`, версии доков, UI (codegen + Vitest + typecheck + lint + build), покрытие Settings UI, MkDocs strict (см. [CI and quality](./docs/contributor/ci-and-quality.md)) |
| `make ci-local-docker` | То же, плюс тесты в Docker-образе и Playwright smoke (тяжело; нужны веса processor) |
| `make build` | Сборка образа |
| `make start` | Запуск контейнера |
| `make stop` | Остановка |
| `make logs` | Логи |

**Ворота релиза (коротко):** [Definition of Done](./archive/internal/docs-legacy/DEFINITION_OF_DONE.ru.md) · [EN](./archive/internal/docs-legacy/DEFINITION_OF_DONE.md) — `make ci-local`, `verify-stack`, ручной смоук ~5 минут. Полный чеклист: [release-readiness](./release-readiness.md).

Из `app/`:

| Команда | Описание |
|---------|----------|
| `make pull` | Скачать и запустить готовый образ |
| `make setup` | Создать `.env` с секретами (вызывается автоматически) |

## Конфигурация

- **Настройки** → Видео: URL Go2RTC (`http://IP:1984`)
- **Настройки** → Камеры: имена потоков из Go2RTC
- **Настройки** → MQTT: брокер для Frigate/BirdNET
- Конфиг: `app/app_config/user_config.yaml`

## Безопасность

Для продакшена задайте в `app/.env` (или через `deploy.local.sh` при деплое):

| Переменная | Назначение |
|------------|------------|
| `FLASK_SECRET_KEY` | Сессия Flask (защита настроек) |
| `PROCESSOR_SECRET` | Защита API processor (заголовок `X-Processor-Token`) |
| `BIRDLENSE_ENV` | `production` — строгая проверка секретов |

Секреты генерируются автоматически при первом `make start` или `make pull`. См. `app/.env.example`.

## Лицензия

Docker-образ: CC BY-NC-ND 4.0 — использование и распространение только в некоммерческих целях. Без производных. См. [LICENSE](LICENSE).

## Благодарности

- [BirdLense](https://github.com/AleksandrRogachev94/BirdLense) от Aleksandr Rogachev — вдохновил на создание этого решения
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
- [BirdNET-Analyzer](https://github.com/kahst/BirdNET-Analyzer)
- [NABirds](https://dl.allaboutbirds.org/nabirds), [COCO](https://cocodataset.org/), [Open Images](https://storage.googleapis.com/openimages/web/index.html) (OIDv4 squirrel) — детектор
- [34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species), [iNaturalist](https://www.inaturalist.org/) (Europe) — классификатор (после объединения)
- [Material-UI](https://mui.com/)
- [OpenWeatherMap](https://openweathermap.org/)

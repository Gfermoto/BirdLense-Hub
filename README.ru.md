<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Hub Logo">
</p>

# BirdLense Hub

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](./CHANGELOG.md) [English](./README.md)

Мониторинг кормушки: компьютерное зрение и распознавание голосов для детекции, идентификации, записи и анализа птиц. Работает в Docker на x86, интегрируется с Go2RTC, Frigate, BirdNET через MQTT. Без облака — полностью локально.

**Исследовательский инструмент:** сбор датасетов из записей, скрипты обучения YOLO (NABirds, COCO), ноутбуки дообучения моделей. См. [docs/DATASET_TRAINING_PLAN.md](./docs/DATASET_TRAINING_PLAN.md).

### Модели

| Компонент | Версия | Дообучено на | Примечание |
|-----------|--------|--------------|------------|
| **Детектор** | YOLOv8n (Ultralytics 8.4.21) | NABirds + COCO birds + OIDv4 squirrel | Бинарный bird/squirrel |
| **Классификатор** | YOLOv8n-cls | NABirds (~400 видов) | **В основном североамериканские птицы** — европейских видов изначально не было |

**Европейские птицы:** пока используем Frigate Bird Classification + BirdNET; планируем дообучить на [birds-525](https://huggingface.co/datasets/34data/birds-525-species) и [iNaturalist Europe](https://api.inaturalist.org/v1/docs/).

**Планируется:** переобучение на YOLO11n (см. [UPGRADE_PLAN.md](./docs/UPGRADE_PLAN.md)).

**Пайплайн обучения:** 1) **Pretrain** на открытых датасетах (birds-525, iNaturalist Europe — для EU; NABirds, Birdsnap, CUB-200 — без EU-видов) → 2) **Fine-tune** на записях BirdLense. См. [docs/FINETUNE_OPEN_DATASETS.md](./docs/FINETUNE_OPEN_DATASETS.md).

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

- **Видео** — поток с IP-камер через [Go2RTC](https://github.com/AlexxIT/Go2RTC), оверлеи детекций в реальном времени
- **Детекция птиц** — кастомный YOLO + ByteTrack, двухэтапная стратегия (бинарный детектор + классификатор видов)
- **Аудио** — [BirdNET](https://github.com/kahst/BirdNET-Analyzer) через MQTT (BirdNET-Pi/Go)
- **Триггеры** — OpenCV motion, события Frigate, MQTT binary, ESPHome
- **Таймлайн** — воспроизведение видео, спектрограммы, визуализация треков, визиты видов
- **UI** — React, Material UI, i18n (en/ru), адаптивный
- **Погода** — OpenWeather или Home Assistant
- **Уведомления** — Telegram Bot API
- **MCP** — Model Context Protocol для внешних инструментов
- **Исследования** — подготовка датасетов (NABirds, COCO → YOLO), ноутбуки обучения, экспорт для дообучения моделей

## Быстрый старт

**Локально (Docker):**
```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make pull
```
UI: http://localhost:8085

**Деплой на сервер:** `make deploy` из корня репозитория.

**Установка:** [docs/INSTALL.md](./docs/INSTALL.md) | **Сценарии:** [docs/SCENARIOS.md](./docs/SCENARIOS.md)

При первом запуске `make setup` создаёт `app/.env` с `PROCESSOR_SECRET` и `FLASK_SECRET_KEY` автоматически.

## Требования

- **Docker** — x86/amd64
- **Go2RTC** — видеопотоки (отдельно или в Frigate), `http://IP:1984`
- **MQTT** (опционально) — события Frigate, детекции BirdNET

## Структура

| Путь | Описание |
|------|----------|
| [app/](./app) | Приложение (UI, API, processor) — один контейнер |
| [docs/](./docs) | Архитектура, конфиг, API, деплой, MCP, **план датасетов и обучения** |
| [scripts/](./scripts) | Деплой, **датасеты** (NABirds/COCO→YOLO), **обучение** (ноутбуки) |

**Скрипты для исследований:** `scripts/datasets/` — конвертация датасетов; `scripts/birds_train*.ipynb` — обучение моделей. Полный список: [docs/DATASET_SCRIPTS.md](./docs/DATASET_SCRIPTS.md).

## Команды

Из корня репозитория:

| Команда | Описание |
|---------|----------|
| `make deploy` | Деплой на сервер (см. [.cursor/rules/deploy.mdc](.cursor/rules/deploy.mdc)) |
| `make build` | Сборка образа |
| `make start` | Запуск контейнера |
| `make stop` | Остановка |
| `make logs` | Логи |

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

Для продакшена задайте в `app/.env`:

| Переменная | Назначение |
|------------|------------|
| `FLASK_SECRET_KEY` | Сессия Flask (защита настроек) |
| `PROCESSOR_SECRET` | Защита API processor (заголовок `X-Processor-Token`) |

Секреты генерируются автоматически при первом `make start` или `make pull`. См. `app/.env.example`.

## Лицензия

CC BY-NC-ND 4.0 — см. [LICENSE](LICENSE).

## Благодарности

- [BirdLense](https://github.com/AleksandrRogachev94/BirdLense) от Aleksandr Rogachev — вдохновил на создание этого решения
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
- [BirdNET-Analyzer](https://github.com/kahst/BirdNET-Analyzer)
- [NABirds](https://dl.allaboutbirds.org/nabirds)
- [Material-UI](https://mui.com/)
- [OpenWeatherMap](https://openweathermap.org/)

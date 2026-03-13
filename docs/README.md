# Документация BirdLense Hub

Навигация по документации. OpenAPI: [app/web/openapi.yaml](../app/web/openapi.yaml).

---

## Начало работы

| Документ | Описание |
|----------|----------|
| [INSTALL.md](./INSTALL.md) | **Установка** — Docker, готовый образ, первый запуск |
| [SCENARIOS.md](./SCENARIOS.md) | **Типичные сценарии** — минимальная установка, Frigate, BirdNET, Telegram, кормушка |
| [CONFIGURATION.md](./CONFIGURATION.md) | **Настройка** — конфиг, переменные окружения, секции |

---

## Система

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Компоненты, потоки данных, страницы UI |
| [API.md](./API.md) | Эндпоинты UI, System, Processor |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Деплой, deploy.local.sh, автодеплой |
| [VERSIONING.md](./VERSIONING.md) | Версионирование, CHANGELOG, политика обновлений |

---

## Тестирование

| Документ | Описание |
|----------|----------|
| [TESTING.md](./TESTING.md) | Unit, API, E2E тесты |
| [TESTING_DEPLOY.md](./TESTING_DEPLOY.md) | План тестирования после деплоя |

---

## Интеграции

| Документ | Описание |
|----------|----------|
| [MCP_SETUP.md](./MCP_SETUP.md) | Настройка MCP (Model Context Protocol) |
| [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md) | MQTT-топики Frigate, BirdNET |

---

## Исследования (датасеты, обучение)

| Документ | Описание |
|----------|----------|
| [COLAB_TRAINING.md](./COLAB_TRAINING.md) | **EU-модель** — пошаговая инструкция (Colab Free, fine-tune) |
| [EPOCHS_ANALYSIS.md](./EPOCHS_ANALYSIS.md) | 150 / 200 / 250 эпох — анализ для YOLO11n-cls + merged_cls |
| [DATASET_MERGE_FORMAT.md](./DATASET_MERGE_FORMAT.md) | Формат Scientific (Common), merge датасетов |
| [DATASET_SCRIPTS.md](./DATASET_SCRIPTS.md) | Справочник скриптов (download_hf_birds, merge и др.) |
| [FINETUNE_OPEN_DATASETS.md](./FINETUNE_OPEN_DATASETS.md) | Датасеты, оборудование, чек-лист |
| [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md) | Пайплайн: сбор → экспорт → обучение |
| [DATASET_SOURCES.md](./DATASET_SOURCES.md) | Ссылки на датасеты (HF, Zenodo) |
| [DATASET_UPLOAD_HF.md](./DATASET_UPLOAD_HF.md) | Загрузка merged_cls на Hugging Face |
| [HUGGINGFACE_HUB.md](./HUGGINGFACE_HUB.md) | Hugging Face Hub |
| [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) | Совместная разметка (планируется) |

---

## Прочее

| Документ | Описание |
|----------|----------|
| [ROADMAP.md](./ROADMAP.md) | План развития (HA autodiscovery, датасет из лучших кадров) |
| [UPGRADE_PLAN.md](./UPGRADE_PLAN.md) | План апгрейда (Ultralytics, зависимости) |

---

## Правила

- Новый документ — сразу добавить в таблицу выше
- В конце документа — секция «См. также» со ссылками
- Один источник истины: избегать дублирования

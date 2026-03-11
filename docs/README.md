# Документация BirdLense Hub

Навигация по документации. OpenAPI: [app/web/openapi.yaml](../app/web/openapi.yaml).

---

## Система

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Компоненты, потоки данных, страницы UI |
| [CONFIGURATION.md](./CONFIGURATION.md) | `default_config.yaml`, переменные окружения |
| [API.md](./API.md) | Эндпоинты UI, System, Processor |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Деплой, deploy.local.sh, автодеплой GitHub Actions |

---

## Тестирование

| Документ | Описание |
|----------|----------|
| [TESTING.md](./TESTING.md) | Unit, API, E2E тесты |
| [TESTING_DEPLOY.md](./TESTING_DEPLOY.md) | План тестирования после деплоя, MQTT, провокация событий |

---

## Интеграции

| Документ | Описание |
|----------|----------|
| [MCP_SETUP.md](./MCP_SETUP.md) | Настройка MCP для Cursor и AI-агентов |
| [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md) | MQTT-топики Frigate, BirdNET, форматы сообщений |
| [mcp.json.example](./mcp.json.example) | Шаблон конфига MCP |

---

## Исследования (датасеты, обучение)

| Документ | Описание |
|----------|----------|
| [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md) | Пайплайн: сбор → экспорт → разметка → обучение, MCP |
| [DATASET_SCRIPTS.md](./DATASET_SCRIPTS.md) | Справочник скриптов (NABirds, COCO, ноутбуки) |
| [DATASET_SOURCES.md](./DATASET_SOURCES.md) | Датасеты на Hugging Face (Birdsnap, CUB-200), Zenodo |
| [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) | Совместная разметка (подтвердить/исправить), куда уходят данные |

---

## Прочее

| Документ | Описание |
|----------|----------|
| [UPGRADE_PLAN.md](./UPGRADE_PLAN.md) | План апгрейда (Ultralytics, зависимости) |

---

## Правила

- Новый документ — сразу добавить в таблицу выше
- В конце документа — секция «См. также» со ссылками на связанные
- Один источник истины: избегать дублирования, ссылаться на основной документ

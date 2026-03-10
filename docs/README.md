# Документация BirdLense Hub

## Основные

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Архитектура: компоненты, потоки данных |
| [CONFIGURATION.md](./CONFIGURATION.md) | Описание `default_config.yaml` и env |
| [API.md](./API.md) | Обзор API, ссылка на OpenAPI |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Деплой на сервер, deploy.local.sh |

## Интеграции

| Документ | Описание |
|----------|----------|
| [MCP_SETUP.md](./MCP_SETUP.md) | Настройка MCP для Cursor и AI-агентов |
| [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md) | MQTT-топики (Frigate, BirdNET), форматы сообщений |

## Прочее

| Документ | Описание |
|----------|----------|
| [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md) | Сбор датасетов, обучение моделей, MCP |
| [DATASET_SCRIPTS.md](./DATASET_SCRIPTS.md) | Справочник скриптов датасетов |
| [UPGRADE_PLAN.md](./UPGRADE_PLAN.md) | План апгрейда (YOLO, зависимости) |
| [TESTING.md](./TESTING.md) | Unit, API и E2E тесты |
| [FORK_ANALYSIS.md](./FORK_ANALYSIS.md) | Сравнение с исходным проектом |
| [mcp.json.example](./mcp.json.example) | Шаблон конфига MCP для Cursor |

---

**OpenAPI:** [app/web/openapi.yaml](../app/web/openapi.yaml) — полная спецификация UI API.

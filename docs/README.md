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
| [FEATURES.md](./FEATURES.md) | **Полный список возможностей** — для разработчиков |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Компоненты, потоки данных, страницы UI |
| [API.md](./API.md) | Эндпоинты UI, System, Processor |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Деплой, deploy.local.sh, автодеплой |
| [VERSIONING.md](./VERSIONING.md) | Версионирование, CHANGELOG, политика обновлений |

---

## Тестирование

| Документ | Описание |
|----------|----------|
| [TESTING.md](./TESTING.md) | Unit, API, E2E тесты + проверка после деплоя |

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
| [TRAINING.md](./TRAINING.md) | **EU-модель** — обучение в Colab Free (пошагово) |
| [DATASETS.md](./DATASETS.md) | Форматы, скрипты, источники, модели |
| [HUGGINGFACE.md](./HUGGINGFACE.md) | Загрузка датасета и модели на HF |

---

## Прочее

| Документ | Описание |
|----------|----------|
| [ROADMAP.md](./ROADMAP.md) | План развития — апгрейды, фичи (HA, датасет), новые предложения |
| [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) | Совместная разметка (планируется) |

---

## Правила

- Новый документ — сразу добавить в таблицу выше
- В конце документа — секция «См. также» со ссылками
- Один источник истины: избегать дублирования

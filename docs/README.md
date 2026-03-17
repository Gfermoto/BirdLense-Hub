# Документация BirdLense Hub

Навигация по документации. Версия: **0.1.9**. OpenAPI: [app/web/openapi.yaml](../app/web/openapi.yaml).

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
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Деплой, deploy.local.sh, секреты, pre-built UI |
| [VERSIONING.md](./VERSIONING.md) | Версионирование, CHANGELOG, политика обновлений |

---

## Безопасность и доступ

| Документ | Описание |
|----------|----------|
| [ACCESS_CONTROL.md](./ACCESS_CONTROL.md) | Роли: Admin, Contributor, пароли настроек |
| [SECURITY.md](./SECURITY.md) | Анализ рисков, рекомендации для продакшена |
| [RECOVERY_CONFIG.md](./RECOVERY_CONFIG.md) | Восстановление доступа при потере пароля |

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
| [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md) | MQTT-топики Frigate, BirdNET, HA Autodiscovery |
| [TELEGRAM_CUSTOM_EMOJI.md](./TELEGRAM_CUSTOM_EMOJI.md) | Кастомные эмодзи в Telegram-уведомлениях |

---

## Исследования (датасеты, обучение)

| Документ | Описание |
|----------|----------|
| [TRAINING.md](./TRAINING.md) | **EU-модель** — обучение в Colab Free (пошагово) |
| [DATASETS.md](./DATASETS.md) | Форматы, скрипты, источники, модели |
| [HUGGINGFACE.md](./HUGGINGFACE.md) | Загрузка датасета и модели на HF |

---

## Разработка

| Документ | Описание |
|----------|----------|
| [AUTODOC.md](./AUTODOC.md) | Автодокументация (pdoc, TypeDoc, interrogate) |
| [LOCAL_DEV.md](./LOCAL_DEV.md) | Локальная сборка и тестирование (make local) |
| [ROADMAP.md](./ROADMAP.md) | План развития — апгрейды, фичи |
| [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) | Совместная разметка (планируется) |
| [DETECTION_SOURCES.md](./DETECTION_SOURCES.md) | Источники детекций: YOLO, Frigate, BirdNET |

---

## Архив

| Документ | Описание |
|----------|----------|
| [archive/README.md](./archive/README.md) | Завершённые ревью, мозговые штурмы, troubleshooting |

---

## Правила

- Новый документ — сразу добавить в таблицу выше
- В конце документа — секция «См. также» со ссылками
- Один источник истины: избегать дублирования

# BirdLense Hub — Документация

> **Версия 0.2.6** · OpenAPI: [YAML](./project/openapi.md) · **Интерактив:** [Redoc](./reference/openapi.ru.md) · **Сайт доков:** [gfermoto.github.io/BirdLense-Hub](https://gfermoto.github.io/BirdLense-Hub/)

[English](./README.md)

Этот каталог — **единый источник правды** для администраторов, интеграторов и контрибьюторов: запуск, устранение проблем, расширение проекта и **основа для сайта, вики или статей** (см. [OVERVIEW](./OVERVIEW.ru.md)).

---

## Три входа

| Путь | Задача | Куда идти |
|------|--------|-----------|
| **Запуск** | Docker, камеры, прод | [OVERVIEW](./OVERVIEW.ru.md) → [INSTALL](./INSTALL.md) → [SCENARIOS](./SCENARIOS.ru.md) |
| **Интеграции** | Frigate, BirdNET, MQTT, HA, Telegram | [SCENARIOS](./SCENARIOS.ru.md) → [CONFIGURATION](./CONFIGURATION.ru.md) |
| **Разработка** | Код, тесты, релизы | [LOCAL_DEV](./LOCAL_DEV.ru.md) → [TESTING](./TESTING.ru.md) → [Contributing](./project/contributing.md) |

---

## Продукт и справка

| Тема | English | Русский |
|------|---------|---------|
| **Краткое описание** (About на GitHub, анонсы) | [EN](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SHORT_DESCRIPTION.md) | [RU](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SHORT_DESCRIPTION.ru.md) |
| **О проекте** (лендинг, статьи) | [OVERVIEW](./OVERVIEW.md) | [RU](./OVERVIEW.ru.md) |
| **Установка и деплой** | [INSTALL](./INSTALL.md) | [RU](./INSTALL.ru.md) |
| **Сценарии** | [SCENARIOS](./SCENARIOS.md) | [RU](./SCENARIOS.ru.md) |
| **Конфигурация** | [CONFIGURATION](./CONFIGURATION.md) | [RU](./CONFIGURATION.ru.md) |
| **Термины (Hub, Frigate, слияние…)** | [GLOSSARY](./GLOSSARY.md) | [RU](./GLOSSARY.ru.md) |
| **Возможности и API** | [FEATURES](./FEATURES.md) | [RU](./FEATURES.ru.md) |
| **Архитектура** | [ARCHITECTURE](./ARCHITECTURE.md) | [RU](./ARCHITECTURE.ru.md) |
| **API** | [API](./API.md) · [OpenAPI Redoc](./reference/openapi.md) | [RU](./API.ru.md) · [Redoc](./reference/openapi.ru.md) |
| **Версионирование** | [VERSIONING](./VERSIONING.md) | — |

---

## Безопасность и эксплуатация

| Тема | Документ |
|------|----------|
| Доступ и пароли | [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md) |
| Риски и рекомендации | [SECURITY](./SECURITY.md) |
| Восстановление конфига | [RECOVERY_CONFIG](./RECOVERY_CONFIG.ru.md) |
| Не работает | [TROUBLESHOOTING](./TROUBLESHOOTING.ru.md) |

---

## Качество и инструменты

| Тема | Документ |
|------|----------|
| Тесты и проверка после деплоя | [TESTING](./TESTING.ru.md) |
| MCP | [MCP_SETUP](./MCP_SETUP.ru.md) |

---

## ML, данные, план

| Тема | English | Русский |
|------|---------|---------|
| Обучение моделей | [TRAINING](./TRAINING.md) | [RU](./TRAINING.ru.md) |
| Датасеты и скрипты | [DATASETS](./DATASETS.md) | [RU](./DATASETS.ru.md) |
| Версионирование | [VERSIONING](./VERSIONING.md) | [RU](./VERSIONING.ru.md) |
| Roadmap | [ROADMAP](./ROADMAP.md) | [RU](./ROADMAP.ru.md) |

---

## Мета

| Тема | Документ |
|------|----------|
| Как вести документацию | [Documentation](./Documentation.ru.md) |
| Анализ безопасности (`docs/`) | [SECURITY](./SECURITY.md) · [RU](./SECURITY.ru.md) |
| Чеклист open-source | [OPEN_SOURCE_PREP](./OPEN_SOURCE_PREP.md) · [RU](./OPEN_SOURCE_PREP.ru.md) |
| Управление и внешний наблюдатель | [GOVERNANCE.ru.md](./GOVERNANCE.ru.md) · [EN](./GOVERNANCE.md) |
| **Настройка GitHub через gh** | [GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md) · [EN](./GITHUB_SETUP_GH.md) |
| **Wiki и отчёты CI** | [WIKI_AUTOMATION.ru.md](./WIKI_AUTOMATION.ru.md) · [EN](./WIKI_AUTOMATION.md) |
| Статус переводов | [I18N_STATUS](./I18N_STATUS.md) |
| **Разделы ↔ файлы** (сверка с `mkdocs.yml`) | [SITE_MAP](./SITE_MAP.ru.md) · [EN](./SITE_MAP.md) |
| **MkDocs и GitHub Pages** | [Documentation.ru.md](./Documentation.ru.md) § *Статический сайт* |
| Архив | [archive/README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/docs/archive/README.md) (в репозитории; не входит в сборку MkDocs) |

---

## Команды (из корня репозитория)

| Цель | Команда |
|------|---------|
| Локально | `cd app && make local` → http://localhost:8085 |
| Web-тесты | `cd app && make test-web` |
| Полный индекс | Вы здесь ✓ |
| Предпросмотр статического сайта | `pip install -r requirements-docs.txt && mkdocs serve` ([подробности](./Documentation.ru.md)) |

Деплой на сервер: [INSTALL](./INSTALL.ru.md).

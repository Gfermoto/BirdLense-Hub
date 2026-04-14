# BirdLense Hub — Документация

> **Версия 0.3.4** (источник правды: корневой файл `VERSION`) · OpenAPI: [YAML](./project/openapi.md) · **Интерактив:** [Redoc](./reference/openapi.ru.md) · **Сайт доков:** [gfermoto.github.io/BirdLense-Hub](https://gfermoto.github.io/BirdLense-Hub/)

[English](./README.md)

Этот каталог — **единый источник правды** для администраторов, интеграторов и контрибьюторов: запуск, устранение проблем, расширение проекта и **основа для сайта, вики или статей** (см. [OVERVIEW](./OVERVIEW.ru.md)).

---

## Три входа

| Путь | Задача | Куда идти |
|------|--------|-----------|
| **Запуск** | Docker, камеры, прод | [QUICKSTART](./QUICKSTART.md) → [OVERVIEW](./OVERVIEW.ru.md) → [INSTALL](./INSTALL.ru.md) → [SCENARIOS](./SCENARIOS.ru.md) |
| **Интеграции** | Frigate, BirdNET, MQTT, HA, Telegram | [SCENARIOS](./SCENARIOS.ru.md) → [CONFIGURATION](./CONFIGURATION.ru.md) |
| **Разработка** | Код, тесты, релизы | [QUICKSTART](./QUICKSTART.md) → [Структура репозитория](./REPOSITORY_LAYOUT.ru.md) → [LOCAL_DEV](./LOCAL_DEV.ru.md) → [TESTING](./TESTING.ru.md) → [CI и качество](./CI_AND_QUALITY.ru.md) → [Contributing](./project/contributing.md) |

---

## Продукт и справка

| Тема | English | Русский |
|------|---------|---------|
| **Краткое описание** (About на GitHub, анонсы) | [EN](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SHORT_DESCRIPTION.md) | [RU](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SHORT_DESCRIPTION.ru.md) |
| **О проекте** (лендинг, статьи) | [OVERVIEW](./OVERVIEW.md) | [RU](./OVERVIEW.ru.md) |
| **Установка и деплой** | [INSTALL](./INSTALL.md) | [RU](./INSTALL.ru.md) |
| **Быстрый старт и проверка** | [QUICKSTART](./QUICKSTART.md) | — |
| **Сценарии** | [SCENARIOS](./SCENARIOS.md) | [RU](./SCENARIOS.ru.md) |
| **Конфигурация** | [CONFIGURATION](./CONFIGURATION.md) | [RU](./CONFIGURATION.ru.md) |
| **Термины (Hub, Frigate, слияние…)** | [GLOSSARY](./GLOSSARY.md) | [RU](./GLOSSARY.ru.md) |
| **Возможности и API** | [FEATURES](./FEATURES.md) | [RU](./FEATURES.ru.md) |
| **Архитектура** | [ARCHITECTURE](./ARCHITECTURE.md) | [RU](./ARCHITECTURE.ru.md) |
| **API** | [API](./API.md) · [OpenAPI Redoc](./reference/openapi.md) | [RU](./API.ru.md) · [Redoc](./reference/openapi.ru.md) |
| **Версионирование** | [VERSIONING](./VERSIONING.md) | [RU](./VERSIONING.ru.md) |
| **Чеклист деплоя на сервер** | [DEPLOY_SERVER](./DEPLOY_SERVER.md) | [RU](./DEPLOY_SERVER.ru.md) |
| **Плитки Heimdall** | [HEIMDALL](./HEIMDALL.md) | [RU](./HEIMDALL.ru.md) |

---

## Безопасность и эксплуатация

| Тема | Документ |
|------|----------|
| Доступ и пароли | [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md) |
| Риски и рекомендации | [SECURITY](./SECURITY.md) |
| Восстановление конфига | [RECOVERY_CONFIG](./RECOVERY_CONFIG.ru.md) |
| Не работает | [TROUBLESHOOTING](./TROUBLESHOOTING.ru.md) |
| Runbooks для операторов | [RUNBOOKS](./RUNBOOKS.md) |

---

## Качество и инструменты

| Тема | Документ |
|------|----------|
| **CI на PR** (Bandit, pip-audit, Ruff, pytest, сборка UI, MkDocs, Docker-тесты, Playwright smoke) | [TESTING.ru.md](./TESTING.ru.md) (раздел 1) |
| **Политика CI** (Ruff format, игноры pip-audit, npm audit, OpenAPI→TS) | [CI_AND_QUALITY.ru.md](./CI_AND_QUALITY.ru.md) |
| Тесты и проверка после деплоя | [TESTING](./TESTING.ru.md) |
| Журнал автоматической верификации (релизы / критические фиксы) | [VERIFICATION](./VERIFICATION.ru.md) |
| MCP (Model Context Protocol — автоматизация и интеграции) | [MCP_SETUP](./MCP_SETUP.ru.md) |

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
| **Структура репозитория** (онбординг) | [REPOSITORY_LAYOUT](./REPOSITORY_LAYOUT.md) · [RU](./REPOSITORY_LAYOUT.ru.md) |
| Как вести документацию | [Documentation](./Documentation.ru.md) |
| Анализ безопасности (`docs/`) | [SECURITY](./SECURITY.md) · [RU](./SECURITY.ru.md) |
| **Ротация секретов (прод)** | [SECRETS_ROTATION.ru.md](./SECRETS_ROTATION.ru.md) · [EN](./SECRETS_ROTATION.md) |
| Чеклист open-source | [OPEN_SOURCE_PREP](./OPEN_SOURCE_PREP.md) · [RU](./OPEN_SOURCE_PREP.ru.md) |
| Управление и внешний наблюдатель | [GOVERNANCE.ru.md](./GOVERNANCE.ru.md) · [EN](./GOVERNANCE.md) |
| **Issues, доска и процесс** | [ROADMAP.ru.md](./ROADMAP.ru.md) (*Триаж*) · [EN](./ROADMAP.md); корневой [CONTRIBUTING.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.ru.md) |
| **Настройка GitHub через gh** | [GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md) · [EN](./GITHUB_SETUP_GH.md) |
| **Wiki и отчёты CI** | [WIKI_AUTOMATION.ru.md](./WIKI_AUTOMATION.ru.md) · [EN](./WIKI_AUTOMATION.md) |
| Статус переводов | [I18N_STATUS](./I18N_STATUS.md) |
| **Разделы ↔ файлы** (сверка с `mkdocs.yml`) | [SITE_MAP](./SITE_MAP.ru.md) · [EN](./SITE_MAP.md) |
| **MkDocs и GitHub Pages** | [Documentation.ru.md](./Documentation.ru.md) (*Статический сайт*) |
| Архив | [archive/README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/docs/archive/README.md) (в репозитории; не входит в сборку MkDocs) |

---

## Команды (из корня репозитория)

| Цель | Команда |
|------|---------|
| Локально | `cd app && make local` → http://localhost:8085 |
| Общая проверка (smoke) | `make verify` (или `BASE_URL=http://ХОСТ:8085 make verify`) |
| Web-тесты | `cd app && make test-web` |
| Telegram proxy autorotate | `make proxy-rotation-install` (статус: `make proxy-rotation-status`) |
| Полный индекс | Эта страница |
| Предпросмотр статического сайта | `pip install -r requirements-docs.txt && mkdocs serve` ([подробности](./Documentation.ru.md)) |

Деплой на сервер: [INSTALL](./INSTALL.ru.md).

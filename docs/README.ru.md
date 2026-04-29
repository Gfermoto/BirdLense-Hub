# BirdLense Hub — Документация

> **Версия 0.3.7** (источник правды: корневой файл `VERSION`) · OpenAPI: [YAML](./project/openapi.md) · **Интерактив:** [Redoc](./reference/openapi.ru.md) · **Сайт доков:** [gfermoto.github.io/BirdLense-Hub](https://gfermoto.github.io/BirdLense-Hub/)

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
| **Быстрый старт и проверка** | [QUICKSTART](./QUICKSTART.md) | [RU](./QUICKSTART.ru.md) |
| **Сценарии** | [SCENARIOS](./SCENARIOS.md) | [RU](./SCENARIOS.ru.md) |
| **Конфигурация** | [CONFIGURATION](./CONFIGURATION.md) · [Policy](./CONFIGURATION_POLICY.md) | [RU](./CONFIGURATION.ru.md) · [Политика](./CONFIGURATION_POLICY.ru.md) |
| **Термины (Hub, Frigate, слияние…)** | [GLOSSARY](./GLOSSARY.md) | [RU](./GLOSSARY.ru.md) |
| **Доменный контракт** (trigger/clip/visit/review/taxon) | [DOMAIN_CONTRACT](./DOMAIN_CONTRACT.md) | [RU](./DOMAIN_CONTRACT.ru.md) |
| **Возможности и API** | [FEATURES](./FEATURES.md) | [RU](./FEATURES.ru.md) |
| **Архитектура** | [ARCHITECTURE](./ARCHITECTURE.md) | [RU](./ARCHITECTURE.ru.md) |
| **API** | [API](./API.md) · [OpenAPI Redoc](./reference/openapi.md) | [RU](./API.ru.md) · [Redoc](./reference/openapi.ru.md) |
| **Версионирование** | [VERSIONING](./VERSIONING.md) | [RU](./VERSIONING.ru.md) |
| **Чеклист деплоя на сервер** | [DEPLOY_SERVER](./DEPLOY_SERVER.md) | [RU](./DEPLOY_SERVER.ru.md) |
| **Release readiness** | [RELEASE_READINESS](./RELEASE_READINESS.md) | [RU](./RELEASE_READINESS.ru.md) |
| **Definition of Done (ворота релиза)** | [DEFINITION_OF_DONE](./DEFINITION_OF_DONE.md) | [RU](./DEFINITION_OF_DONE.ru.md) |
| **Карта настроек UI** | [UI_SETTINGS_MAP](./UI_SETTINGS_MAP.md) | [RU](./UI_SETTINGS_MAP.ru.md) |
| **Каноническая UX-карта** (роли, маршруты, сценарии) | [UX_CANONICAL_MAP](./UX_CANONICAL_MAP.md) | [RU](./UX_CANONICAL_MAP.ru.md) |
| **Производительность процессора** | [PROCESSOR_PERFORMANCE](./PROCESSOR_PERFORMANCE.md) | [RU](./PROCESSOR_PERFORMANCE.ru.md) |
| **Инвентаризация триггеров / Frigate** | [CONFIGURATION_TRIGGERS_INVENTORY](./CONFIGURATION_TRIGGERS_INVENTORY.md) | [RU](./CONFIGURATION_TRIGGERS_INVENTORY.ru.md) |
| **Ошибки API и security baseline** | [API_ERRORS](./API_ERRORS.md) | [RU](./API_ERRORS.ru.md) |
| **Трекер эпиков Hub (GitHub)** | [HUB_EPICS_TRACKER](./HUB_EPICS_TRACKER.md) | [RU](./HUB_EPICS_TRACKER.ru.md) |
| **Плитки Heimdall** | [HEIMDALL](./HEIMDALL.md) | [RU](./HEIMDALL.ru.md) |

---

## Безопасность и эксплуатация

| Тема | Документ |
|------|----------|
| Доступ и пароли | [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md) · [EN](./ACCESS_CONTROL.md) |
| Риски и рекомендации | [SECURITY.ru](./SECURITY.ru.md) · [EN](./SECURITY.md) |
| Восстановление конфига | [RECOVERY_CONFIG](./RECOVERY_CONFIG.ru.md) |
| Не работает | [TROUBLESHOOTING](./TROUBLESHOOTING.ru.md) |
| Runbooks для операторов | [RUNBOOKS.ru.md](./RUNBOOKS.ru.md) |

---

## Качество и инструменты

| Тема | Документ |
|------|----------|
| **CI на PR** (Bandit, pip-audit, Ruff, pytest, сборка UI, MkDocs, Docker-тесты, Playwright smoke) | [TESTING.ru.md](./TESTING.ru.md) §1 |
| **Локальный полный CI и политика** (`make ci-local`, `make ci-local-docker`, форматы, аудиты, OpenAPI→TS) | [CI_AND_QUALITY.ru.md](./CI_AND_QUALITY.ru.md) · [EN](./CI_AND_QUALITY.md) |
| **Тесты, E2E, проверки после деплоя** | [TESTING](./TESTING.ru.md) · [EN](./TESTING.md) |
| Журнал автоматической верификации (релизы / критические фиксы) | [VERIFICATION](./VERIFICATION.ru.md) |
| Проверка доменных инвариантов | `GET /api/ui/system/domain-health` + [DOMAIN_CONTRACT](./DOMAIN_CONTRACT.ru.md) |
| MCP (Model Context Protocol — автоматизация и интеграции) | [MCP_SETUP](./MCP_SETUP.ru.md) |
| **UX: тултипы и подсказки** (контрибьюторы) | [UX_TOOLTIPS.ru.md](./UX_TOOLTIPS.ru.md) · [EN](./UX_TOOLTIPS.md) |

---

## ML, данные, план

| Тема | English | Русский |
|------|---------|---------|
| Обучение моделей | [TRAINING](./TRAINING.md) | [RU](./TRAINING.ru.md) |
| Цикл качества ML (операторы) | — | [только RU](./ML_QUALITY_LOOP.ru.md) |
| Эпик CV / ML (GitHub) | [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) | [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) |
| Контракт подготовки CV / ML | [CV_ML_PREP](./CV_ML_PREP.md) | [RU](./CV_ML_PREP.ru.md) |
| Фазы roadmap CV / ML | [CV_ML_ROADMAP_PHASES](./CV_ML_ROADMAP_PHASES.md) | [RU](./CV_ML_ROADMAP_PHASES.ru.md) |
| ML: репозиторий и ваши шаги | [ML_OPERATOR_HANDOFF](./ML_OPERATOR_HANDOFF.md) | [RU](./ML_OPERATOR_HANDOFF.ru.md) |
| Датасеты и скрипты | [DATASETS](./DATASETS.md) | [RU](./DATASETS.ru.md) |
| Датасет детектора (HF, ZIP) | [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) | [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) |
| Детектор в Colab | [ML_DETECTOR_COLAB](./ML_DETECTOR_COLAB.md) | [RU](./ML_DETECTOR_COLAB.ru.md) |
| Декод видео (#373) | [CV_ML_DECODE](./CV_ML_DECODE.md) | [RU](./CV_ML_DECODE.ru.md) |
| Active learning (#369) | [ACTIVE_LEARNING](./ACTIVE_LEARNING.md) | [RU](./ACTIVE_LEARNING.ru.md) |
| Re-ID (#374) | [REID_ROADMAP](./REID_ROADMAP.md) | [RU](./REID_ROADMAP.ru.md) |
| Федеративное обучение (#375) | [FEDERATED_LEARNING](./FEDERATED_LEARNING.md) | [RU](./FEDERATED_LEARNING.ru.md) |
| Версионирование | [VERSIONING](./VERSIONING.md) | [RU](./VERSIONING.ru.md) |
| Roadmap | [ROADMAP](./ROADMAP.md) | [RU](./ROADMAP.ru.md) |

---

## Мета

Боковое меню статического сайта задаётся корневым `mkdocs.yml`. Сопоставление **файл ↔ пункт меню** (порядок как **Мета** и **Репозиторий (канонические файлы)**) — [SITE_MAP.ru.md](./SITE_MAP.ru.md) · [EN](./SITE_MAP.md).

### Мета (в `nav` → Meta)

| Тема | Документ |
|------|----------|
| **Трекер эпиков Hub (GitHub)** | [HUB_EPICS_TRACKER.ru.md](./HUB_EPICS_TRACKER.ru.md) · [EN](./HUB_EPICS_TRACKER.md) |
| **Структура репозитория** (онбординг) | [REPOSITORY_LAYOUT.ru.md](./REPOSITORY_LAYOUT.ru.md) · [EN](./REPOSITORY_LAYOUT.md) |
| **Журнал верификации релизов** | [VERIFICATION.ru.md](./VERIFICATION.ru.md) · [EN](./VERIFICATION.md) |
| Как вести документацию | [Documentation.ru.md](./Documentation.ru.md) · [EN](./Documentation.md) |
| **Карта сайта** (сверка с `nav`) | [SITE_MAP.ru.md](./SITE_MAP.ru.md) · [EN](./SITE_MAP.md) |
| Статус переводов | [I18N_STATUS.ru.md](./I18N_STATUS.ru.md) · [EN](./I18N_STATUS.md) |
| **Ротация секретов (прод)** | [SECRETS_ROTATION.ru.md](./SECRETS_ROTATION.ru.md) · [EN](./SECRETS_ROTATION.md) |
| Анализ безопасности | [SECURITY.ru.md](./SECURITY.ru.md) · [EN](./SECURITY.md) |
| Чеклист open-source | [OPEN_SOURCE_PREP.ru.md](./OPEN_SOURCE_PREP.ru.md) · [EN](./OPEN_SOURCE_PREP.md) |
| Управление и внешний наблюдатель | [GOVERNANCE.ru.md](./GOVERNANCE.ru.md) · [EN](./GOVERNANCE.md) |
| **Настройка GitHub через gh** | [GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md) · [EN](./GITHUB_SETUP_GH.md) |
| **Wiki и отчёты CI** | [WIKI_AUTOMATION.ru.md](./WIKI_AUTOMATION.ru.md) · [EN](./WIKI_AUTOMATION.md) |

### Связанный процесс (не отдельные строки меню)

| Тема | Документ |
|------|----------|
| **Issues, доска и roadmap** | [ROADMAP.ru.md](./ROADMAP.ru.md) (*Триаж*) · [EN](./ROADMAP.md); корневой [CONTRIBUTING.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.ru.md) |

### Репозиторий (заглушки `docs/project/`)

| Тема | Документ |
|------|----------|
| Contributing | [project/contributing.md](./project/contributing.md) → корневой **CONTRIBUTING** на GitHub |
| Политика безопасности | [project/security-policy.md](./project/security-policy.md) → корневой **SECURITY** |
| Code of Conduct | [project/code-of-conduct.md](./project/code-of-conduct.md) → корень репозитория |
| Changelog | [project/changelog.md](./project/changelog.md) → корневой **CHANGELOG** |
| OpenAPI (YAML) | [project/openapi.md](./project/openapi.md) → `app/web/openapi.yaml` |
| Корневой README | [project/root-readme.md](./project/root-readme.md) → корневой **README** |

### Публикация и архив

| Тема | Документ |
|------|----------|
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
| Регенерация блока путей OpenAPI | `python3 scripts/merge_openapi_fragments.py` из корня репозитория (смотреть diff) — [подробности](./Documentation.ru.md#openapi-spec-maintenance) |
| Полный индекс | Эта страница |
| Предпросмотр статического сайта | `pip install -r requirements-docs.txt && mkdocs serve` ([подробности](./Documentation.ru.md)) |

Деплой на сервер: [INSTALL](./INSTALL.ru.md).

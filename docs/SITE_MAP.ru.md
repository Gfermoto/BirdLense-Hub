# Карта сайта документации (рекомендация)

Сопоставление разделов и файлов и проверка, что `nav` в [`mkdocs.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml) не разъехался. Сайт собирается **MkDocs Material** из корня репозитория.

[English](./SITE_MAP.md)

---

## Верхнее меню

| Пункт | Файл | Примечание |
|-------|------|------------|
| Обзор | [OVERVIEW.ru.md](./OVERVIEW.ru.md) | Первый пункт MkDocs (секция «Русский») |
| Оглавление | [README.ru.md](./README.ru.md) | Таблицы по темам и входы |
| GitHub | внешняя ссылка | Репозиторий |

---

## Сайдбар — «Использование»

| Страница | Источник |
|----------|----------|
| Установка | [INSTALL.ru.md](./INSTALL.ru.md) |
| Сценарии | [SCENARIOS.ru.md](./SCENARIOS.ru.md) |
| Конфигурация | [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) |
| Возможности | [FEATURES.ru.md](./FEATURES.ru.md) |
| Проблемы | [TROUBLESHOOTING.ru.md](./TROUBLESHOOTING.ru.md) |
| Восстановление конфига | [RECOVERY_CONFIG.ru.md](./RECOVERY_CONFIG.ru.md) |
| Глоссарий | [GLOSSARY.ru.md](./GLOSSARY.ru.md) |

---

## Сайдбар — «Разработка и интеграции»

| Страница | Источник |
|----------|----------|
| Архитектура | [ARCHITECTURE.ru.md](./ARCHITECTURE.ru.md) |
| HTTP API | [API.ru.md](./API.ru.md) + OpenAPI |
| OpenAPI (Redoc) | [reference/openapi.ru.md](./reference/openapi.ru.md) · [EN](./reference/openapi.md) |
| Доступ и роли | [ACCESS_CONTROL.ru.md](./ACCESS_CONTROL.ru.md) |
| MCP | [MCP_SETUP.ru.md](./MCP_SETUP.ru.md) |
| Локальная разработка | [LOCAL_DEV.ru.md](./LOCAL_DEV.ru.md) |
| CodeQL (CI) | [CODEQL.ru.md](./CODEQL.ru.md) |
| Тесты | [TESTING.ru.md](./TESTING.ru.md) |
| Доступность | [A11Y.ru.md](./A11Y.ru.md) · [EN](./A11Y.md) |

---

## Сайдбар — «ML и проект»

| Страница | Источник |
|----------|----------|
| Обучение | [TRAINING.md](./TRAINING.md) |
| Датасеты | [DATASETS.md](./DATASETS.md) |
| Версионирование | [VERSIONING.md](./VERSIONING.md) |
| Roadmap | [ROADMAP.md](./ROADMAP.md) |

---

## Мета

| Страница | Источник |
|----------|----------|
| Contributing | [project/contributing.md](./project/contributing.md) → корневой `CONTRIBUTING.md` на GitHub |
| Политика безопасности | [project/security-policy.md](./project/security-policy.md) → корневой `SECURITY.md` |
| Code of Conduct | [project/code-of-conduct.md](./project/code-of-conduct.md) → корень репозитория |
| Changelog | [project/changelog.md](./project/changelog.md) → корневой `CHANGELOG.md` |
| OpenAPI YAML | [project/openapi.md](./project/openapi.md) → `app/web/openapi.yaml` |
| Корневой README | [project/root-readme.md](./project/root-readme.md) |
| Структура репозитория | [REPOSITORY_LAYOUT.ru.md](./REPOSITORY_LAYOUT.ru.md) · [EN](./REPOSITORY_LAYOUT.md) |
| Правила доков | [Documentation.ru.md](./Documentation.ru.md) |
| Анализ безопасности | [SECURITY.ru.md](./SECURITY.ru.md) |
| Ротация секретов (прод) | [SECRETS_ROTATION.ru.md](./SECRETS_ROTATION.ru.md) · [EN](./SECRETS_ROTATION.md) |
| Подготовка к open-source | [OPEN_SOURCE_PREP.ru.md](./OPEN_SOURCE_PREP.ru.md) |
| Локализация | [I18N_STATUS.md](./I18N_STATUS.md) |
| Управление и наблюдатель | [GOVERNANCE.ru.md](./GOVERNANCE.ru.md) · [EN](./GOVERNANCE.md) |
| Issues, доска и roadmap | [ROADMAP.ru.md](./ROADMAP.ru.md) § Триаж · [EN](./ROADMAP.md); корень репо CONTRIBUTING.ru.md |
| Настройка GitHub (`gh`) | [GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md) · [EN](./GITHUB_SETUP_GH.md) |
| Wiki и отчёты CI | [WIKI_AUTOMATION.ru.md](./WIKI_AUTOMATION.ru.md) · [EN](./WIKI_AUTOMATION.md) |

**Генератор:** [mkdocs.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml) в корне репозитория (MkDocs Material); русские страницы — отдельная секция в `nav`.

---

## Два языка

Дублировать структуру для `/ru/` или держать пары `*.md` / `*.ru.md` — см. [I18N_STATUS.md](./I18N_STATUS.md).

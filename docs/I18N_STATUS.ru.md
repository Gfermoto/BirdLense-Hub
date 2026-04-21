# Документация — статус двуязычия

Основной язык — **английский** (`*.md`). Русский — **вторичный** (`*.ru.md`).

[English](./I18N_STATUS.md)

---

## Подход

1. **Структура и переписывание** — информационная архитектура, сценарии читателя, таблицы вместо простыней (технический писатель).
2. **Сначала EN** — выкладываем выверенный `DOC.md` (база для сайта и сообщества).
3. **RU** — зеркало в `DOC.ru.md` по мере необходимости (переводчик / мейнтейнер).

По умолчанию это не «перевести ради перевода»: страницы должны оставаться **полезными как разделы сайта** и **сырьём для статей**.

## Зачистка архива (сделано)

Из `archive/` убраны: ROLLBACK_LOST_FEATURES, SYSTEM_UI_AND_FRIGATE_REFERENCE, COLLABORATIVE_LABELING, UX_IMPROVEMENTS, FRIGATE_EVENT_LOSS_AUDIT (содержимое ушло в TROUBLESHOOTING). Сокращён: REACT_19_MIGRATION.

## Схема имён

- `DOC.md` — английский (основной)
- `DOC.ru.md` — русский

В начале каждой пары — ссылка на другую локаль: `[English](./DOC.md)` / `[Русский](./DOC.ru.md)`.

## Опубликованный сайт (`mkdocs.yml`)

При **добавлении, удалении или переименовании** опубликованной страницы в `docs/`: обновите **`nav`** в корневом **`mkdocs.yml`**, порядок блоков **Мета** и **Репозиторий (канонические файлы)** в [SITE_MAP.ru.md](./SITE_MAP.ru.md) / [SITE_MAP.md](./SITE_MAP.md), при необходимости таблицы в [README.ru.md](./README.ru.md) и [README.md](./README.md), затем **одну и ту же строку** в таблицах ниже и в [I18N_STATUS.md](./I18N_STATUS.md).

## Статус

| Документ | EN | RU |
|----------|:--:|:--:|
| **Корень репозитория** | | |
| README | ✅ | ✅ |
| CONTRIBUTING | ✅ | ✅ |
| CODE_OF_CONDUCT | ✅ | ✅ |
| SECURITY | ✅ | ✅ |
| **docs/** | | |
| README (хаб) | ✅ | ✅ |
| QUICKSTART | ✅ | ✅ |
| REPOSITORY_LAYOUT | ✅ | ✅ |
| OVERVIEW (история / лендинг) | ✅ | ✅ |
| INSTALL | ✅ | ✅ |
| DEPLOY_SERVER (чеклист) | ✅ | ✅ |
| Documentation (мета-гайд) | ✅ | ✅ |
| SCENARIOS | ✅ | ✅ |
| CONFIGURATION | ✅ | ✅ |
| HEIMDALL (плитки) | ✅ | ✅ |
| GLOSSARY | ✅ | ✅ |
| FEATURES | ✅ | ✅ |
| TESTING | ✅ | ✅ |
| TROUBLESHOOTING | ✅ | ✅ |
| RUNBOOKS | ✅ | ✅ |
| DOMAIN_CONTRACT | ✅ | ✅ |
| RELEASE_READINESS | ✅ | ✅ |
| CI_AND_QUALITY | ✅ | ✅ |
| LOCAL_DEV | ✅ | ✅ |
| CODEQL (CI) | ✅ | ✅ |
| A11Y | ✅ | ✅ |
| UX_TOOLTIPS | ✅ только EN | — |
| SETTINGS_TRIGGERS_PHASE2 (черновик) | ✅ только EN | — |
| UX_UNKNOWN_VIDEO_CORRECTION | ✅ одна страница | — |
| ARCHITECTURE | ✅ | ✅ |
| API | ✅ | ✅ |
| reference/openapi (врезка Redoc) | ✅ | ✅ |
| MCP_SETUP | ✅ | ✅ |
| ACCESS_CONTROL | ✅ | ✅ |
| RECOVERY_CONFIG | ✅ | ✅ |
| SITE_MAP (разделы ↔ файлы, `nav`) | ✅ | ✅ |
| UX_CANONICAL_MAP (роли / маршруты) | ✅ | ✅ |
| TRAINING | ✅ | ✅ |
| ML_QUALITY_LOOP | — | ✅ (только RU) |
| DATASETS | ✅ | ✅ |
| ROADMAP (в т.ч. Issues / доска) | ✅ | ✅ |
| VERSIONING | ✅ | ✅ |
| VERIFICATION (журнал проверок релиза) | ✅ | ✅ |
| PRE_IMPLEMENTATION_UNKNOWN_TIMELINE (мейнтейнер; вне MkDocs) | ✅ | ✅ |
| SECURITY (анализ в docs/) | ✅ | ✅ |
| SECRETS_ROTATION (ops) | ✅ | ✅ |
| OPEN_SOURCE_PREP | ✅ | ✅ |
| GOVERNANCE (процесс / наблюдатель) | ✅ | ✅ |
| GITHUB_SETUP_GH | ✅ | ✅ (RU как основной текст) |
| WIKI_AUTOMATION | ✅ | ✅ |
| **docs/project/** (заглушки → корень / OpenAPI; MkDocs) | ✅ | — (опционально позже) |

## Добавить или обновить документ

1. Написать или переписать **английский** в `DOC.md` (инструкция, плейсхолдеры, перекрёстные ссылки).
2. При необходимости RU: создать/обновить `DOC.ru.md` (та же структура).
3. Зарегистрировать в [README.md](./README.md) и [README.ru.md](./README.ru.md).
4. Обновить таблицу в этом файле и в [I18N_STATUS.md](./I18N_STATUS.md).
5. Если меняются **HTTP-маршруты** в OpenAPI: [обслуживание OpenAPI](./Documentation.ru.md#openapi-spec-maintenance) (merge / регенерация) и при необходимости `pytest web/tests/test_openapi_contract.py`.

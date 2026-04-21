# Руководство по документации — BirdLense Hub

Как устроена документация проекта для читателей и контрибьюторов.

[English](./Documentation.md)

---

## Структура

| Зона | Назначение |
|------|------------|
| Корень репозитория | `README.md` (EN), быстрый старт, ссылки на `docs/` |
| `docs/` | Подробные гайды, справка, troubleshooting |
| `docs/archive/` | Исторические заметки (по желанию) |

**Навигация:** с [docs/README.md](./README.md).

### Новая опубликованная страница

Если страница попадает в сайт: обновите **`nav`** в корневом **`mkdocs.yml`**, блоки **Мета** и **Репозиторий (канонические файлы)** в [SITE_MAP.ru.md](./SITE_MAP.ru.md) / [SITE_MAP.md](./SITE_MAP.md), при необходимости таблицы в [README.ru.md](./README.ru.md) и [README.md](./README.md), строки в [I18N_STATUS.ru.md](./I18N_STATUS.ru.md) и [I18N_STATUS.md](./I18N_STATUS.md) (раздел **Published site** / опубликованный сайт).

---

## Статический сайт документации (MkDocs + GitHub Pages)

**Версия Python:** в **Docker-образе приложения** BirdLense — **Python 3.11** (база Ultralytics). **MkDocs** для этого репозитория собирается на **Python 3.12** (как в CI job **docs**) — используйте **отдельный venv** (например `.venv-docs`); не смешивайте с интерпретатором внутри контейнера приложения.

В корне репозитория лежит **[mkdocs.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml)**: тема **Material**, каталог исходников — `docs/`, `nav` сверяют с [SITE_MAP.ru.md](./SITE_MAP.ru.md) · [EN](./SITE_MAP.md) (блоки **Мета** и **Репозиторий (канонические файлы)** — в том же порядке, что две группы в боковом меню). Файлы политики и метаданных в корне репозитория (contributing, security policy, changelog, OpenAPI) на сайте открываются через короткие страницы в [docs/project/](./project/contributing.md), чтобы ссылки из `docs/` не уходили в `../` (так ломается публикация на GitHub Pages).

**Проверка в CI:** `python3 scripts/check_site_map_meta_paths.py` (нужен PyYAML из `requirements-docs.txt`) сверяет пути из английских секций `nav` (**Use the hub**, **Develop & integrate**, **ML & project**, **Meta**, **Repository**) с отрывками `docs/SITE_MAP.md`, а плоский блок **Русский** — с отрывками `docs/SITE_MAP.ru.md`, до `mkdocs build --strict`.

**По расписанию — аудит карточек видов:** в workflow [`catalog-cards-audit.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/catalog-cards-audit.yml) задайте переменную репозитория **`CATALOG_CARDS_AUDIT_URL`** (Settings → Secrets and variables → Actions → Variables) или при ручном запуске укажите `base_url`. Продакшен-URL хаба не должен быть захардкожен в репозитории.

### Сборка локально

```bash
python3 -m venv .venv-docs
.venv-docs/bin/pip install -r requirements-docs.txt
.venv-docs/bin/mkdocs serve   # http://127.0.0.1:8000
```

Каталог `site/` в git не коммитится (см. `.gitignore`).

**Полный локальный CI (как проверки на GitHub):** из **корня репозитория** команда `make ci-local` запускает `scripts/ci-full-local.sh` — безопасность Python + Ruff + полный `pytest web/tests/` в **`.venv-ci`**, сверка версий, UI (дрейф OpenAPI codegen, Vitest, typecheck, lint, build), скрипт покрытия Settings UI, **MkDocs** `--strict` через **`.venv-docs`**. `make ci-local-docker` добавляет тесты в Docker-образ и Playwright `smoke.spec.ts`. Для фазы UI нужен **Node.js ≥ 22**. Подробности: [CI_AND_QUALITY.ru](./CI_AND_QUALITY.ru.md).

### Обслуживание спецификации OpenAPI {#openapi-spec-maintenance}

Большой список путей **`/api/ui/...`** и второй **`servers`** для **`/api/processor`** генерируется скриптом **`scripts/generate_openapi_remaining_paths.py`** и вставляется скриптом **`scripts/merge_openapi_fragments.py`** в **`app/web/openapi.yaml`** (перед `components:`).

Из **корня репозитория**:

```bash
python3 scripts/merge_openapi_fragments.py
```

Перед коммитом смотрите **`git diff app/web/openapi.yaml`**: перезаписывается крупный фрагмент файла. Текст в `info.description` и точные схемы ответов при необходимости восстановите вручную после регенерации.

**Повторный merge без дублей:** `merge_openapi_fragments.py` перед вставкой удаляет уже смерженный массовый блок (от первого ключа пути **`/cameras`** до конца секции `paths`), затем снова дописывает фрагмент — повторный запуск не размножает пути. **Ручные пути держите выше `/cameras`** в `openapi.yaml` (генератор всегда начинает bulk-список с `/cameras`). Скрипт **перезаписывает блок `servers:`** ровно в два URL (UI + processor), чтобы повторные merge не накапливали дублирующиеся ключи `description` (это ломает YAML и `openapi-typescript`).

**Не входят в опубликованный сайт** (`exclude_docs` в корневом `mkdocs.yml`): `docs/archive/**`, `docs/article/**` (черновики публикаций), `CONSILIUM_AUDIT.ru.md` (исторический аудит; см. [архив на GitHub](https://github.com/Gfermoto/BirdLense-Hub/tree/main/docs/archive)), а также `PRE_IMPLEMENTATION_UNKNOWN_TIMELINE*.md` (внутренний чеклист перед крупными изменениями UI/API — файл в репозитории, не часть операторского руководства) и `LEGACY_CLEANUP.md` (внутренние заметки по инвентарю/legacy).

### Публикация (CI)

Workflow [.github/workflows/docs-pages.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docs-pages.yml):

- При push в **`main`** или **`dev`** при изменениях в `docs/**`, `mkdocs.yml`, **`VERSION`**, `requirements-docs.txt` или `scripts/check-docs-version.py` (или вручную: **Actions → Documentation site → Run workflow**) сайт **собирается** каждый раз.
- Перед сборкой: **`python3 scripts/check-docs-version.py`** — строка из корневого **`VERSION`** должна быть в `mkdocs.yml` (как минимум `extra.site_version`; верхний баннер — **`overrides/main.html`**, блок `{% block announce %}`, версия из `config.extra.site_version`).
- Сборка: **`mkdocs build --strict`** (битые ссылки и ошибки навигации роняют CI).
- **Деплой на GitHub Pages** выполняется только для ветки **`main`**.

**Настройки репозитория (один раз):** *Settings → Pages → Build and deployment → Source:* **GitHub Actions**. При первом запуске может понадобиться подтвердить окружение `github-pages` для workflow.

Если на опубликованном сайте всё ещё старая версия в баннере, проверьте, что в **`main`** попал актуальный `mkdocs.yml` и что workflow **Documentation site** завершился успешно (обновление Pages может занять несколько минут).

---

## Контент для сообщества, сайта и статей

| Материал | Назначение |
|----------|------------|
| [OVERVIEW](./OVERVIEW.ru.md) | Текст «что и зачем» — главная, статьи |
| [README](./README.ru.md) в `docs/` | Оглавление по темам; навигация сайта — `mkdocs.yml` в корне |
| [SITE_MAP](./SITE_MAP.ru.md) | Готовое сопоставление разделов и файлов |
| [INSTALL](./INSTALL.md) + [SCENARIOS](./SCENARIOS.ru.md) | Быстрый старт и туториалы |
| [FEATURES](./FEATURES.ru.md) | Витрина возможностей |
| [ARCHITECTURE](./ARCHITECTURE.md) | Техническая глубина |
| `app/web/openapi.yaml` | Контракт API; на статическом сайте: [OpenAPI (Redoc)](./reference/openapi.ru.md) (iframe → `openapi.html`) |

**Стиль:** на «вы», короткие блоки, таблицы; без внутреннего жаргона планирования в пользовательских страницах.

### Чеклист ревьюера (перед мержем доков)

- [ ] Основной язык — EN в `*.md`; при смене структуры обновлён `*.ru.md`.
- [ ] Только плейсхолдеры, без реальных IP/путей.
- [ ] Перекрёстные ссылки на ту же локаль, где есть пара.
- [ ] Длинные инструкции (Colab): ячейки исполнимы; тексты print согласованы с языком страницы.
- [ ] Обновлены [README.md](./README.md), [I18N_STATUS.md](./I18N_STATUS.md) и [I18N_STATUS.ru.md](./I18N_STATUS.ru.md) при новой странице (полный контур: **Новая опубликованная страница** выше и **Published site** в обоих файлах статуса).
- [ ] **[ROADMAP.ru](./ROADMAP.ru.md)** § *Текущий стек*: версии React/Vite (и прочие зафиксированные UI-версии) совпадают с `app/ui/package.json` / lock; блок про БД/миграции соответствует `app/web`.
- [ ] Корневой `mkdocs.yml`: новая страница в английском `nav` и в секции **Русский** (или осознанно только в репозитории).
- [ ] [SITE_MAP.md](./SITE_MAP.md) и [SITE_MAP.ru.md](./SITE_MAP.ru.md) совпадают с боковым меню (блоки **Мета** и **Репозиторий (канонические файлы)** — в том же порядке, что две группы в корневом `mkdocs.yml`); если есть пара `DOC.md` / `DOC.ru.md`, в колонке **источник** даны ссылки **на оба** (EN · RU или RU · EN), чтобы карта была двуязычным указателем.
- [ ] После массовой регенерации OpenAPI: `python3 scripts/merge_openapi_fragments.py` — проверить diff, `pytest web/tests/test_openapi_contract.py`, `python3 -c "import yaml; yaml.safe_load(open('app/web/openapi.yaml'))"`.

---

## Языки

- **Английский** — основной язык для новых и поддерживаемых страниц (`*.md`).
- **Русский** — в парных файлах (`*.ru.md`), где есть перевод.
- В **начале** каждой пары — ссылка на другую версию (как в [INSTALL.md](./INSTALL.md)).

Документы, где в `*.md` пока только RU, перечислены в [I18N_STATUS.md](./I18N_STATUS.md); цель — EN основной + опционально RU.

---

## Безопасность в примерах

Не коммитить реальные хосты, пути, токены и ключи. Использовать плейсхолдеры:

| Тип | Пример |
|-----|--------|
| Хост | `YOUR_HOST`, `localhost` |
| Путь на сервере | `YOUR_REMOTE_DIR` |
| Имя в SSH config | `YOUR_SSH_HOST` |
| Секреты | `your-secret-token`, `your-api-key` |
| Публичный URL | `https://your-birdlense.example.com` |

Полная таблица: [OPEN_SOURCE_PREP.md](./OPEN_SOURCE_PREP.md), раздел «Placeholders».

---

## Как править документацию

1. **Инструктивный** тон: что сделать, а не история разработки.
2. Согласованность **INSTALL**, **CONFIGURATION**, **SCENARIOS**, **TROUBLESHOOTING** (перекрёстные ссылки).
3. После смены заголовков — проверить внутренние ссылки.
4. Новый гайд — строка в [docs/README.md](./README.md) и обновление [I18N_STATUS.md](./I18N_STATUS.md).

Нормы репозитория: [Contributing](./project/contributing.md).

---

## Ключевые документы

| Тема | Вход (EN) |
|------|-----------|
| Обзор и аудитория | [OVERVIEW.md](./OVERVIEW.md) |
| Установка / деплой | [INSTALL.md](./INSTALL.md) |
| Сценарии | [SCENARIOS.md](./SCENARIOS.md) |
| Конфигурация | [CONFIGURATION.md](./CONFIGURATION.md) |
| Глоссарий | [GLOSSARY.ru.md](./GLOSSARY.ru.md) |
| Тесты | [TESTING.md](./TESTING.md) |
| Проблемы | [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) |
| Локальная разработка | [LOCAL_DEV.md](./LOCAL_DEV.md) |
| Архитектура | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| API (обзор) | [API.md](./API.md) |
| OpenAPI YAML (канон) | [project/openapi.md](./project/openapi.md) |
| Доступ и роли | [ACCESS_CONTROL.md](./ACCESS_CONTROL.md) |
| Карта сайта | [SITE_MAP.md](./SITE_MAP.md) |
| Обучение (Colab) | [TRAINING.md](./TRAINING.md) |
| Датасеты | [DATASETS.md](./DATASETS.md) |
| Версионирование | [VERSIONING.md](./VERSIONING.md) |
| Roadmap | [ROADMAP.md](./ROADMAP.md) |
| Анализ безопасности | [SECURITY.md](./SECURITY.md) |
| Чеклист open-source | [OPEN_SOURCE_PREP.md](./OPEN_SOURCE_PREP.md) |
| Статус локализации | [I18N_STATUS.md](./I18N_STATUS.md) |

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

---

## Статический сайт документации (MkDocs + GitHub Pages)

В корне репозитория лежит **[mkdocs.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml)**: тема **Material**, каталог исходников — `docs/`, структура `nav` согласована с [SITE_MAP.ru.md](./SITE_MAP.ru.md). Файлы политики и метаданных в корне репозитория (contributing, security policy, changelog, OpenAPI) на сайте открываются через короткие страницы в [docs/project/](./project/contributing.md), чтобы ссылки из `docs/` не уходили в `../` (так ломается публикация на GitHub Pages).

### Сборка локально

```bash
python3 -m venv .venv-docs
.venv-docs/bin/pip install -r requirements-docs.txt
.venv-docs/bin/mkdocs serve   # http://127.0.0.1:8000
```

Каталог `site/` в git не коммитится (см. `.gitignore`).

### Публикация (CI)

Workflow [.github/workflows/docs-pages.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docs-pages.yml):

- При push в **`main`** или **`dev`** при изменениях в `docs/**`, `mkdocs.yml`, **`VERSION`**, `requirements-docs.txt` или `scripts/check-docs-version.py` (или вручную: **Actions → Documentation site → Run workflow**) сайт **собирается** каждый раз.
- Перед сборкой: **`python3 scripts/check-docs-version.py`** — строка из корневого **`VERSION`** должна быть в `mkdocs.yml` (`theme.announcement` и `extra.site_version`), чтобы баннер не отставал от релиза.
- Сборка: **`mkdocs build --strict`** (битые ссылки и ошибки навигации роняют CI).
- **Деплой на GitHub Pages** выполняется только для ветки **`main`**.

**Настройки репозитория (один раз):** *Settings → Pages → Build and deployment → Source:* **GitHub Actions**. При первом запуске может понадобиться подтвердить окружение `github-pages` для workflow.

Если на опубликованном сайте всё ещё старая версия в баннере, проверьте, что в **`main`** попал актуальный `mkdocs.yml` и что workflow **Documentation site** завершился успешно (обновление Pages может занять несколько минут).

---

## Контент для сообщества, сайта и статей

| Материал | Назначение |
|----------|------------|
| [OVERVIEW](./OVERVIEW.ru.md) | Текст «что и зачем» — главная, статьи |
| [README](./README.ru.md) в `docs/` | Структура навигации для статического сайта |
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
- [ ] Обновлены [README.md](./README.md) и [I18N_STATUS.md](./I18N_STATUS.md) при новой странице.

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
| Доступ и роли | [ACCESS_CONTROL.md](./ACCESS_CONTROL.md) |
| Карта сайта | [SITE_MAP.md](./SITE_MAP.md) |
| Обучение (Colab) | [TRAINING.md](./TRAINING.md) |
| Датасеты | [DATASETS.md](./DATASETS.md) |
| Версионирование | [VERSIONING.md](./VERSIONING.md) |
| Roadmap | [ROADMAP.md](./ROADMAP.md) |
| Анализ безопасности | [SECURITY.md](./SECURITY.md) |
| Чеклист open-source | [OPEN_SOURCE_PREP.md](./OPEN_SOURCE_PREP.md) |
| Статус локализации | [I18N_STATUS.md](./I18N_STATUS.md) |

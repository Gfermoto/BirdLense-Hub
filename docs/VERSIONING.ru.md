# Версионирование BirdLense Hub

[English](./VERSIONING.md)

---

## Схема версий

Используется [Semantic Versioning](https://semver.org/lang/ru/): `MAJOR.MINOR.PATCH`.

| Часть | Когда увеличивать |
|-------|-------------------|
| **MAJOR** | Несовместимые изменения API или конфигурации |
| **MINOR** | Новая функциональность с обратной совместимостью |
| **PATCH** | Исправления ошибок, мелкие улучшения |

Примеры:
- `0.1.0` → `0.1.1` — исправление бага
- `0.1.1` → `0.2.0` — новая фича (например, новый тип триггера)
- `1.0.0` → `2.0.0` — ломающее изменение (например, смена формата конфига)

## Где хранится версия

| Файл | Назначение |
|------|------------|
| `VERSION` | Единый источник истины (корень репозитория) |
| `app/ui/package.json` | Версия UI-пакета |
| `app/web/openapi.yaml` | Версия API в OpenAPI |

При релизе обновлять все три.

Также **`mkdocs.yml`**: `extra.site_version` должен совпадать с `VERSION` (CI: `scripts/check-docs-version.py`). Видимый баннер задаётся в **`overrides/main.html`** (блок `announce`), ключ `theme.announcement` в YAML Material не использует.

## Релизы и теги

1. **Перед релизом:** обновить `VERSION`, `package.json`, `openapi.yaml`, `CHANGELOG.md`
2. **Коммит:** `git add -A && git commit -m "Release v0.1.0"`
3. **Тег:** `git tag -a v0.1.0 -m "Release v0.1.0"`
4. **Пуш:** `git push && git push origin v0.1.0`
5. **GitHub Release:** создать Release из тега, вставить заметки из CHANGELOG

### Что запускает GitHub Actions после релиза

- **Docker:** [`.github/workflows/docker-publish.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docker-publish.yml) — при push в **`main`** и при **`release: published`**. Пушит **`latest`** в обоих случаях и **semver-тег** образа (например `0.2.2`) при **опубликованном** Release (не Draft). Для релиза checkout идёт по тегу/коммиту релиза.
- **Сайт документации:** [`.github/workflows/docs-pages.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docs-pages.yml) — **сборка** при push в `main`/`dev` (по путям), при **`release: published`** и `workflow_dispatch`. **Деплой на Pages** — при push/`workflow_dispatch` с **`main`** и при **опубликованном релизе** (у события release `github.ref` = `refs/tags/...`, поэтому деплой нельзя включать только при `ref == main`).

Общая схема: **[Экосистема GitHub](./GITHUB_ECOSYSTEM.ru.md)** (Wiki, Discussions, Issues, Projects).

## CHANGELOG

Формат [Keep a Changelog](https://keepachangelog.com/).

Секции:
- **Added** — новая функциональность
- **Changed** — изменения в существующем поведении
- **Deprecated** — устаревшее (будет удалено)
- **Removed** — удалённая функциональность
- **Fixed** — исправления багов
- **Security** — уязвимости

## Обновления

- **Минорные (0.x.y):** обновление через `make deploy` или `make pull`. Конфиг и данные сохраняются.
- **Мажорные:** см. заметки к релизу — могут потребоваться миграции.

---

См. также: [Changelog](./project/changelog.md), [INSTALL](./INSTALL.ru.md).

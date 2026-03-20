# Экосистема GitHub — как всё связано

[English](./GITHUB_ECOSYSTEM.md)

В BirdLense Hub одновременно используются несколько сущностей GitHub. Здесь — **что главный источник правды**, что **опционально**, и как **релизы** связаны с **Docker** и **Pages**.

---

## Единый источник правды

| Задача | Где правда | Чем не заменять |
|--------|------------|-----------------|
| Установка, API, архитектура, конфиг | **`docs/`** в репозитории → **GitHub Pages** | Только вики |
| README / короткий текст About | Корень: **`README.md`**, **`SHORT_DESCRIPTION.md`** | — |
| Формулировки roadmap | **`docs/ROADMAP.md`** / **`docs/ROADMAP.ru.md`** | Колонки доски без текста в репо |
| Номер версии | **`VERSION`**, плюс `app/ui/package.json`, `app/web/openapi.yaml`, `mkdocs.yml` → `extra.site_version` | Один только тег без обновления файлов |

---

## GitHub Pages (сайт документации)

- **URL:** **Settings → Pages** (например `https://gfermoto.github.io/BirdLense-Hub/`).
- **Сборка:** [`.github/workflows/docs-pages.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docs-pages.yml) (MkDocs Material).
- **Когда выкладывается:** push в **`main`** (при изменении docs и связанных путей), **`workflow_dispatch`**, либо **опубликованный GitHub Release** — чтобы после релиза обновился сайт, даже если менялись только корневые файлы (`VERSION` и т.д.).
- **Версия в шапке** (рядом со звёздами): частично с GitHub API; отображаемая версия доков выравнивается с **`VERSION`** через `overrides/main.html` (см. [VERSIONING](./VERSIONING.ru.md)).

---

## Docker-образ (GHCR)

- **Workflow:** [`.github/workflows/docker-publish.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docker-publish.yml).
- **Триггеры:** push в **`main`**, событие **`release: published`**.
- **Теги:** `…/birdlense-hub:latest` обновляется при push в **main** и при **опубликованном** релизе; semver-тег (например `0.2.2`) добавляется при **Publish** релиза (черновики не считаются).
- Если пакета нет: смотреть **Actions**, убедиться что Release **опубликован**, не Draft.

---

## Wiki

- **Отдельный Git** от кода (`*.wiki.git`), MkDocs там не крутится.
- **Опционально:** [WIKI_AUTOMATION](./WIKI_AUTOMATION.ru.md) — отчёт в Summary, Artifact, при **`WIKI_PUSH_TOKEN`** — push в Wiki.
- Вики — для кратких заметок и ссылок; **основная** документация — `docs/` + Pages.

---

## Discussions и Issues

| Сущность | Для чего |
|----------|----------|
| **Discussions** | Идеи, вопросы, длинные обсуждения |
| **Issues** | Баги, конкретные задачи, регрессии |

Ссылку на Discussions держать в README; метки и шаблоны — по [CONTRIBUTING.ru.md в корне репозитория](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.ru.md) (EN в сайте доков: [Contributing](./project/contributing.md)).

---

## Roadmap и GitHub Projects

- **Roadmap в репо:** `docs/ROADMAP.md` / `.ru.md` — текст и чеклист «что сделано».
- **Projects (доска):** опционально; карточки чаще всего = **Issues**. Доска **не заменяет** Markdown-roadmap: не плодить задачи из уже отгруженного бэклога (сверка с ROADMAP и [FEATURES](./FEATURES.ru.md)).

---

## Чеклист релиза (maintainer)

1. Слить изменения в **`main`**.
2. Поднять **`VERSION`**, **`app/ui/package.json`**, **`app/web/openapi.yaml`**, **`mkdocs.yml`** → `extra.site_version`, **`CHANGELOG.md`**.
3. Коммит, тег **`vX.Y.Z`**, push ветки и тега.
4. GitHub → **Releases** → черновик релиза → выбрать тег → **Publish release** (не оставлять Draft).
5. Проверить **Actions**: Docker и docs зелёные; в **Packages** новые теги; на **Pages** новая версия (при необходимости обновить кэш браузера).

Подробности: [VERSIONING](./VERSIONING.ru.md).

---

## См. также

[GITHUB_SETUP_GH](./GITHUB_SETUP_GH.ru.md) · [WIKI_AUTOMATION](./WIKI_AUTOMATION.ru.md) · [VERSIONING](./VERSIONING.ru.md) · [Contributing](./project/contributing.md)

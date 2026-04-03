# Участие в разработке BirdLense Hub

Спасибо за интерес к проекту BirdLense Hub.

**ИИ / автоматизация:** доводить задачи до конца — [AGENTS.md](AGENTS.md). **Issues и доска:** [docs/ROADMAP.ru.md](docs/ROADMAP.ru.md) (триаж и отчётность) и § *Issues и доска Project* ниже.

## Как участвовать

### Модель веток (два шага до production)

| Шаг | Куда мержим | Кто |
|-----|-------------|-----|
| **1** | Ветка `feature/...` (от **`dev`**) → **Pull Request в `dev`** | Контрибьюторы |
| **2** | **`dev`** → **Pull Request в `main`** | Мейнтейнеры (релиз) |

**Не открывайте** PR фич **напрямую в `main`**: сначала интеграция в `dev`, затем отдельный PR `dev` → `main`.

После merge PR в **`dev`** GitHub **автоматически удалит** фича-ветку — ветки не копятся. **`main`** и **`dev`** остаются: они **защищены от удаления**.

1. **Клонируйте** [BirdLense-Hub](https://github.com/Gfermoto/BirdLense-Hub) (при необходимости — **fork** в свой аккаунт) и создайте ветку от **`dev`**.
2. **Вносите изменения** — следуйте существующему стилю кода.
3. **Тестируйте** — в `app/`: `make test` и `make test-web` (Docker), либо убедитесь, что PR зелёный в CI (**`ui-build`**, **`docs`**, **`docker-tests`**).
4. **Откройте Pull Request** с базой **`dev`**.

**Вторая пара глаз:** для защищённых веток желательно одобрение другого человека. См. [docs/GOVERNANCE.ru.md](docs/GOVERNANCE.ru.md) — как добавить наблюдателя на GitHub и почему ИИ не может принять приглашение collaborator.

## Настройка окружения

```bash
git clone https://github.com/YOUR_USER/BirdLense-Hub.git
cd BirdLense-Hub/app
make build
make start
```

Подробнее: [docs/LOCAL_DEV.ru.md](docs/LOCAL_DEV.ru.md).

## Документация

- **Структура репозитория:** [docs/REPOSITORY_LAYOUT.ru.md](docs/REPOSITORY_LAYOUT.ru.md) — где `app/`, `docs/` и `scripts/`.
- **Индекс:** [docs/README.ru.md](docs/README.ru.md) — структура (запуск / интеграции / разработка).
- **Текст для читателей и статей:** [docs/OVERVIEW.ru.md](docs/OVERVIEW.ru.md).
- **Правила оформления:** [docs/Documentation.ru.md](docs/Documentation.ru.md). **Термины:** [docs/GLOSSARY.ru.md](docs/GLOSSARY.ru.md).
- Изменение поведения для пользователя → обновить соответствующий гайд и [CHANGELOG.md](CHANGELOG.md).

## Стиль кода

- **Python:** PEP 8, по возможности type hints.
- **TypeScript/React:** ESLint, Prettier (конфиг проекта).
- **Документация:** Markdown, короткие блоки и таблицы; placeholders (`YOUR_HOST`, `your-token`) вместо реальных значений.

## Issues и доска Project (отчётность)

**Вся содержательная работа** должна быть отражена в **GitHub Issues** и, если карточка на доске, в проекте **BirdLense Hub — Roadmap** — включая задачи **вне** таблицы консилиума в ROADMAP (только CI, доки, chore). Комментарий с итогом + ссылки на PR, **закрытие** issue при готовности, на доске **Status → Done** (или `bash scripts/github-project-mark-done.sh <n>` при PAT `repo` + `project`). **Отложенные идеи** без текущего объёма работы могут фиксироваться только в [ROADMAP](docs/ROADMAP.ru.md), пока не заведён новый issue под реализацию.

## Требования к Pull Request

- Один PR — одна фича или исправление.
- Добавляйте тесты для новых API и логики процессора.
- Обновляйте документацию при изменении поведения.
- Должны проходить **`make test`** и **`make test-web`** в `app/` (Docker), либо PR зелёный в CI (**`ui-build`**, **`docs`**, **`docker-tests`**).
- Для PR, которые меняют **размещение в UI** или добавляют новый экран (`area:web`): в описании PR кратко подтвердите **ворота UX-контекста** (после [#114](https://github.com/Gfermoto/BirdLense-Hub/issues/114)): какая страница отвечает за намерение пользователя, переиспользуется ли поток данных/API, что покажется оператору «не на своём месте».

### Чеклист перед релизом (мейнтейнер)

См. [docs/LOCAL_DEV.ru.md](docs/LOCAL_DEV.ru.md) — блок **«Чеклист перед релизом»**: тесты, `mkdocs build --strict`, по желанию E2E, смоук после деплоя.

## Сообщение об ошибках

- Используйте GitHub Issues; при закрытии работы и обновлении доски — как в § *Issues и доска Project* выше.
- Уязвимости безопасности: [SECURITY.md](SECURITY.md).

## Вопросы

**[GitHub Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions)** — для вопросов и идей; **Issues** — для багов и конкретных задач.

## Good first issue

Ищите задачи с меткой **`good first issue`**. Мейнтейнерам: в таком issue укажите файлы, критерии готовности и ссылки на `docs/LOCAL_DEV.ru.md` / `docs/TESTING.ru.md`.

## Сообщество

- **Discussions:** https://github.com/Gfermoto/BirdLense-Hub/discussions  
- **Безопасность:** только по [SECURITY.md](SECURITY.md), не в открытых тредах.

## GitHub Projects (мейнтейнерам)

В репозитории включены **Issues**, **Discussions** и **Projects**. Метки `area:*`, `priority:*`, `triage` и вехи **v0.2.3** / **Backlog (no milestone)** уже заведены.

Создать проект **BirdLense Hub — Roadmap**, привязать репозиторий и поле «Поток» (канбан). Для API Projects у `gh` OAuth и `auth refresh -s project` часто крутят **device login** — проще **classic PAT**:

1. [Новый classic token](https://github.com/settings/tokens/new) → **repo** + **project**.
2. `cp scripts/env.project.example scripts/.env.project` и вписать `export GH_TOKEN="ghp_…"` (файл не коммитится, шаблон `.env.*`), либо разово `export GH_TOKEN=ghp_…`.
3. `bash scripts/github-bootstrap-project.sh`

Новый проект изначально **без карточек**. Подтянуть все **открытые issues и PR** на доску:

```bash
bash scripts/github-project-import-open-items.sh
```

Бэклог из ROADMAP (issues **#46–#48, #50–#57**; **#49** не в скоупе — только x86):

```bash
bash scripts/github-project-add-backlog-consilium.sh
```

После закрытия issue, которая уже на доске, выставить **Status** и **Поток** в **Done** (тот же `GH_TOKEN` / `.env.project`):

```bash
bash scripts/github-project-mark-done.sh 46
bash scripts/github-project-mark-done.sh 46 57
```

В **WSL** команда `gh project view … --web` часто падает (`xdg-open: Permission denied`) — откройте напечатанную ссылку вида **https://github.com/users/…/projects/N** в браузере Windows.

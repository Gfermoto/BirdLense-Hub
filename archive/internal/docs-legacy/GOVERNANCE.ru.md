# Управление проектом и внешний наблюдатель

Как снизить **bus factor** и гарантировать, что важные изменения видит не один человек.

[English](./GOVERNANCE.md)

---

## Секреты и автоматизация на GitHub

**Приглашение collaborator** принимает только **реальный пользователь GitHub**. Скрипты и «безликие» инструменты не становятся участником репозитория как человек — для автоматизации используйте **отдельный бот-аккаунт** или **GitHub App** с минимальными правами.

**Не передавайте** в публичные чаты, общие логи и ненадёжные каналы:

- Personal Access Token (PAT) с правами `repo`, `workflow`, `admin`
- Deploy keys с **write** на прод
- содержимое Secrets из GitHub Actions

---

## Сторонний наблюдатель (человек)

**Наблюдатель** — доверенный человек вне (или рядом с) основной разработки: смотрит PR, релизы, security, документацию.

### Как выдать доступ на GitHub

1. Откройте репозиторий → **Settings** → **Collaborators and teams** (или **Manage access**).
2. **Add people** → введите GitHub username или email.
3. Роль:
   - **Read** — просмотр кода, Issues, Actions (достаточно для «наблюдения» и комментариев в PR, если включены форки/ветки; для approve на `main` часто нужен выше уровень — см. ниже).
   - **Triage** — то же + метки, milestone на Issues (без merge).
   - **Write** — может **approve** PR, если в branch protection указаны reviewers (типичный вариант для «второго мнения»).

Официальная справка: [Repository roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/repository-roles-for-an-organization).

### Обязательное ревью перед merge в `main`

1. **Settings** → **Rules** → **Rulesets** (или классический **Branches** → **Branch protection rules**).
2. Для ветки `main`:
   - включите **Require a pull request before merging**;
   - **Required number of approvals** ≥ **1** (лучше 1–2 для критичных репо);
   - опционально: **Dismiss stale reviews**, **Require review from Code Owners**.

Тогда любой merge в `main` проходит через PR и **одобрение наблюдателя**.

### CODEOWNERS

В корне репозитория файл [CODEOWNERS](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/CODEOWNERS): укажите логины ответственных и при необходимости отдельные владельцы для `docs/`, `.github/workflows/`, `app/processor/` и т.д.

---

## Что проверяет наблюдатель (короткий чеклист)

- Соответствие **SECURITY.md** и отсутствие секретов в diff.
- Смысл изменений для пользователей (CHANGELOG, docs).
- CI зелёный; для релизов — теги и артефакты.
- Лицензионная чистота новых зависимостей и ассетов.

Шаблон PR с чекбоксами: [.github/PULL_REQUEST_TEMPLATE.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/PULL_REQUEST_TEMPLATE.md).

---

## Настройка репозитория через `gh` (личный аккаунт)

Пошаговые команды без передачи токенов в чат: [GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md), скрипт `scripts/github-repo-bootstrap.sh`.

---

## Автоматические «внешние» сигналы (не замена человеку)

- **Dependabot** + своевременное закрытие алертов.
- **Dependency review** в Actions для PR.
- **CodeQL** (GitHub Advanced Security или публичный репо — по политике GitHub).
- [OpenSSF Scorecard](https://github.com/ossf/scorecard) — периодический снимок зрелости супплай-чейна.

Их стоит прогонять и обсуждать с наблюдателем по релизам.

---

## Резюме

| Кто | Что делает |
|-----|------------|
| **Maintainer** | Разработка, merge после ревью, релизы |
| **Наблюдатель (collaborator)** | Approve PR, замечания по security/docs |
| **Бот / GitHub App** | Автоматизация с ограниченными токенами — не замена ревью дизайна |

**Доверие оформляется процессом:** PR + одобрение человека.

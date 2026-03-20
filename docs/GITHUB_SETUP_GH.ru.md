# Настройка личного репозитория через GitHub CLI (`gh`)

Пошагово для **`Gfermoto/BirdLense-Hub`**. Токен **никому не отправляйте** — только `gh auth login` у себя на машине.

[English summary](./GITHUB_SETUP_GH.md)

---

## 0. Установка и вход

```bash
# https://cli.github.com/
gh --version
gh auth login
# Рекомендуется: GitHub.com → HTTPS → авторизация через браузер
gh auth status
```

**WSL / SSH / сервер без GUI:** если `xdg-open` и «Permission denied» для браузера — это ожидаемо. Скопируйте одноразовый код из терминала и **вручную** откройте в браузере (на Windows — Chrome/Edge): **https://github.com/login/device** . Код быстро истекает; при ошибке снова `gh auth login`. Из WSL можно открыть вкладку в Windows: `cmd.exe /c start https://github.com/login/device` .

Переменные (удобно вставлять дальше):

```bash
export OWNER=Gfermoto
export REPO=BirdLense-Hub
export FULL="$OWNER/$REPO"
```

Проверка:

```bash
gh repo view "$FULL"
```

### Репозиторий по умолчанию для `gh`

Чтобы команды вроде `gh pr merge` не обращались к другому репо из контекста каталога:

```bash
gh repo set-default Gfermoto/BirdLense-Hub
```

---

## 1. Описание, темы, поведение merge

Подставьте свой текст описания.

```bash
gh repo edit "$FULL" \
  --description "Smart bird feeder monitoring: local ML, Docker, Go2RTC, Frigate, BirdNET, HA — open source." \
  --homepage "https://gfermoto.github.io/BirdLense-Hub/" \
  --add-topic "computer-vision" \
  --add-topic "docker" \
  --add-topic "bird-monitoring" \
  --add-topic "home-assistant" \
  --add-topic "machine-learning" \
  --default-branch main \
  --delete-branch-on-merge \
  --enable-issues \
  --enable-projects
```

Wiki через API:

```bash
gh api "repos/$FULL" -X PATCH -f has_wiki=true
```

Автоотчёты и вывод скриптов в CI → **Summary** / **Wiki**: [WIKI_AUTOMATION.ru.md](./WIKI_AUTOMATION.ru.md).

Опционально (если поддерживает ваша версия `gh`):

```bash
gh repo edit "$FULL" --enable-discussions 2>/dev/null || true
```

Проверить флаги: `gh repo edit -h`.

---

## 2. Безопасность (Dependabot и алерты)

Для **публичного** репо часть включена по умолчанию. Имеет смысл явно включить обновления зависимостей (у вас уже есть `dependabot.yml` в репо — после push в default branch Dependabot начнёт открывать PR).

Включить **Dependabot security updates** (если ещё не включено), через API:

```bash
gh api -X PUT "repos/$FULL/vulnerability-alerts" 2>/dev/null || true
```

Для **приватного** репозитория алерты уязвимостей могут требовать отдельного тарифа — см. документацию GitHub.

Закрывайте алерты из **Security → Dependabot** (у вас уже встречался high — лучше разобрать PR’ом).

---

## 3. GitHub Pages

Источник: **Actions** (у вас workflow `Documentation site` деплоит с `main`).

В UI: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

Через API (если нужно выставить именно `workflow`):

```bash
gh api -X POST "repos/$FULL/pages" \
  -f "build_type=workflow" \
  -f "source[branch]=main" \
  -f "source[path]=/" 2>/dev/null || echo "Если 409 — Pages уже настроены; проверьте в Settings."
```

Чаще всего достаточно один раз кликнуть в веб-интерфейсе после первого успешного деплоя.

---

## 4. Защита веток `main` и `dev` (один мейнтейнер, без второго человека)

Цель: **запрет прямого push** в `main` и `dev`; **фичи** — только PR в **`dev`**, затем отдельный PR **`dev` → `main`**. Ветки **`main`** и **`dev`** **нельзя удалить** (`allow_deletions: false`). Остальные ветки после merge **удаляются**, чтобы не копились.

**Автоудаление head после merge** (`delete_branch_on_merge=true`): при merge фича-PR в `dev` GitHub удалит фича-ветку. При merge PR `dev` → `main` head — это `dev`, но **защищённую от удаления** ветку GitHub **не сотрёт** (см. [документацию GitHub](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-the-automatic-deletion-of-branches)).

Файл в репозитории: [`scripts/github-branch-protection-main.json`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/github-branch-protection-main.json) — тот же payload для **обеих** веток (`allow_deletions: false`).

Применить:

```bash
cd /path/to/BirdLense-Hub   # корень клона
gh api --method PUT "repos/$FULL/branches/main/protection" \
  --input scripts/github-branch-protection-main.json
gh api --method PUT "repos/$FULL/branches/dev/protection" \
  --input scripts/github-branch-protection-main.json
```

Включить автоудаление фича-веток после merge (рекомендуется вместе с защитой `main`/`dev`):

```bash
gh api "repos/$FULL" -X PATCH -f delete_branch_on_merge=true
```

Если GitHub вернёт **422** (политика API менялась), откройте **Settings → Rules → Rulesets** и создайте правила для `main` и `dev`:

- запрет удаления / force push;
- требование **Pull request** перед merge в `main` (для `dev` — по желанию: можно разрешить прямой push мейнтейнеру, но **запрет удаления** оставить);
- **Required approvals: 0** до появления второго человека.

Потом добавьте **Required approvals: 1** и второго в [`.github/CODEOWNERS`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/CODEOWNERS).

### Обязательные status checks (ruleset **Protect**)

На default branch в ruleset включены проверки из workflow **CI**: **`ui-build`** и **`docs`** (они бегают на каждый push/PR в `main` и `dev`). Approve по-прежнему **0** — для одного разработчика.

**Не добавляйте** как required checks workflow **Documentation site** или **Deploy**, если они не гарантированно запускаются на каждый merge (фильтры путей, self-hosted).

Иначе merge в `main` будет «висеть» в ожидании пропущенных проверок.

---

## 5. Packages (GHCR)

Образ собирается workflow **Build and push Docker image**. Проверка:

```bash
gh api "user/packages?package_type=container" -q '.[].name' | head -20
```

Видимость пакета при необходимости: **Package settings → Change visibility** (или через политики org — у вас личный аккаунт, проще в UI).

---

## 6. Секреты для `Deploy` (только если используете self-hosted)

Workflow [`.github/workflows/deploy.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/deploy.yml) ожидает runner с метками `self-hosted`, `birdlense`. Секреты в чат не кладём; при необходимости:

```bash
gh secret list -R "$FULL"
# gh secret set NAME -b"value" -R "$FULL"
```

---

## 7. Один скрипт «по максимуму» из безопасных операций

Из корня клона:

```bash
./scripts/github-repo-bootstrap.sh
```

Скрипт вызывает `gh repo edit` и печатает команду для branch protection. Требуется `gh auth login`.

---

## Чеклист после настройки

- [ ] `main` и `dev` защищены: нет force-push, **нельзя удалить** ветку; фичи → PR в `dev`, релиз — PR `dev` → `main`.
- [ ] **Automatically delete head branches** включено (`delete_branch_on_merge=true`): фича-ветки после merge не копятся; `main`/`dev` не удаляются (защита).
- [ ] (Опционально) Workflow **Prune remote branches** — только **вручную** (`workflow_dispatch`), если нужно снять забытые ветки с `origin`; обычно хватает удаления ветки **после merge** PR.
- [ ] Pages: сайт открывается, последний workflow **Documentation site** зелёный на `main`.
- [ ] Dependabot PR’ы не копятся месяцами.
- [ ] **Deploy** workflow: либо runner поднят, либо workflow отключён / не required, чтобы не было вечных красных статусов.

Когда появится наблюдатель: **GOVERNANCE** + `CODEOWNERS` + **Required approvals ≥ 1**.

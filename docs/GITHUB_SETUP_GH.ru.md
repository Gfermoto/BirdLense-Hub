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

Связка **Pages, Docker, Wiki, Issues и релизов**: [GITHUB_ECOSYSTEM.ru.md](./GITHUB_ECOSYSTEM.ru.md).

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

## 4. Защита ветки `main` (один мейнтейнер, без второго человека)

Цель: **запрет прямого push в `main`**, merge только через **PR** (с `dev` или фича-веток), **без** обязательных approve (пока нет наблюдателя).

Файл в репозитории: [`scripts/github-branch-protection-main.json`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/github-branch-protection-main.json).

Применить:

```bash
cd /path/to/BirdLense   # корень клона
gh api --method PUT "repos/$FULL/branches/main/protection" \
  --input scripts/github-branch-protection-main.json
```

Если GitHub вернёт **422** (политика API менялась), откройте **Settings → Rules → Rulesets** и создайте правило для `main`:

- запрет удаления / force push;
- требование **Pull request** перед merge;
- **Required approvals: 0** до появления второго человека.

Потом добавьте **Required approvals: 1** и второго в [`.github/CODEOWNERS`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/CODEOWNERS).

### Важно про обязательные status checks

Workflow **Documentation site** и **Deploy** срабатывают **не на каждый** push в `main` (фильтры путей и self-hosted runner).  
**Не включайте** их как required checks, пока не будет:

- либо отдельного workflow **«CI на каждый push в main»**;
- либо стабильного self-hosted runner для `Deploy`.

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

- [ ] `main` защищён: нет force-push, merge через PR.
- [ ] Pages: сайт открывается, последний workflow **Documentation site** зелёный на `main`.
- [ ] Dependabot PR’ы не копятся месяцами.
- [ ] **Deploy** workflow: либо runner поднят, либо workflow отключён / не required, чтобы не было вечных красных статусов.

Когда появится наблюдатель: **GOVERNANCE** + `CODEOWNERS` + **Required approvals ≥ 1**.

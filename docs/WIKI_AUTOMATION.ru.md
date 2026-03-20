# Wiki и отчёты CI

На GitHub **Wiki не выполняет скрипты** — это отдельный Git-репозиторий с Markdown. Чтобы «выполнялись скрипты и был виден вывод», используется связка:

1. **GitHub Actions** — workflow **Wiki report** запускает `scripts/generate-wiki-report.sh` и (опционально) публикует результат.
2. **Summary** у каждого запуска — полный вывод отчёта прямо в интерфейсе Actions.
3. **Artifacts** — скачиваемый файл `wiki-report.md`.
4. **Wiki** — копия отчёта на странице **Latest-CI-Report** (если настроен push).

[English](./WIKI_AUTOMATION.md)

---

## Включить Wiki

В настройках репозитория: **Settings → General → Features → Wikis** (вкл.).

Скрипт bootstrap теперь выставляет `has_wiki=true`:

```bash
gh api "repos/Gfermoto/BirdLense-Hub" -X PATCH -f has_wiki=true
```

Либо включите вручную в UI.

---

## Секрет для автопубликации в Wiki (опционально)

Стандартный `GITHUB_TOKEN` **не подходит** для push в Wiki. Нужен **Personal Access Token**:

1. GitHub → **Settings → Developer settings → Personal access tokens**.
2. **Classic**: создайте токен с областью **`repo`** (полный доступ к приватным репозиториям — для публичного репо достаточно этой галки для работы с wiki.git).
3. В репозитории **BirdLense-Hub**: **Settings → Secrets and variables → Actions → New repository secret**.
4. Имя: **`WIKI_PUSH_TOKEN`**, значение: вставленный PAT.

**Не коммитьте токен и не отправляйте в чаты.**

После сохранения секрета workflow **Wiki report** при следующем запуске обновит страницы **Home**, **Latest-CI-Report** (и любые `wiki-source/*.md` из основного репозитория).

---

## Запуск вручную

### В браузере (если не видите кнопку)

1. Откройте **прямую страницу workflow** (имя в YAML — `Wiki report`, файл — `wiki-report.yml`):  
   **https://github.com/Gfermoto/BirdLense-Hub/actions/workflows/wiki-report.yml**
2. Справа сверху блок **Run workflow** → выберите ветку **`main`** → зелёная кнопка **Run workflow**.

Если открываете через общий список: **Actions** → слева в списке **All workflows** найдите **Wiki report** (если список длинный — прокрутите или используйте ссылку выше).

**Если workflow нет в списке вообще:**

- Убедитесь, что файл есть на **default branch** (`main`):  
  https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/wiki-report.yml
- **Settings** → **Actions** → **General** → раздел *Actions permissions* — должно быть разрешено выполнение workflows (не «Disable actions»).

### Через CLI (надёжно)

```bash
gh workflow run "Wiki report" --repo Gfermoto/BirdLense-Hub --ref main
```

Просмотр последнего запуска:

```bash
gh run list --repo Gfermoto/BirdLense-Hub --workflow=wiki-report.yml --limit 3
```

Расписание: по понедельникам ~06:00 UTC (см. `cron` в workflow).

---

## Локальный прогон отчёта

```bash
cd /path/to/BirdLense
bash scripts/generate-wiki-report.sh | less
```

---

## Файлы

| Файл | Назначение |
|------|------------|
| `scripts/generate-wiki-report.sh` | Формирует Markdown |
| `scripts/push-wiki-report.sh` | Пуш в `*.wiki.git` (только CI + секрет) |
| `wiki-source/Home.md` | Статическая главная Wiki (копируется при каждом push) |
| `.github/workflows/wiki-report.yml` | Workflow |

# CodeQL (статический анализ в CI)

[English](./CODEQL.md)

---

**CodeQL** от GitHub запускается workflow **`.github/workflows/codeql.yml`** (в корне репозитория) при **push/PR** в ветки `main` и `dev`, **раз в неделю** по расписанию и **вручную** (**Actions** → **CodeQL** → **Run workflow**, `workflow_dispatch`). В шагах используется **`github/codeql-action@v4`** (`init`, `autobuild`, `analyze`).

## Что анализируется

| Язык | Область (конфиг в `.github/codeql/`) |
|------|----------------------------------------|
| **JavaScript / TypeScript** | `app/ui/src` |
| **Python** | `app/web`, `app/processor` (без `app/processor/models` и `**/tests/**`) |

## Где смотреть результаты

На **GitHub.com**: **Security** → **Code scanning** (алерты и история).  
У форков и в частных репозиториях полный UI может требовать **GitHub Advanced Security**; workflow всё равно выполняется и при необходимости загружает SARIF.

## Локальная среда (по желанию)

### VS Code

1. Откройте репозиторий **с корня** (папка с `.vscode/extensions.json`) — в **Extensions** появится рекомендация **CodeQL**.
2. Установите [CodeQL для VS Code](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-codeql) (ID: **`GitHub.vscode-codeql`** — с заглавной **G** у издателя).

**Если поиск «CodeQL» в Marketplace ничего не находит:**

- Терминал: `code --install-extension GitHub.vscode-codeql`.
- Вручную: на странице расширения в Marketplace — **Download Extension** (файл `.vsix`) → **Extensions** → **⋯** → **Install from VSIX…**.
- Анализ в CI и локально **не завязан** на расширение: достаточно **`scripts/codeql-local.sh`** и просмотра SARIF (в GitHub Security, другим SARIF-viewer или после установки расширения).

3. После прогона скрипта: команды CodeQL для просмотра SARIF или БД из `.tools/codeql-dbs/`.

### CLI

Скрипт **`scripts/codeql-local.sh`** (нужны `gh`, `unzip`, Node **22+**, Python 3.12+):

```bash
bash scripts/codeql-local.sh
```

Кладёт CLI в `.tools/codeql`, пакеты запросов в `~/.codeql/packages`, SARIF в `.tools/codeql-results/` (каталог `.tools/` в `.gitignore`).

### Пример результата ревью (security-extended)

Прогон: Python `app/web` + UI после `npm run build`, наборы **python/javascript-security-extended**.

Исправления по открытым алертам (без «принятия риска»): парсинг хоста через **`urllib.parse.urlparse`** в `infer_metadata_source_fields`, линейный разбор скобок в **`_extract_common_for_hierarchy`**, **`read_safe_image_bytes`** / **`remove_safe_image_file`** для Telegram-уведомлений: `realpath` + `commonpath` + **`full.startswith(base + os.sep)`**, затем `open`/`remove`. Для запроса **`py/path-injection`** барьер `startswith` на практике не снимает taint до sink (поток из `processor_routes` → `image_path`); на строках с `isfile`/`open`/`remove` добавлены комментарии **`# lgtm[py/path-injection]`** с пометкой о проверке под `DATA_DIR` — GitHub Code Scanning учитывает их как подавление после валидации пути., **`mkstemp`** вместо `mktemp` в `spectrogram.py`, редактирование URL в логах go2RTC.

| Разбор | Правило | Файл | Комментарий |
|--------|---------|------|-------------|
| — | `js/missing-origin-check` | `app/ui/public/sw.js` | `postMessage` для `SKIP_WAITING` без проверки origin; для PWA обычно приемлемо. Опционально: `if (event.origin !== self.origin) return;`. |

**Итого:** польза — **регулярный автоматический аудит** и вкладка **Security** на GitHub. На PR может отображаться отдельный агрегат **Code scanning** (по открытым алертам); он не совпадает 1:1 с успехом job’ов workflow **CodeQL**.

В **ruleset** ветки по умолчанию CodeQL **не** обязателен — его можно включить как required check отдельно.

## См. также

- [SECURITY.ru.md](./SECURITY.ru.md) — модель угроз и ручной разбор  
- [TESTING.ru.md](./TESTING.ru.md) — прогон тестов (pytest, Docker)

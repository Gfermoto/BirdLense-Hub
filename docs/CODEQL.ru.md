# CodeQL (статический анализ в CI)

[English](./CODEQL.md)

---

**CodeQL** от GitHub запускается workflow **`.github/workflows/codeql.yml`** (в корне репозитория) при **push/PR** в ветки `main` и `dev`, а также **раз в неделю** по расписанию.

## Что анализируется

| Язык | Область (конфиг в `.github/codeql/`) |
|------|----------------------------------------|
| **JavaScript / TypeScript** | `app/ui/src` |
| **Python** | `app/web`, `app/processor` (без `app/processor/models` и `**/tests/**`) |

## Где смотреть результаты

На **GitHub.com**: **Security** → **Code scanning** (алерты и история).  
У форков и в частных репозиториях полный UI может требовать **GitHub Advanced Security**; workflow всё равно выполняется и при необходимости загружает SARIF.

## Локальная среда (по желанию)

### Cursor / VS Code

1. Откройте репозиторий с корня — в **Extensions** будет рекомендация **CodeQL** (`.vscode/extensions.json`).
2. Установите [CodeQL для VS Code](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-codeql) (в Cursor — тот же Marketplace).
3. После прогона скрипта: команды CodeQL для просмотра SARIF или БД из `.tools/codeql-dbs/`.

### CLI

Скрипт **`scripts/codeql-local.sh`** (нужны `gh`, `unzip`, Node **22+**, Python 3.12+):

```bash
bash scripts/codeql-local.sh
```

Кладёт CLI в `.tools/codeql`, пакеты запросов в `~/.codeql/packages`, SARIF в `.tools/codeql-results/` (каталог `.tools/` в `.gitignore`).

### Пример результата ревью (security-extended)

Прогон: Python `app/web` + UI после `npm run build`, наборы **python/javascript-security-extended**:

| Разбор | Правило | Файл | Комментарий |
|--------|---------|------|-------------|
| Низкий риск | `py/polynomial-redos` | `app/web/util.py` (~439) | Регекс для common name из `species_name`; ReDoS теоретически на злонамеренной строке, на практике — данные каталога видов. |
| Вероятный FP | `py/path-injection` | `app/web/util.py` (~811, 917–919) | `open`/`remove` по `image_path`; перед `open` есть **`_is_safe_image_path`**. Анализатор не связывает путь с `remove` — можно закрыть как false positive в GitHub или вынести общий «безопасный путь». |
| Низкий | `js/missing-origin-check` | `app/ui/public/sw.js` | `postMessage` для `SKIP_WAITING` без проверки origin; для PWA обычно приемлемо. Опционально: `if (event.origin !== self.origin) return;`. |

**Итого:** 4 + 1 срабатывание — без явных критических SQLi/XSS в этом прогоне; польза — **регулярный автоматический аудит** и вкладка **Security** на GitHub.

В **ruleset** ветки по умолчанию CodeQL **не** обязателен — его можно включить как required check отдельно.

## См. также

- [SECURITY.ru.md](./SECURITY.ru.md) — модель угроз и ручной разбор  
- [TESTING.ru.md](./TESTING.ru.md) — прогон тестов (pytest, Docker)

# BirdLense Hub — Wiki

Добро пожаловать. **Основная документация** живёт в репозитории в каталоге [`docs/`](https://github.com/Gfermoto/BirdLense-Hub/tree/main/docs) и на [сайте документации (GitHub Pages)](https://gfermoto.github.io/BirdLense-Hub/).

## Автоматические отчёты CI

- Страница **[Latest-CI-Report](Latest-CI-Report)** обновляется workflow **Wiki report**, если в репозитории задан секрет `WIKI_PUSH_TOKEN` (см. `docs/WIKI_AUTOMATION.ru.md` в основном репо).
- **Всегда** можно открыть: **Actions** → **Wiki report** → последний запуск → вкладка **Summary** (полный вывод) и **Artifacts** (файл `wiki-report.md`).

## Ручное редактирование

Wiki можно править через веб-интерфейс GitHub или клонированием репозитория `*.wiki.git`. Изменения из CI не затирают произвольные страницы — перезаписываются только файлы из `wiki-source/*.md` в репо и `Latest-CI-Report.md`.

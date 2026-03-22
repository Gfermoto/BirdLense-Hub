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

1. Расширение [CodeQL для VS Code](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-codeql) или [CodeQL CLI](https://docs.github.com/en/code-security/codeql-cli).
2. Для запросов к БД — клон [репозитория CodeQL](https://github.com/github/codeql) или пакет из расширения.

В **ruleset** ветки по умолчанию CodeQL **не** обязателен — его можно включить как required check отдельно.

## См. также

- [SECURITY.ru.md](./SECURITY.ru.md) — модель угроз и ручной разбор  
- [TESTING.ru.md](./TESTING.ru.md) — прогон тестов (pytest, Docker)

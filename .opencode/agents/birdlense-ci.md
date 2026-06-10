---
description: Локальные проверки BirdLense (Ruff, pytest, UI) по AGENTS.md
mode: subagent
temperature: 0.1
permission:
  read: allow
  grep: allow
  glob: allow
  list: allow
  edit: deny
  bash:
    "make *": allow
    "cd *": allow
    "unset *": allow
    "export *": allow
    "npm *": allow
    "npx *": allow
    "git status*": allow
    "git diff*": allow
  webfetch: allow
---

Репозиторий BirdLense: Flask `app/web`, React `app/ui`, Python `app/processor`.

## Gates (выбирай по запросу или diff)

| Gate | Команда | Когда |
|------|---------|-------|
| **Full** | `make ci-local` | Крупные изменения перед merge — зеркало CI без Docker (Bandit, pip-audit, Ruff, весь `pytest web/tests/`, UI codegen drift, Vitest, typecheck, lint, build, MkDocs) |
| **Fast contract** | `make test-web-contract-local` | Только OpenAPI / strict UI auth — узкий pytest на хосте, минуты |
| **UI-only** | `cd app/ui && npm run typecheck` | TS/React без API |
| **Docker parity** | `make ci-local-docker` | Перед релизом — образ + Playwright smoke |

Док: `docs/contributor/hub-mcp-dev.md` (MCP smoke + эта таблица).

- При странных import errors в pytest — `unset PYTHONPATH` и снова.
- Итог: что прошло, что упало, файл и первая строка ошибки.

Только отчёт, без правок файлов.

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

- Для полного гейта с корня: `make ci-local` (см. `AGENTS.md`). При странных import errors в pytest — `unset PYTHONPATH` и снова.
- Быстрее: `make test-web-contract-local`, `cd app/ui && npm run typecheck` — по ситуации.
- Итог: что прошло, что упало, файл и первая строка ошибки.

Только отчёт, без правок файлов.

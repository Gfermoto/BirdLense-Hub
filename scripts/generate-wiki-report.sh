#!/usr/bin/env bash
# Печатает Markdown-отчёт для GitHub Wiki / Summary / артефакта CI.
# Запуск: из корня репозитория; в CI подставляются GITHUB_* переменные.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_AT="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"
SHA_SHORT="$(git rev-parse --short HEAD 2>/dev/null || echo "n/a")"
SHA_FULL="$(git rev-parse HEAD 2>/dev/null || echo "n/a")"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "n/a")"
LAST_COMMIT="$(git log -1 --format='%h %s (%an)' 2>/dev/null || echo "n/a")"

VERSION_FILE="n/a"
[[ -f VERSION ]] && VERSION_FILE="$(tr -d '\n' < VERSION)"

PKG_VER="n/a"
if command -v jq >/dev/null 2>&1 && [[ -f app/ui/package.json ]]; then
  PKG_VER="$(jq -r '.version // "n/a"' app/ui/package.json)"
fi

cat <<EOF
# Отчёт CI — BirdLense Hub

| Поле | Значение |
|------|----------|
| **Время (UTC)** | ${RUN_AT} |
| **Workflow run** | \`${GITHUB_RUN_ID:-local}\` |
| **Репозиторий** | \`${GITHUB_REPOSITORY:-local}\` |
| **Ветка (git)** | \`${BRANCH}\` |
| **Commit** | \`${SHA_SHORT}\` (\`${SHA_FULL}\`) |
| **Последний коммит** | ${LAST_COMMIT} |
| **VERSION (файл)** | \`${VERSION_FILE}\` |
| **app/ui package.json** | \`${PKG_VER}\` |

## Workflows (репозиторий)

EOF

if [[ -d .github/workflows ]]; then
  printf '%s\n' '```'
  ls -1 .github/workflows/*.yml 2>/dev/null | xargs -I{} basename {} || true
  printf '%s\n' '```'
else
  echo "_(нет каталога .github/workflows)_"
fi

cat <<'EOF'

## Быстрые проверки (без секретов и SSH)

Скрипты вроде `verify-eu-model.sh` требуют `deploy.local.sh` и доступ к серверу — в GitHub Actions не запускаются.

EOF

echo '```'
echo "openapi.yaml: $([[ -f app/web/openapi.yaml ]] && echo OK || echo MISSING)"
echo "Dockerfile:   $([[ -f app/Dockerfile ]] && echo OK || echo MISSING)"
echo "VERSION:      $(cat VERSION 2>/dev/null || echo MISSING)"
if command -v python3 >/dev/null 2>&1; then
  echo "python3:      $(python3 --version 2>&1)"
fi
if command -v node >/dev/null 2>&1; then
  echo "node:         $(node --version 2>&1)"
fi
echo '```'
echo ""

cat <<EOF

## Куда смотреть вывод

- **GitHub Actions** → workflow **Wiki report** → вкладка **Summary** (этот текст) и **Artifacts** (\`wiki-report.md\`).
- **Wiki**: страница **Latest-CI-Report** — если в настройках репозитория задан секрет \`WIKI_PUSH_TOKEN\` (см. \`docs/WIKI_AUTOMATION.ru.md\`).

---
_Сгенерировано \`scripts/generate-wiki-report.sh\`_
EOF

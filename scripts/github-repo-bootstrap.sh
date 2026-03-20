#!/usr/bin/env bash
# Настройка личного репозитория BirdLense-Hub через GitHub CLI.
# Требуется: gh auth login (токен не передавать в чаты и не коммитить).
set -euo pipefail

OWNER="${OWNER:-Gfermoto}"
REPO="${REPO:-BirdLense-Hub}"
FULL="${OWNER}/${REPO}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v gh >/dev/null 2>&1; then
  echo "Установите GitHub CLI: https://cli.github.com/"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Выполните: gh auth login"
  exit 1
fi

echo "==> Репозиторий: $FULL"
gh repo view "$FULL" >/dev/null

echo "==> Базовые настройки (описание, темы, merge, issues; Wiki включаем через API)"
gh repo edit "$FULL" \
  --description "Smart bird feeder monitoring: local ML, Docker, Go2RTC, Frigate, BirdNET, HA — open source." \
  --homepage "https://gfermoto.github.io/BirdLense-Hub/" \
  --add-topic "computer-vision" \
  --add-topic "docker" \
  --add-topic "bird-monitoring" \
  --add-topic "home-assistant" \
  --add-topic "machine-learning" \
  --default-branch main \
  --enable-issues \
  --enable-projects

gh api "repos/${FULL}" -X PATCH -f has_wiki=true >/dev/null \
  && echo "    Wiki: включена (has_wiki=true). Автоотчёты: workflow Wiki report + docs/WIKI_AUTOMATION.ru.md" \
  || echo "    Wiki: не удалось включить через API (включите в Settings → General → Wikis)."

# Не удалять head-ветку после merge: иначе при merge PR dev→main GitHub сотрёт long-lived ветку dev.
gh api "repos/${FULL}" -X PATCH -f delete_branch_on_merge=false >/dev/null \
  && echo "    delete_branch_on_merge=false (ветки main и dev не исчезают после PR)" \
  || echo "    (delete_branch_on_merge: не удалось выставить через API)"

gh repo edit "$FULL" --enable-discussions 2>/dev/null || echo "(discussions: пропуск, если флаг недоступен)"

echo "==> Включение vulnerability alerts (для публичного репо обычно безвредно)"
gh api -X PUT "repos/${FULL}/vulnerability-alerts" 2>/dev/null || echo "(alerts: уже есть или недоступно для типа репо)"

echo ""
echo "==> Защита веток main и dev (PR, без approve; allow_deletions=false — ветки не удалять)"
echo "    Файл: $ROOT/scripts/github-branch-protection-main.json (тот же payload для обеих)"
if ! gh api --method PUT "repos/${FULL}/branches/main/protection" \
  --input "$ROOT/scripts/github-branch-protection-main.json"; then
  echo "    Ошибка: main (часто 422 — используйте Rulesets). См. docs/GITHUB_SETUP_GH.ru.md"
  exit 1
fi
echo "    OK: main"
if gh api --method PUT "repos/${FULL}/branches/dev/protection" \
  --input "$ROOT/scripts/github-branch-protection-main.json"; then
  echo "    OK: dev"
else
  echo "    Пропуск dev: ветки нет или API 422 — создайте dev, затем:"
  echo "    gh api --method PUT repos/${FULL}/branches/dev/protection --input scripts/github-branch-protection-main.json"
fi

echo ""
echo "Готово. Дальше вручную в UI:"
echo "  - Settings → Pages → Source: GitHub Actions (если ещё не)"
echo "  - Wiki: при желании секрет WIKI_PUSH_TOKEN для пуша отчёта (см. docs/WIKI_AUTOMATION.ru.md)"
echo "  - Security → Dependabot: разгрести алерты"
echo "  - При отсутствии self-hosted runner: не включать workflow Deploy как required check"

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

echo "==> Базовые настройки (описание, темы, merge, issues; wiki выключаем через API)"
# Примечание: старые версии gh не знают --disable-wiki; wiki отключаем PATCH-запросом.
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

gh api "repos/${FULL}" -X PATCH -f has_wiki=false >/dev/null \
  && echo "    Wiki: выключена (has_wiki=false)." \
  || echo "    Wiki: не удалось выключить через API (проверьте права или выключите в Settings)."

gh repo edit "$FULL" --enable-discussions 2>/dev/null || echo "(discussions: пропуск, если флаг недоступен)"

echo "==> Включение vulnerability alerts (для публичного репо обычно безвредно)"
gh api -X PUT "repos/${FULL}/vulnerability-alerts" 2>/dev/null || echo "(alerts: уже есть или недоступно для типа репо)"

echo ""
echo "==> Защита ветки main (PR обязателен, approve: 0 — пока один мейнтейнер)"
echo "    Файл: $ROOT/scripts/github-branch-protection-main.json"
if gh api --method PUT "repos/${FULL}/branches/main/protection" \
  --input "$ROOT/scripts/github-branch-protection-main.json"; then
  echo "    OK: branch protection применён."
else
  echo "    Ошибка API (часто 422). Настройте Ruleset вручную: Settings → Rules → Rulesets"
  echo "    См. docs/GITHUB_SETUP_GH.ru.md"
  exit 1
fi

echo ""
echo "Готово. Дальше вручную в UI:"
echo "  - Settings → Pages → Source: GitHub Actions (если ещё не)"
echo "  - Security → Dependabot: разгрести алерты"
echo "  - При отсутствии self-hosted runner: не включать workflow Deploy как required check"

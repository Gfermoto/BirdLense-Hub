#!/usr/bin/env bash
# Создаёт GitHub Project (v2) у владельца, линкует репозиторий BirdLense-Hub,
# добавляет поле «Поток» (Backlog → … → Done).
#
# Аутентификация (рекомендуется без круга device-login):
#
#   A) Classic PAT — самый стабильный для gh project:* :
#        https://github.com/settings/tokens/new → repo + project
#        export GH_TOKEN=ghp_xxxxxxxx
#        bash scripts/github-bootstrap-project.sh
#      Или: cp scripts/env.project.example scripts/.env.project и вписать токен (файл в .gitignore).
#
#   B) OAuth: gh auth login -h github.com -w -s repo … project read:project
#      (часто «refresh -s project» крутит браузер — для скриптов лучше PAT.)
#
# После создания проекта по умолчанию вызывается импорт открытых issues/PR
# (github-project-import-open-items.sh). Отключить: GITHUB_PROJECT_IMPORT_OPEN=0
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=github-project-pat-hint.sh
source "$SCRIPT_DIR/github-project-pat-hint.sh"
github_project_load_env "$ROOT"

OWNER="${GITHUB_PROJECT_OWNER:-Gfermoto}"
REPO_FULL="${GITHUB_REPO:-Gfermoto/BirdLense-Hub}"
PROJECT_TITLE="${GITHUB_PROJECT_TITLE:-BirdLense Hub — Roadmap}"

die_help() {
  echo ""
  if [[ -n "${GH_TOKEN:-}" ]]; then
    echo "Сейчас задан GH_TOKEN: нужен classic PAT с scope «project» (fine-grained только под repo часто не хватает)."
    echo ""
  fi
  github_project_pat_hint
  exit 1
}

TMPERR=$(mktemp)
trap 'rm -f "$TMPERR"' EXIT

if ! gh project list --owner "$OWNER" --limit 1 2>"$TMPERR"; then
  echo "Ошибка при gh project list:"
  sed 's/^/  /' "$TMPERR"
  echo ""
  die_help
fi

exists_json=$(gh project list --owner "$OWNER" --format json --limit 50)
proj_num=$(echo "$exists_json" | jq -r --arg t "$PROJECT_TITLE" '.projects[] | select(.title == $t) | .number' | head -1)

if [[ -z "$proj_num" || "$proj_num" == "null" ]]; then
  echo "Создаю проект «$PROJECT_TITLE»…"
  create_out=$(gh project create --owner "$OWNER" --title "$PROJECT_TITLE" --format json)
  proj_num=$(echo "$create_out" | jq -r '.number')
  echo "Создан проект #$proj_num"
else
  echo "Проект «$PROJECT_TITLE» уже есть (#$proj_num)"
fi

echo "Линкую $REPO_FULL…"
gh project link "$proj_num" --owner "$OWNER" --repo "$REPO_FULL" 2>/dev/null || true

echo "Добавляю поле «Поток» (если ещё нет — при дубликате можно игнорировать)…"
gh project field-create "$proj_num" --owner "$OWNER" \
  --name "Поток" \
  --data-type "SINGLE_SELECT" \
  --single-select-options "Backlog,Ready,In progress,In review,Done" 2>/dev/null \
  || echo "(поле «Поток» уже есть или не удалось создать — проверьте в UI проекта)"

proj_url=$(gh project view "$proj_num" --owner "$OWNER" --format json --jq '.url' 2>/dev/null) || true
if [[ -z "$proj_url" || "$proj_url" == "null" ]]; then
  proj_url="https://github.com/users/${OWNER}/projects/${proj_num}"
fi

echo
echo "Готово."
echo "Ссылка на проект (в WSL откройте вручную в браузере — «gh … --web» часто даёт Permission denied на xdg-open):"
echo "  $proj_url"
echo
echo "Проект по умолчанию без карточек. Чтобы добавить все открытые issues и PR:"
echo "  bash \"$SCRIPT_DIR/github-project-import-open-items.sh\""

if [[ "${GITHUB_PROJECT_IMPORT_OPEN:-1}" == "1" ]]; then
  echo ""
  echo "GITHUB_PROJECT_IMPORT_OPEN=1 — запускаю импорт открытых карточек…"
  bash "$SCRIPT_DIR/github-project-import-open-items.sh"
fi

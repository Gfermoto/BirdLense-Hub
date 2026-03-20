#!/usr/bin/env bash
# Создаёт GitHub Project (v2) у владельца, линкует репозиторий BirdLense-Hub,
# добавляет поле «Поток» (Backlog → … → Done).
#
# Аутентификация (любой рабочий вариант):
#
#   A) OAuth через браузер с нужными scope (надёжнее, чем только refresh):
#        gh auth logout -h github.com
#        gh auth login -h github.com -w -s repo -s read:org -s gist -s project -s read:project
#
#   B) Классический PAT: https://github.com/settings/tokens/new
#      Включите scope «project» (и «repo», «read:org» как минимум).
#        export GH_TOKEN=ghp_xxxxxxxx
#        bash scripts/github-bootstrap-project.sh
#
#   Вариант «refresh» часто НЕ добавляет project, если токен fine-grained или кэш не обновился.
#
# После создания проекта по умолчанию вызывается импорт открытых issues/PR
# (github-project-import-open-items.sh). Отключить: GITHUB_PROJECT_IMPORT_OPEN=0
#
set -euo pipefail

OWNER="${GITHUB_PROJECT_OWNER:-Gfermoto}"
REPO_FULL="${GITHUB_REPO:-Gfermoto/BirdLense-Hub}"
PROJECT_TITLE="${GITHUB_PROJECT_TITLE:-BirdLense Hub — Roadmap}"

die_help() {
  echo ""
  echo "=== Что сделать ==="
  echo "1) Посмотрите scopes:  gh auth status"
  echo "   Нужны в списке: project и read:project (или один classic PAT с правом Projects)."
  echo ""
  echo "2) Надёжно: полный вход с scope:"
  echo "     gh auth logout -h github.com"
  echo "     gh auth login -h github.com -w -s repo -s read:org -s gist -s project -s read:project"
  echo ""
  echo "3) Или classic PAT в переменную (не коммитьте!):"
  echo "     export GH_TOKEN=ghp_..."
  echo "     bash scripts/github-bootstrap-project.sh"
  echo ""
  exit 1
}

TMPERR=$(mktemp)
trap 'rm -f "$TMPERR"' EXIT

if ! gh project list --owner "$OWNER" --limit 1 2>"$TMPERR"; then
  echo "Ошибка при gh project list:"
  sed 's/^/  /' "$TMPERR"
  echo ""
  if [[ -n "${GH_TOKEN:-}" ]]; then
    echo "Используется GH_TOKEN: убедитесь, что это классический PAT со scope «project» (fine-grained с ограничением только на репо Projects может не подойти)."
  else
    echo "Токен gh, скорее всего, без scope Projects. «gh auth refresh» иногда не меняет права (fine-grained / старый OAuth)."
  fi
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

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

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

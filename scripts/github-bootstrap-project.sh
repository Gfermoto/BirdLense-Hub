#!/usr/bin/env bash
# Создаёт GitHub Project (v2) у владельца, линкует репозиторий BirdLense-Hub,
# добавляет поле «Поток» (Backlog → … → Done) поверх стандартного Status.
#
# Требуется один раз расширить gh-токен:
#   gh auth refresh -s project -s read:project
#
set -euo pipefail

OWNER="${GITHUB_PROJECT_OWNER:-Gfermoto}"
REPO_FULL="${GITHUB_REPO:-Gfermoto/BirdLense-Hub}"
PROJECT_TITLE="${GITHUB_PROJECT_TITLE:-BirdLense Hub — Roadmap}"

if ! gh project list --owner "$OWNER" --limit 1 >/dev/null 2>&1; then
  echo "gh не может читать Projects (нужны scope project / read:project). Выполните:"
  echo "  gh auth refresh -s project -s read:project"
  echo "Затем снова запустите этот скрипт."
  exit 1
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

# Доп. поле для канбана (рядом со стандартным полем Status в Projects)
echo "Добавляю поле «Поток» (если ещё нет — при дубликате будет ошибка, её можно игнорировать)…"
gh project field-create "$proj_num" --owner "$OWNER" \
  --name "Поток" \
  --data-type "SINGLE_SELECT" \
  --single-select-options "Backlog,Ready,In progress,In review,Done" 2>/dev/null \
  || echo "(поле «Поток» уже есть или не удалось создать — проверьте в UI проекта)"

echo
echo "Готово. Открыть в браузере:"
gh project view "$proj_num" --owner "$OWNER" --web 2>/dev/null || echo "  gh project view $proj_num --owner $OWNER --web"

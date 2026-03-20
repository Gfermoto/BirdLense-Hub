#!/usr/bin/env bash
# Добавляет в GitHub Project все открытые issues и pull requests из репозитория.
# Повторный запуск безопасен: уже добавленные элементы пропускаются (по тексту ошибки API).
#
# Те же права, что для github-bootstrap-project.sh (scope project / read:project).
#
set -euo pipefail

OWNER="${GITHUB_PROJECT_OWNER:-Gfermoto}"
REPO_FULL="${GITHUB_REPO:-Gfermoto/BirdLense-Hub}"
PROJECT_TITLE="${GITHUB_PROJECT_TITLE:-BirdLense Hub — Roadmap}"

command -v jq >/dev/null || { echo "Нужна утилита jq"; exit 1; }

TMPERR=$(mktemp)
trap 'rm -f "$TMPERR"' EXIT

if ! gh project list --owner "$OWNER" --limit 1 >/dev/null 2>"$TMPERR"; then
  echo "Нет доступа к Projects:"
  cat "$TMPERR"
  exit 1
fi

exists_json=$(gh project list --owner "$OWNER" --format json --limit 50)
proj_num=$(echo "$exists_json" | jq -r --arg t "$PROJECT_TITLE" '.projects[] | select(.title == $t) | .number' | head -1)

if [[ -z "$proj_num" || "$proj_num" == "null" ]]; then
  echo "Проект «$PROJECT_TITLE» не найден. Сначала: bash scripts/github-bootstrap-project.sh"
  exit 1
fi

echo "Проект #$proj_num «$PROJECT_TITLE» — импорт открытых issues/PR из $REPO_FULL"

added=0
skipped=0
failed=0

while IFS= read -r url; do
  [[ -z "$url" ]] && continue
  if gh project item-add "$proj_num" --owner "$OWNER" --url "$url" 2>"$TMPERR"; then
    echo "  + $url"
    added=$((added + 1))
  else
    err=$(cat "$TMPERR" | tr '\n' ' ')
    if echo "$err" | grep -qiE 'already|exist|duplicate|in the project'; then
      echo "  = уже на доске: $url"
      skipped=$((skipped + 1))
    else
      echo "  ! $url"
      echo "    $err"
      failed=$((failed + 1))
    fi
  fi
done < <(gh issue list -R "$REPO_FULL" --state open --limit 500 --json url --jq '.[].url')

echo ""
echo "Итого: добавлено $added, уже было $skipped, ошибок $failed"

proj_url=$(gh project view "$proj_num" --owner "$OWNER" --format json 2>/dev/null | jq -r '.url // empty')
if [[ -z "$proj_url" || "$proj_url" == "null" ]]; then
  proj_url="https://github.com/users/${OWNER}/projects/${proj_num}"
fi
echo "Доска: $proj_url"
echo ""
echo "В WSL ссылку откройте вручную в Windows-браузере (gh project view --web часто падает на xdg-open)."

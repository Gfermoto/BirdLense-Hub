#!/usr/bin/env bash
# Добавляет на GitHub Project карточки по issues бэклога из ROADMAP (консилиум): #46–#57,
# кроме номеров из GITHUB_BACKLOG_SKIP_ISSUES (по умолчанию 49 — ARM вне политики x86-only).
#
# Доступ к API Projects (надёжно): classic PAT в GH_TOKEN или в scripts/.env.project
#   (см. scripts/env.project.example). OAuth «refresh -s project» часто крутит device-login.
#
# Использование:
#   bash scripts/github-project-add-backlog-consilium.sh
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
# Issues из docs/ROADMAP.md § Backlog consilium
ISSUE_START="${GITHUB_BACKLOG_ISSUE_START:-46}"
ISSUE_END="${GITHUB_BACKLOG_ISSUE_END:-57}"
# Пробел-разделённые номера issues, которые не добавлять (например закрытые / вне скоупа)
GITHUB_BACKLOG_SKIP_ISSUES="${GITHUB_BACKLOG_SKIP_ISSUES:-49}"

issue_skipped() {
  local n=$1
  local s
  for s in $GITHUB_BACKLOG_SKIP_ISSUES; do
    [[ "$s" == "$n" ]] && return 0
  done
  return 1
}

command -v jq >/dev/null || { echo "Нужна утилита jq"; exit 1; }

TMPERR=$(mktemp)
trap 'rm -f "$TMPERR"' EXIT

if ! gh project list --owner "$OWNER" --limit 1 >/dev/null 2>"$TMPERR"; then
  echo "Нет доступа к GitHub Projects:"
  cat "$TMPERR"
  echo ""
  github_project_pat_hint
  exit 1
fi

exists_json=$(gh project list --owner "$OWNER" --format json --limit 50)
proj_num=$(echo "$exists_json" | jq -r --arg t "$PROJECT_TITLE" '.projects[] | select(.title == $t) | .number' | head -1)

if [[ -z "$proj_num" || "$proj_num" == "null" ]]; then
  echo "Проект «$PROJECT_TITLE» не найден. Сначала: bash scripts/github-bootstrap-project.sh"
  exit 1
fi

echo "Проект #$proj_num «$PROJECT_TITLE» — добавляю issues ${ISSUE_START}..${ISSUE_END} из $REPO_FULL (пропуск: ${GITHUB_BACKLOG_SKIP_ISSUES})"

added=0
skipped=0
failed=0

for n in $(seq "$ISSUE_START" "$ISSUE_END"); do
  if issue_skipped "$n"; then
    echo "  − #$n (пропуск: GITHUB_BACKLOG_SKIP_ISSUES)"
    continue
  fi
  url="https://github.com/${REPO_FULL}/issues/${n}"
  if gh project item-add "$proj_num" --owner "$OWNER" --url "$url" 2>"$TMPERR"; then
    echo "  + #$n"
    added=$((added + 1))
  else
    err=$(tr '\n' ' ' <"$TMPERR")
    if echo "$err" | grep -qiE 'already|exist|duplicate|in the project|not found'; then
      echo "  = #$n (уже на доске или issue не найден)"
      skipped=$((skipped + 1))
    else
      echo "  ! #$n — $err"
      failed=$((failed + 1))
    fi
  fi
done

echo ""
echo "Итого: добавлено $added, пропущено/уже есть $skipped, ошибок $failed"
proj_url=$(gh project view "$proj_num" --owner "$OWNER" --format json 2>/dev/null | jq -r '.url // empty')
[[ -z "$proj_url" || "$proj_url" == "null" ]] && proj_url="https://github.com/users/${OWNER}/projects/${proj_num}"
echo "Доска: $proj_url"

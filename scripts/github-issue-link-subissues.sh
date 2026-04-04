#!/usr/bin/env bash
# Привязывает дочерние issues к родительскому через GitHub REST Sub-issues
# (колонка «Sub-issues» на доске и иерархия на странице issue).
#
# Использование:
#   bash scripts/github-issue-link-subissues.sh <родитель_номер> <ребёнок> [ребёнок ...]
#
# Пример (эпик техдолга #220 + уровни + сводные #198/#201):
#   bash scripts/github-issue-link-subissues.sh 220 198 201 221 222 223 224 225
#
# Требуется: gh auth (тот же GH_TOKEN, что для project-скриптов — см. scripts/env.project.example).
# Повторный запуск: уже привязанные sub-issue дают 422 — скрипт их пропускает.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=github-project-pat-hint.sh
source "$SCRIPT_DIR/github-project-pat-hint.sh"
github_project_load_env "$ROOT"

REPO_FULL="${GITHUB_REPO:-Gfermoto/BirdLense-Hub}"

if [[ $# -lt 2 ]]; then
  echo "Использование: $0 <parent_issue_number> <child_issue_number> [child ...]"
  exit 1
fi

parent_num="$1"
shift

tmp_err=$(mktemp)
trap 'rm -f "$tmp_err"' EXIT

if ! parent_id=$(gh api "repos/${REPO_FULL}/issues/${parent_num}" -q .id 2>"$tmp_err"); then
  err=$(tr '\n' ' ' <"$tmp_err")
  echo "Не найден родительский issue #${parent_num} в ${REPO_FULL}: $err"
  exit 1
fi
if [[ -z "$parent_id" || "$parent_id" == "null" ]]; then
  echo "Не найден родительский issue #${parent_num} в ${REPO_FULL}"
  exit 1
fi

linked=0
skipped=0
failed=0

for child_num in "$@"; do
  if ! child_id=$(gh api "repos/${REPO_FULL}/issues/${child_num}" -q .id 2>"$tmp_err"); then
    err=$(tr '\n' ' ' <"$tmp_err")
    echo "! нет issue #${child_num}: $err"
    failed=$((failed + 1))
    continue
  fi
  if [[ -z "$child_id" || "$child_id" == "null" ]]; then
    echo "! нет issue #${child_num}"
    failed=$((failed + 1))
    continue
  fi
  # -F передаёт sub_issue_id как JSON integer; -f даёт строку и API отвечает 422
  if gh api --method POST "repos/${REPO_FULL}/issues/${parent_num}/sub_issues" \
      -F sub_issue_id="$child_id" >/dev/null 2>"$tmp_err"; then
    echo "+ #${child_num} → sub-issue of #${parent_num}"
    linked=$((linked + 1))
  else
    err=$(tr '\n' ' ' <"$tmp_err")
    if echo "$err" | grep -qiE 'duplicate|only have one parent|already'; then
      echo "= #${child_num} уже привязан (пропуск)"
      skipped=$((skipped + 1))
    else
      echo "! #${child_num}: $err"
      failed=$((failed + 1))
    fi
  fi
done

echo ""
echo "Итого: привязано $linked, уже было $skipped, ошибок $failed (родитель #${parent_num})"

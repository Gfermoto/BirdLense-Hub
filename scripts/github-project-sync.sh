#!/usr/bin/env bash
# Синхронизирует GitHub Project с реальным состоянием issues:
# - closed issue -> Status=Done (+ Поток=Done, если поле есть)
# - open issue   -> Status=Todo  (+ Поток=Todo/Backlog, если есть)
# - опционально назначает assignee для открытых issue без исполнителя
# - печатает отчёт по open issue без checklist-подзадач
#
# Пример:
#   bash scripts/github-project-sync.sh --assign Gfermoto
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
ASSIGNEE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --assign)
      ASSIGNEE="${2:-}"
      if [[ -z "$ASSIGNEE" ]]; then
        echo "Пустой --assign. Пример: --assign Gfermoto"
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "Неизвестный аргумент: $1"
      echo "Использование: $0 [--assign <github-login>]"
      exit 1
      ;;
  esac
done

command -v jq >/dev/null || { echo "Нужна утилита jq"; exit 1; }

tmp_err=$(mktemp)
trap 'rm -f "$tmp_err"' EXIT

if ! gh project list --owner "$OWNER" --limit 1 >/dev/null 2>"$tmp_err"; then
  echo "Нет доступа к GitHub Projects:"
  cat "$tmp_err"
  echo ""
  github_project_pat_hint
  exit 1
fi

proj_num=$(
  gh project list --owner "$OWNER" --format json --limit 50 \
    | jq -r --arg t "$PROJECT_TITLE" '.projects[] | select(.title == $t) | .number' \
    | head -1
)
if [[ -z "$proj_num" || "$proj_num" == "null" ]]; then
  echo "Проект «$PROJECT_TITLE» не найден."
  exit 1
fi

proj_id=$(gh project view "$proj_num" --owner "$OWNER" --format json | jq -r '.id')
fields_json=$(gh project field-list "$proj_num" --owner "$OWNER" --format json)
items_json=$(gh project item-list "$proj_num" --owner "$OWNER" --format json --limit 500)

status_field_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Status" and .type == "ProjectV2SingleSelectField") | .id' | head -1)
status_done_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Status" and .type == "ProjectV2SingleSelectField") | .options[]? | select(.name == "Done") | .id' | head -1)
status_todo_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Status" and .type == "ProjectV2SingleSelectField") | .options[]? | select(.name == "Todo") | .id' | head -1)
if [[ -z "$status_todo_id" || "$status_todo_id" == "null" ]]; then
  status_todo_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Status" and .type == "ProjectV2SingleSelectField") | .options[]? | select(.name == "Backlog") | .id' | head -1)
fi

flow_field_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Поток" and .type == "ProjectV2SingleSelectField") | .id' | head -1)
flow_done_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Поток" and .type == "ProjectV2SingleSelectField") | .options[]? | select(.name == "Done") | .id' | head -1)
flow_todo_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Поток" and .type == "ProjectV2SingleSelectField") | .options[]? | select(.name == "Todo") | .id' | head -1)
if [[ -z "$flow_todo_id" || "$flow_todo_id" == "null" ]]; then
  flow_todo_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Поток" and .type == "ProjectV2SingleSelectField") | .options[]? | select(.name == "Backlog") | .id' | head -1)
fi

if [[ -z "$status_field_id" || "$status_field_id" == "null" || -z "$status_done_id" || "$status_done_id" == "null" ]]; then
  echo "Не найдено поле Status с опцией Done."
  exit 1
fi
if [[ -z "$status_todo_id" || "$status_todo_id" == "null" ]]; then
  echo "Не найдено поле Status с опцией Todo/Backlog."
  exit 1
fi

declare -A OPEN_ISSUES=()
declare -A CLOSED_ISSUES=()
while IFS= read -r n; do
  [[ -n "$n" ]] && OPEN_ISSUES["$n"]=1
done < <(gh issue list -R "$REPO_FULL" --state open --limit 500 --json number --jq '.[].number')
while IFS= read -r n; do
  [[ -n "$n" ]] && CLOSED_ISSUES["$n"]=1
done < <(gh issue list -R "$REPO_FULL" --state closed --limit 500 --json number --jq '.[].number')

updated_done=0
updated_todo=0
assigned=0
checked=0

while IFS=$'\t' read -r item_id issue_n status assignees; do
  [[ -z "$item_id" || -z "$issue_n" ]] && continue
  checked=$((checked + 1))

  target_status_id=""
  target_flow_id=""

  if [[ -n "${CLOSED_ISSUES[$issue_n]:-}" ]]; then
    target_status_id="$status_done_id"
    target_flow_id="$flow_done_id"
  elif [[ -n "${OPEN_ISSUES[$issue_n]:-}" ]]; then
    target_status_id="$status_todo_id"
    target_flow_id="$flow_todo_id"
  else
    # Issue не найден (удалён/перенесён) — пропускаем.
    continue
  fi

  current_status_name="${status:-}"
  target_status_name="Todo"
  [[ "$target_status_id" == "$status_done_id" ]] && target_status_name="Done"
  [[ "$target_status_id" == "$status_todo_id" ]] && target_status_name="Todo/Backlog"

  if [[ "$current_status_name" != "Done" && "$target_status_id" == "$status_done_id" ]]; then
    gh project item-edit --id "$item_id" --project-id "$proj_id" \
      --field-id "$status_field_id" --single-select-option-id "$status_done_id" >/dev/null
    if [[ -n "$flow_field_id" && "$flow_field_id" != "null" && -n "$flow_done_id" && "$flow_done_id" != "null" ]]; then
      gh project item-edit --id "$item_id" --project-id "$proj_id" \
        --field-id "$flow_field_id" --single-select-option-id "$flow_done_id" >/dev/null
    fi
    updated_done=$((updated_done + 1))
    echo "  ✓ #$issue_n -> Status Done"
  elif [[ "$current_status_name" == "Done" && "$target_status_id" == "$status_todo_id" ]]; then
    gh project item-edit --id "$item_id" --project-id "$proj_id" \
      --field-id "$status_field_id" --single-select-option-id "$status_todo_id" >/dev/null
    if [[ -n "$flow_field_id" && "$flow_field_id" != "null" && -n "$flow_todo_id" && "$flow_todo_id" != "null" ]]; then
      gh project item-edit --id "$item_id" --project-id "$proj_id" \
        --field-id "$flow_field_id" --single-select-option-id "$flow_todo_id" >/dev/null
    fi
    updated_todo=$((updated_todo + 1))
    echo "  ✓ #$issue_n -> Status ${target_status_name}"
  fi

  if [[ -n "$ASSIGNEE" && -n "${OPEN_ISSUES[$issue_n]:-}" && -z "${assignees:-}" ]]; then
    gh issue edit "$issue_n" -R "$REPO_FULL" --add-assignee "$ASSIGNEE" >/dev/null
    assigned=$((assigned + 1))
    echo "  ✓ #$issue_n -> assignee @$ASSIGNEE"
  fi
done < <(
  echo "$items_json" | jq -r '
    .items[]
    | select(.content.type == "Issue")
    | [.id, (.content.number|tostring), (.status // ""), ((.assignees // []) | join(","))]
    | @tsv
  '
)

echo ""
echo "Синхронизация доски завершена:"
echo "  - проверено карточек issue: $checked"
echo "  - обновлено в Done: $updated_done"
echo "  - обновлено в Todo/Backlog: $updated_todo"
echo "  - назначено исполнителей: $assigned"

echo ""
echo "Open issues без checklist-подзадач:"
missing=0
while IFS=$'\t' read -r n title; do
  [[ -z "$n" ]] && continue
  missing=$((missing + 1))
  echo "  - #$n $title"
done < <(
  gh issue list -R "$REPO_FULL" --state open --limit 500 --json number,title,body \
    | jq -r '.[] | select((.body // "") | test("- \\[[ xX]\\]") | not) | [.number, .title] | @tsv'
)
if [[ "$missing" -eq 0 ]]; then
  echo "  ✓ нет — у всех open issues есть чеклист."
fi

proj_url=$(gh project view "$proj_num" --owner "$OWNER" --format json 2>/dev/null | jq -r '.url // empty')
[[ -z "$proj_url" || "$proj_url" == "null" ]] && proj_url="https://github.com/users/${OWNER}/projects/${proj_num}"
echo ""
echo "Доска: $proj_url"

#!/usr/bin/env bash
# Помечает issue на доске «BirdLense Hub — Roadmap» как Done:
#   поля Status и Поток (если есть) → опция Done.
#
# ID полей подтягиваются из API (не хардкод), чтобы пережить правки доски.
#
# Использование:
#   bash scripts/github-project-mark-done.sh 46
#   bash scripts/github-project-mark-done.sh 46 47 57
#
# Доступ: GH_TOKEN (classic PAT: repo + project) — scripts/.env.project
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

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <issue-number> [<issue-number>...]"
  exit 1
fi

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
  echo "Проект «$PROJECT_TITLE» не найден."
  exit 1
fi

proj_id=$(gh project view "$proj_num" --owner "$OWNER" --format json | jq -r '.id')
fields_json=$(gh project field-list "$proj_num" --owner "$OWNER" --format json)

# Status → Done (англ. колонка GitHub)
status_field_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Status" and .type == "ProjectV2SingleSelectField") | .id' | head -1)
status_done_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Status" and .type == "ProjectV2SingleSelectField") | .options[]? | select(.name == "Done") | .id' | head -1)

# Поток → Done (кастомное поле канбана)
flow_field_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Поток" and .type == "ProjectV2SingleSelectField") | .id' | head -1)
flow_done_id=$(echo "$fields_json" | jq -r '.fields[] | select(.name == "Поток" and .type == "ProjectV2SingleSelectField") | .options[]? | select(.name == "Done") | .id' | head -1)

if [[ -z "$status_field_id" || "$status_field_id" == "null" || -z "$status_done_id" || "$status_done_id" == "null" ]]; then
  echo "Не найдено поле Status с опцией Done. Проверьте: gh project field-list $proj_num --owner $OWNER"
  exit 1
fi

items_json=$(gh project item-list "$proj_num" --owner "$OWNER" --format json --limit 500)

for n in "$@"; do
  if ! [[ "$n" =~ ^[0-9]+$ ]]; then
    echo "Пропуск «$n» — не номер issue"
    continue
  fi
  item_id=$(echo "$items_json" | jq -r --argjson num "$n" '.items[] | select(.content.type == "Issue" and .content.number == $num) | .id' | head -1)
  if [[ -z "$item_id" || "$item_id" == "null" ]]; then
    echo "  ! #$n — нет на доске. Добавить: gh project item-add $proj_num --owner $OWNER --url https://github.com/$REPO_FULL/issues/$n"
    continue
  fi
  gh project item-edit --id "$item_id" --project-id "$proj_id" \
    --field-id "$status_field_id" --single-select-option-id "$status_done_id"
  if [[ -n "$flow_field_id" && "$flow_field_id" != "null" && -n "$flow_done_id" && "$flow_done_id" != "null" ]]; then
    gh project item-edit --id "$item_id" --project-id "$proj_id" \
      --field-id "$flow_field_id" --single-select-option-id "$flow_done_id"
  fi
  echo "  ✓ #$n — Status Done${flow_done_id:+; Поток Done}"
done

proj_url=$(gh project view "$proj_num" --owner "$OWNER" --format json 2>/dev/null | jq -r '.url // empty')
[[ -z "$proj_url" || "$proj_url" == "null" ]] && proj_url="https://github.com/users/${OWNER}/projects/${proj_num}"
echo "Доска: $proj_url"

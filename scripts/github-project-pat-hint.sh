#!/usr/bin/env bash
# Подключается из других скриптов (source). Не запускать напрямую.
# shellcheck shell=bash

# Загрузить scripts/.env.project (gitignore) — внутри: export GH_TOKEN="ghp_..."
github_project_load_env() {
  local root="$1"
  local f="$root/scripts/.env.project"
  if [[ -f "$f" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
    [[ -n "${GH_TOKEN:-}" ]] && echo "Загружен $f (GH_TOKEN для gh)."
  fi
}

github_project_pat_hint() {
  cat <<'EOF'
=== Доступ к GitHub Projects: без «device login» по кругу ===

OAuth и «gh auth refresh -s project» часто уходят в бесконечный browser/device flow.
Для скриптов проекта надёжнее classic PAT:

1) Создать токен: https://github.com/settings/tokens/new
   Включить: ✓ repo, ✓ project (Full control of user projects).

2) Вариант A — только на эту команду:
     export GH_TOKEN=ghp_xxxxxxxx
     bash scripts/…

   Вариант B — файл (не коммитить, шаблон: scripts/env.project.example):
     cp scripts/env.project.example scripts/.env.project
     # отредактировать GH_TOKEN в scripts/.env.project

3) Проверка:
     GH_TOKEN=ghp_… gh project list --owner Gfermoto --limit 3

Токен не передавать в чаты и не коммитить.
EOF
}

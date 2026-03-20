#!/usr/bin/env bash
# Пушит wiki-report.md и статические страницы из wiki-source/ в GitHub Wiki.
# Требует: переменная WIKI_PUSH_TOKEN (classic PAT с правом repo), GITHUB_REPOSITORY.
set -euo pipefail

if [[ -z "${WIKI_PUSH_TOKEN:-}" ]]; then
  echo "::notice title=Wiki::Секрет WIKI_PUSH_TOKEN не задан — страница Wiki не обновлена. Откройте Summary этого job или скачайте артефакт wiki-report.md."
  exit 0
fi

if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "::error::GITHUB_REPOSITORY не задан (запускайте только из GitHub Actions)."
  exit 1
fi

if [[ ! -f "${GITHUB_WORKSPACE:-.}/wiki-report.md" ]]; then
  echo "::error::Файл wiki-report.md не найден в GITHUB_WORKSPACE."
  exit 1
fi

REPO_URL="https://x-access-token:${WIKI_PUSH_TOKEN}@github.com/${GITHUB_REPOSITORY}.wiki.git"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export GIT_TERMINAL_PROMPT=0
git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"
git config --global user.name "github-actions[bot]"

WIKI_DIR="$TMP/wiki"
rm -rf "$WIKI_DIR"
if git clone --depth 1 "$REPO_URL" "$WIKI_DIR" 2>/dev/null; then
  echo "Wiki: клонирован существующий репозиторий."
else
  echo "Wiki: clone не удался (часто так бывает до первой страницы) — создаём локальный репозиторий."
  mkdir -p "$WIKI_DIR"
  git -C "$WIKI_DIR" init
  git -C "$WIKI_DIR" remote add origin "$REPO_URL"
fi

cd "$WIKI_DIR"

# Отчёт CI (всегда перезаписываем)
cp "${GITHUB_WORKSPACE}/wiki-report.md" ./Latest-CI-Report.md

# Статические страницы из основного репо
if [[ -d "${GITHUB_WORKSPACE}/wiki-source" ]]; then
  cp -f "${GITHUB_WORKSPACE}/wiki-source/"*.md . 2>/dev/null || true
fi

git add -A
if git diff --staged --quiet; then
  echo "Wiki: изменений нет, push не нужен."
  exit 0
fi

git commit -m "chore(wiki): CI report run ${GITHUB_RUN_ID:-?} ${GITHUB_SHA:-}"

# У GitHub Wiki ветка по умолчанию — master
if git show-ref --verify --quiet refs/heads/master; then
  git push origin master
else
  git branch -M master
  git push -u origin master
fi

echo "::notice title=Wiki::Страницы обновлены (в т.ч. Latest-CI-Report)."

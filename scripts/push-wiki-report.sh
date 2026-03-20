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

# Проверка: фича Wiki включена у репозитория (иначе *.wiki.git не существует → «Repository not found»).
api_json="$(curl -fsS -H "Authorization: Bearer ${WIKI_PUSH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${GITHUB_REPOSITORY}" 2>/dev/null || true)"
if [[ -n "$api_json" ]]; then
  has_wiki="$(printf '%s' "$api_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('has_wiki', False))" 2>/dev/null || echo "unknown")"
  if [[ "$has_wiki" == "False" ]]; then
    echo "::error::У репозитория выключена Wiki. Включите: **Settings → General → Features → Wikis**, затем на вкладке **Wiki** создайте первую страницу (любой текст) и Save, после чего перезапустите workflow."
    exit 1
  fi
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
  echo "Wiki: clone не удался (часто до первой страницы в UI или Wiki выключена) — создаём локальный репозиторий."
  mkdir -p "$WIKI_DIR"
  git -C "$WIKI_DIR" init
  git -C "$WIKI_DIR" branch -M master
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
git branch -M master 2>/dev/null || true
if ! git push -u origin master 2>/tmp/wiki-push.err; then
  echo "::error::Push в Wiki не удался (см. git ниже). Частые причины:"
  echo "  1) **Wikis** выключены в Settings → General, или ни разу не создавали страницу на вкладке Wiki."
  echo "  2) **Токен**: нужен **classic PAT** с галкой **repo** (fine-grained часто не подходит для *.wiki.git)."
  echo "  3) Токен выдан **другим** пользователем без прав на репозиторий (GitHub тогда пишет «not found»)."
  echo ""
  cat /tmp/wiki-push.err 2>/dev/null || true
  exit 1
fi

echo "::notice title=Wiki::Страницы обновлены (в т.ч. Latest-CI-Report)."

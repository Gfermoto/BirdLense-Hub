#!/usr/bin/env bash
# OPTIONAL LAST RESORT — rewrites every commit (new SHAs). Prefer SECURITY.md §8.2 “keep history”:
# sanitize current branch only; do not run this script unless the team accepts force-push.
#
# Removes leaked host/IP from all blobs and commit messages across history.
#
# Requires: git, Python 3, pip (installs git-filter-repo into user site-packages if missing).
#
# Usage (values do not stay in repo files; may still appear in shell history):
#   ./scripts/redact-git-history-leaks.sh 'OLD_IPV4' 'OLD_HOSTNAME' [NEW_IPV4 NEW_HOSTNAME]
#
# Defaults for NEW_* match docs (RFC 5737 TEST-NET-3 + example.com):
#   NEW_IPV4=203.0.113.10  NEW_HOSTNAME=hub.example.com
#
# Alternative — rules file (git-filter-repo --replace-text syntax, one rule per line):
#   ./scripts/redact-git-history-leaks.sh --from-file /tmp/my-replacements.txt
#
# Before running:
#   1) Push all branches or make a bare mirror backup: git clone --mirror . ../BirdLense-backup.git
#   2) Worktree clean (commit/stash), or: SKIP_DIRTY_CHECK=1 ./scripts/...
#
# After success:
#   git push --force-with-lease --all
#   git push --force-with-lease --tags
#   Ask collaborators to re-clone or reset hard to the new history.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: not a git repository" >&2
  exit 1
fi

have_filter_repo() {
  command -v git-filter-repo >/dev/null 2>&1
}

ensure_filter_repo() {
  if have_filter_repo; then
    return 0
  fi
  echo "Installing git-filter-repo for current user (pip --user)..."
  python3 -m pip install --user --upgrade git-filter-repo
  export PATH="${HOME}/.local/bin:${PATH}"
  if ! have_filter_repo; then
    echo "error: git-filter-repo still not on PATH; add ~/.local/bin to PATH" >&2
    exit 1
  fi
}

make_rules_from_args() {
  local old_ip="$1" old_host="$2" new_ip="$3" new_host="$4"
  local f
  f="$(mktemp "${TMPDIR:-/tmp}/birdlense-redact.XXXXXX")"
  printf '%s==>%s\n' "$old_ip" "$new_ip" >>"$f"
  printf '%s==>%s\n' "$old_host" "$new_host" >>"$f"
  echo "$f"
}

if [[ "${SKIP_DIRTY_CHECK:-}" != "1" ]] && [[ -n "$(git status --porcelain)" ]]; then
  echo "error: dirty worktree. Commit/stash, or rerun with SKIP_DIRTY_CHECK=1" >&2
  exit 1
fi

RULES_FILE=""
cleanup() {
  if [[ -n "${RULES_FILE:-}" && -f "${RULES_FILE:-}" && "${RULES_FILE}" == *birdlense-redact.* ]]; then
    rm -f "$RULES_FILE"
  fi
}
trap cleanup EXIT

if [[ "${1:-}" == "--from-file" ]]; then
  [[ -n "${2:-}" ]] || { echo "usage: $0 --from-file /path/to/rules.txt" >&2; exit 1; }
  RULES_FILE="$2"
  [[ -f "$RULES_FILE" ]] || { echo "error: file not found: $RULES_FILE" >&2; exit 1; }
else
  [[ -n "${1:-}" && -n "${2:-}" ]] || {
    echo "usage: $0 <old_ipv4> <old_hostname> [new_ipv4 new_hostname]" >&2
    echo "   or: $0 --from-file /path/to/replacements.txt" >&2
    exit 1
  }
  NEW_IP="${3:-203.0.113.10}"
  NEW_HOST="${4:-hub.example.com}"
  RULES_FILE="$(make_rules_from_args "$1" "$2" "$NEW_IP" "$NEW_HOST")"
fi

echo "Replacement rules (first line only shown):"
head -n 1 "$RULES_FILE" | sed 's/==>.*$/==>…/'
echo "… ($(wc -l <"$RULES_FILE") lines total)"
echo ""
echo "WARNING: every commit hash will change; you will need force-push. To KEEP history, Ctrl+C and read SECURITY §8.2."
read -r -p "Type YES to rewrite entire history: " confirm
[[ "$confirm" == "YES" ]] || { echo "aborted."; exit 1; }

ensure_filter_repo

export PATH="${HOME}/.local/bin:${PATH}"

# --force: allow running on a non-fresh clone (see git-filter-repo docs).
git filter-repo \
  --replace-text "$RULES_FILE" \
  --replace-message "$RULES_FILE" \
  --force

echo ""
echo "Done. Verify (pick a string you redacted): git log --all -S'…' --oneline"
echo "Expect no hits. Then:"
echo "  git push --force-with-lease --all"
echo "  git push --force-with-lease --tags"

#!/usr/bin/env bash
# Pre-flight проверка переменных окружения для production-хаба (без сетевых запросов).
# Соответствует «Production Gates» в AGENTS.md / CONFIGURATION.md.
#
# Использование:
#   ./scripts/verify-prod-env.sh
#   VERIFY_PROD_ENV=1 ./scripts/verify-prod-env.sh --env-file app/.env
#   ./scripts/verify-prod-env.sh --env-file app/.env --require-mcp-token
#
# По умолчанию скрипт проверяет только если BIRDLENSE_ENV=production (регистр не важен)
# или задан VERIFY_PROD_ENV=1 (прогон перед деплоем с тем же .env, что на сервере).
#
# Коды выхода: 0 — ок или проверка пропущена; 1 — нарушение обязательных условий; 2 — ошибка аргументов.

set -euo pipefail

ENV_FILE=""
REQUIRE_MCP_TOKEN=0

usage() {
  echo "usage: $0 [--env-file PATH] [--require-mcp-token]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      [[ $# -ge 2 ]] || usage
      ENV_FILE="$2"
      shift 2
      ;;
    --require-mcp-token)
      REQUIRE_MCP_TOKEN=1
      shift
      ;;
    -h | --help)
      usage
      ;;
    *)
      echo "unknown option: $1" >&2
      usage
      ;;
  esac
done

load_dotenv_file() {
  local f="$1"
  [[ -n "$f" ]] || return 0
  if [[ ! -f "$f" ]]; then
    echo "verify-prod-env: warning: --env-file not found: $f (using current environment only)" >&2
    return 0
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      if [[ "$val" == \"*\" ]]; then
        val="${val#\"}"
        val="${val%\"}"
      elif [[ "$val" == \'*\' ]]; then
        val="${val#\'}"
        val="${val%\'}"
      fi
      export "$key=$val"
    fi
  done <"$f"
  echo "verify-prod-env: loaded environment keys from $f" >&2
}

[[ -n "$ENV_FILE" ]] && load_dotenv_file "$ENV_FILE"

be_prod=0
if [[ "${VERIFY_PROD_ENV:-}" =~ ^(1|true|yes)$ ]]; then
  be_prod=1
fi
_env_lc="${BIRDLENSE_ENV:-}"
_env_lc="${_env_lc,,}"
if [[ "$_env_lc" == "production" || "$_env_lc" == "prod" ]]; then
  be_prod=1
fi

if [[ "$be_prod" -eq 0 ]]; then
  echo "verify-prod-env: skip (set BIRDLENSE_ENV=production or VERIFY_PROD_ENV=1 to enforce checks)"
  exit 0
fi

fail=0
warn() { echo "verify-prod-env: WARN: $*" >&2; }
err() { echo "verify-prod-env: ERROR: $*" >&2; fail=1; }

# Secrets: не печатаем значения
if [[ -z "${FLASK_SECRET_KEY:-}" ]]; then
  err "FLASK_SECRET_KEY is empty (required in production)"
else
  if [[ "${FLASK_SECRET_KEY}" == *'\${'* ]] || [[ "${FLASK_SECRET_KEY}" == '${'* ]]; then
    err "FLASK_SECRET_KEY looks unexpanded (remove \${...} placeholders)"
  fi
  if [[ "${#FLASK_SECRET_KEY}" -lt 32 ]]; then
    err "FLASK_SECRET_KEY length must be at least 32 characters in production"
  fi
fi

if [[ -z "${PROCESSOR_SECRET:-}" ]]; then
  err "PROCESSOR_SECRET is empty (required in production)"
else
  if [[ "${PROCESSOR_SECRET}" == *'\${'* ]] || [[ "${PROCESSOR_SECRET}" == '${'* ]]; then
    err "PROCESSOR_SECRET looks unexpanded (remove \${...} placeholders)"
  fi
  if [[ "${#PROCESSOR_SECRET}" -lt 32 ]]; then
    err "PROCESSOR_SECRET length must be at least 32 characters in production"
  fi
fi

_strict="${BIRDLENSE_STRICT_API_AUTH:-}"
_strict_lc="${_strict,,}"
if [[ "$_strict_lc" != "1" && "$_strict_lc" != "true" && "$_strict_lc" != "yes" ]]; then
  err "BIRDLENSE_STRICT_API_AUTH should be 1/true/yes for public or non-LAN deployments"
fi

if [[ "$REQUIRE_MCP_TOKEN" -eq 1 ]]; then
  _mt="${MCP_TOKEN:-${BIRDLENSE_MCP_TOKEN:-}}"
  if [[ -z "$_mt" ]]; then
    err "MCP token required (--require-mcp-token) but MCP_TOKEN and BIRDLENSE_MCP_TOKEN are empty"
  fi
fi

if [[ "$fail" -ne 0 ]]; then
  echo "verify-prod-env: production pre-flight failed" >&2
  exit 1
fi

echo "verify-prod-env: production pre-flight OK (strict auth + secrets present)" >&2
exit 0

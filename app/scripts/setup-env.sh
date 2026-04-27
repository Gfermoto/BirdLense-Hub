#!/bin/bash
# Создаёт app/.env с PROCESSOR_SECRET и FLASK_SECRET_KEY если их нет
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${APP_DIR}/.env"

mkdir -p "$APP_DIR"
if [ ! -f "$ENV_FILE" ]; then
  cp "${APP_DIR}/.env.example" "$ENV_FILE"
  echo "Создан ${ENV_FILE} из .env.example"
fi

if ! grep -q '^BIRDLENSE_ENV=.\+' "$ENV_FILE" 2>/dev/null; then
  echo "BIRDLENSE_ENV=production" >> "$ENV_FILE"
  echo "Добавлен BIRDLENSE_ENV=production в ${ENV_FILE}"
fi

if ! grep -q '^BIRDLENSE_STRICT_API_AUTH=.\+' "$ENV_FILE" 2>/dev/null; then
  echo "BIRDLENSE_STRICT_API_AUTH=1" >> "$ENV_FILE"
  echo "Добавлен BIRDLENSE_STRICT_API_AUTH=1 в ${ENV_FILE}"
fi

# PROCESSOR_SECRET — генерируем если нет или пустой
if ! grep -q '^PROCESSOR_SECRET=.\+' "$ENV_FILE" 2>/dev/null; then
  SECRET=$(openssl rand -hex 16)
  (grep -v '^PROCESSOR_SECRET=' "$ENV_FILE" 2>/dev/null || cat "$ENV_FILE") > "${ENV_FILE}.tmp"
  echo "PROCESSOR_SECRET=${SECRET}" >> "${ENV_FILE}.tmp"
  mv "${ENV_FILE}.tmp" "$ENV_FILE"
  echo "Добавлен PROCESSOR_SECRET в ${ENV_FILE}"
fi

# FLASK_SECRET_KEY — генерируем если нет или дефолтный
if ! grep -q '^FLASK_SECRET_KEY=.\+' "$ENV_FILE" 2>/dev/null || grep -q '^FLASK_SECRET_KEY=birdlense-settings-session' "$ENV_FILE" 2>/dev/null; then
  SECRET=$(openssl rand -hex 16)
  (grep -v '^FLASK_SECRET_KEY=' "$ENV_FILE" 2>/dev/null || cat "$ENV_FILE") > "${ENV_FILE}.tmp"
  echo "FLASK_SECRET_KEY=${SECRET}" >> "${ENV_FILE}.tmp"
  mv "${ENV_FILE}.tmp" "$ENV_FILE"
  echo "Добавлен FLASK_SECRET_KEY в ${ENV_FILE}"
fi

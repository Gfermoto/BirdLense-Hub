#!/usr/bin/env bash
# Обёртка: см. основной скрипт в app/scripts (тот же файл в образе).
exec "$(cd "$(dirname "$0")" && pwd)/../app/scripts/verify-detector-weights.sh" "$@"

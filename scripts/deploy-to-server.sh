#!/bin/bash
# Деплой на 192.168.1.11 — вызывает scripts/deploy.sh
# DEPLOY_HOST=birdlense (из ~/.ssh/config)

cd "$(dirname "$0")"
exec ./deploy.sh

#!/bin/bash
set -e
# Очистка старых контейнеров и образов birdlense (только!)
docker-compose down
# Удаляем старые образы birdlense, если они есть
old_images=$(docker images -q birdlense 2>/dev/null)
[ -n "$old_images" ] && docker rmi $old_images || true

# Сборка и запуск
make build
make start
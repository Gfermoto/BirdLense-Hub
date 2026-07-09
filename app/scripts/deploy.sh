#!/bin/bash
set -e
# Очистка старых контейнеров и образов birdlense перед пересборкой (Redis не трогаем).
docker compose stop birdlense 2>/dev/null || true
docker compose rm -f birdlense 2>/dev/null || true
old_images=$(docker images -q app-birdlense 2>/dev/null || true)
if [ -n "$old_images" ]; then
  echo "Removing old app-birdlense images: $old_images"
  docker rmi -f $old_images || true
fi
docker image prune -f --filter 'dangling=true' 2>/dev/null || true

make build
make start

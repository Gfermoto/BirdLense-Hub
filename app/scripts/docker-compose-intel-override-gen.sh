#!/usr/bin/env bash
# Генерация docker-compose.override.yml для Intel: VA-API + метрики GPU (#intel).
# Вызывается с хоста с GPU (деплой) или вручную из каталога app/ рядом с docker-compose.yml.
# Условие: есть хотя бы один /dev/dri/renderD* — иначе override удаляется.
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="${1:-docker-compose.override.yml}"

if ! compgen -G "/dev/dri/renderD*" >/dev/null 2>&1; then
  rm -f "$OUT"
  echo "docker-compose-intel-override-gen: нет /dev/dri/renderD* — $OUT удалён"
  exit 0
fi

DEV_LINES=""
for f in /dev/dri/renderD*; do
  [[ -e "$f" ]] || continue
  DEV_LINES+="      - $f:$f"$'\n'
done
for f in /dev/dri/card*; do
  [[ -e "$f" ]] || continue
  DEV_LINES+="      - $f:$f"$'\n'
done

GA_LINES=""
if command -v getent >/dev/null 2>&1; then
  VG="$(getent group video 2>/dev/null | cut -d: -f3 || true)"
  RG="$(getent group render 2>/dev/null | cut -d: -f3 || true)"
  if [[ -n "${VG:-}" ]]; then
    GA_LINES+="      - \"$VG\"  # video (хост)"$'\n'
  fi
  if [[ -n "${RG:-}" ]]; then
    GA_LINES+="      - \"$RG\"  # render (хост)"$'\n'
  fi
fi

GA_BLOCK=""
if [[ -n "$GA_LINES" ]]; then
  GA_BLOCK="    group_add:
$GA_LINES"
fi

cat >"$OUT" <<EOF
# Сгенерировано scripts/docker-compose-intel-override-gen.sh — не править руками (перегенерируется при деплое).
services:
  birdlense:
    devices:
$DEV_LINES$GA_BLOCK    cap_add:
      - SYS_ADMIN
      - PERFMON
    environment:
      - LIBVA_DRIVER_NAME=iHD
    volumes:
      - /sys/class/drm:/sys/class/drm:ro
EOF

echo "docker-compose-intel-override-gen: записан $OUT (устройства DRI + group_add video/render + CAP_PERFMON)"

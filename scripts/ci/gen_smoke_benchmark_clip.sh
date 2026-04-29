#!/usr/bin/env bash
# Генерация краткого чёрного mp4 для smoke ``benchmark-track-regen.py`` (#372).
# Требуется: ffmpeg (apt install ffmpeg / brew install ffmpeg).
set -euo pipefail
OUT="${1:-$(dirname "$0")/../../.artifacts/smoke_clip.mp4}"
mkdir -p "$(dirname "$OUT")"
exec ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i color=c=black:s=128x128:r=2:d=2 \
  -pix_fmt yuv420p -c:v libx264 -preset ultrafast \
  -movflags +faststart \
  "$OUT"
echo "Wrote $OUT ($(wc -c < "$OUT") bytes)"
sha256sum "$OUT" || true

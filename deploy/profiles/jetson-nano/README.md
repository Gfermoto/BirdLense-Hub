# Jetson Nano (aarch64)

Отдельный образ `app/Dockerfile.jetson` и override `app/docker-compose.jetson.yml` (лимиты RAM, опционально `runtime: nvidia`).

## Деплой

В `scripts/deploy.local.sh`:

```bash
export DEPLOY_HOST="gfer@192.168.8.199"
export DEPLOY_URL="http://192.168.8.199:8085"
export BIRDLENSE_PLATFORM=jetson_nano
```

```bash
make deploy
```

Локально на Jetson:

```bash
cd app
BIRDLENSE_PLATFORM=jetson_nano docker compose -f docker-compose.yml -f docker-compose.jetson.yml up -d --build
```

## Конфиг

- Overlay: `config.overlay.yaml` (torch/cpu, opencv capture)
- Env: `.env.example`
- OpenVINO IR на устройство не требуется — только `.pt`

## Ограничения (сейчас)

- Декод/encode через NVDEC/NVENC в коде ещё не реализованы (`ffmpeg_nvdec` — в планах).
- TensorRT — будущий этап; сейчас torch.

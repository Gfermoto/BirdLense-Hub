# Intel NUC (x86_64)

Дефолтный профиль BirdLense Hub: **OpenVINO IR** + **VA-API** / `ffmpeg_vaapi`, образ `app/Dockerfile`, при деплое — `docker-compose.override.yml` для `/dev/dri`.

## Деплой

```bash
# Без переменной — тот же путь, что раньше
make deploy
```

Опционально в `scripts/deploy.local.sh`:

```bash
export BIRDLENSE_PLATFORM=intel_nuc
export BIRDLENSE_DEPLOY_REQUIRE_INTEL_GPU=1   # если нужен OpenVINO GPU в контейнере
```

## Конфиг

- Overlay: `config.overlay.yaml`
- Env-подсказки: `.env.example`
- Примеры: `app/app_config/user_config.openvino-intel.example.yaml`

## Веса

Нужны `.pt` и каталог `*_openvino_model/` (Trapper @704 или NABirds). Проверка: `make sync-models` / `scripts/sync_trapper_weights.sh --check`.

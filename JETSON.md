# BirdLense Hub — Jetson Nano

Ветка **`jetson-nano`**: edge-runtime без Intel/OpenVINO. Для Intel NUC — ветка `dev` / `main`.

## Быстрый старт

| Кто | Документ | Команда |
|-----|----------|---------|
| **Оператор (устройство)** | [docs/user/jetson-nano-quickstart.md](docs/user/jetson-nano-quickstart.md) | `sudo ./scripts/jetson-setup.sh` на Jetson |
| **Разработчик (полный runbook)** | [docs/strategy/jetson-nano-edge-setup-and-migration.md](docs/strategy/jetson-nano-edge-setup-and-migration.md) | §2 шаги 1–20 |
| **Профиль deploy** | [deploy/profiles/jetson-nano/README.md](deploy/profiles/jetson-nano/README.md) | overlay + `.env.example` |

## Стек (production)

| Этап | Модель | Backend |
|------|--------|---------|
| Детектор | TrapperAI v02.2024 | TensorRT `.engine` @704 *(после Jetson PyTorch в образе)*; bootstrap: torch `.pt` |
| Классификатор | chriamue EfficientNet (525 spp) | ONNX Runtime CUDA |
| ReID / welfare | Ornimetrics | ONNX CUDA |
| Behavior | meta | logistic_json |
| Видео | OpenCV lores + CPU libx264 | без VA-API / OpenVINO |

## Makefile (на Jetson или dev с SSH)

```bash
export BIRDLENSE_PLATFORM=jetson_nano
make jetson-config          # user_config из overlay + site.env
make jetson-fetch-models    # HF: trapper pt, chriamue, ornimetrics
make jetson-build           # UI локально + docker build на целевом хосте
make jetson-up              # compose up
make jetson-verify          # health + status API
make jetson-trt             # ONNX → .engine (на устройстве)
```

## Что в ветке / чего нет

**Есть:** `Dockerfile.jetson`, `docker-compose.jetson.yml`, overlay, fetch/prune/TRT скрипты, документация.

**Нет в git (нормально):** веса `app/processor/models/**`, `user_config.yaml`, `app/.env`, `site.env` — только примеры `*.example.*`.

**Не использовать на Jetson:** OpenVINO IR, Birder EU-707, `detection/weights/`, Intel VA-API, Ornimetrics species packs, Hailo `.hef`.

## Деплой с dev-машины

```bash
# scripts/deploy.local.sh — блок Jetson
export BIRDLENSE_PLATFORM=jetson_nano
make deploy
```

Веса и `user_config.yaml` на устройстве **не перезаписываются** rsync (данные на SSD).

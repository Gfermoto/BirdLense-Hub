# Jetson Nano (aarch64)

Отдельный образ `app/Dockerfile.jetson` и override `app/docker-compose.jetson.yml` (Jetson L4T, лимиты RAM, `runtime: nvidia`).

Текущий проверенный base: `nvcr.io/nvidia/l4t-base:r32.7.1`. DeepStream (`deepstream-l4t:*`, `nvinfer`, `nvtracker`) требует отдельного gate: NGC auth или native DeepStream SDK install.

## Хранение (SD + SSD)

Runbook **rev.7**: корень на **microSD**, на SSD — bind-mount:

- `~/BirdLense/app/data` → клипы, SQLite
- `~/BirdLense/app/processor/models` → `.pt` / TRT `.engine`
- Docker `data-root` → `/mnt/ssd/docker`

Полный порядок: `docs/strategy/jetson-nano-edge-setup-and-migration.md` §2.0, шаги 5–8.

## Runtime hygiene

Jetson — runtime edge, не dev-копия репозитория. На устройство не копировать:

- `docs/`, `.github/`, `datasets/`, `site/`, venv, `node_modules`
- тестовые логи, benchmark artifacts, старые UI-каталоги
- полные Markdown/docs наборы и tooling для разработки

Синхронизация только allowlist из runbook §2, шаг 12. После deploy `tree -L 2 ~/BirdLense` должен показывать малый runtime bundle: `app/`, `scripts/`, `Makefile`, `VERSION`, без dev-мусора.

## Деплой

В `scripts/deploy.local.sh`:

```bash
export DEPLOY_HOST="gfer@192.168.1.127"
export DEPLOY_URL="http://192.168.1.127:8085"
export BIRDLENSE_PLATFORM=jetson_nano
```

```bash
make deploy
```

`make deploy` запускается на dev-машине, но:

- UI (`app/ui/dist`) собирается локально на dev.
- Docker-образ `birdlense` собирается на Jetson по SSH (`cd app && make build` на целевом хосте).
- `user_config.yaml` на Jetson не перезаписывается (исключён из rsync), поэтому камеры/Go2RTC/MQTT остаются из текущего рабочего конфига.
- `app/processor/models` на Jetson не удаляется деплоем; в режиме Jetson проверяется только факт наличия детекторного `.pt`.

Локально на Jetson:

```bash
cd app
docker compose -f docker-compose.yml -f docker-compose.jetson.yml config >/tmp/birdlense-compose-config.yml
```

Полный production `up -d --build` — после решения detector TensorRT adapter (#648/#651). Smoke overlay удалён из target bundle; web-only/processor-disabled запуск не закрывает Jetson ML gate.

## Desk preflight (2026-06-18)

Проверено на столе без камер:

- reboot resilience: SSH вернулся, SSD bind-mounts поднялись
- `gdm` inactive/masked, `multi-user.target`
- MAXN + ZRAM + `jtop.service` active
- Docker root `/mnt/ssd/docker`, default runtime `nvidia`
- `docker compose ... config` OK
- GPU smoke: `l4t-base:r32.7.1` видит `/dev/nvhost-gpu` и `/dev/nvmap`
- Исторический Hub desk smoke подтвердил web/nginx shell; smoke overlay удалён из target bundle.
- NUC settings copied: `user_config.yaml` без моков; go2rtc/MQTT/RTSP `192.168.1.11` недоступны на столе и остаются site-pending

MVP detector: TrapperAI `trapper_ai_v02_2024` → ONNX @1024 → FP16 `trapper_ai_v02_2024.engine` (карточка [OSCF/TrapperAI-v02.2024](https://huggingface.co/OSCF/TrapperAI-v02.2024)); классы из `model.names` в `.pt` → `class_maps/trapper_ai_v02_2024.yaml`. Legacy `yolo11n.*` — удалить после smoke (`jetson_models_prune.sh`).

## Конфиг

- Overlay: `config.overlay.yaml` (без Intel/OpenVINO)
- Env: `.env.example`
- Сборка `user_config.yaml` на dev: `python3 scripts/build_jetson_user_config.py`
- Bootstrap без `.engine`: `--bootstrap-torch`
- OpenVINO IR на устройство **не** требуется.

## Стек нейросетей (2026-06-22)

| Этап | Модель | Backend |
|------|--------|---------|
| Детектор | TrapperAI v02.2024 | TensorRT `.engine` @704 (fallback `.pt` torch) |
| Классификатор | chriamue EfficientNet | ONNX Runtime CUDA |
| ReID / welfare | Ornimetrics | ONNX Runtime CUDA |
| Behavior | meta | logistic_json |

Подробно: `docs/strategy/jetson-nano-edge-setup-and-migration.md` §0.1.

## Модели на Jetson (flat layout, без `weights/`)

```text
app/processor/models/
  detection/trapper_ai_v02_2024/
    trapper_ai_v02_2024.engine
    trapper_ai_v02_2024.onnx
    trapper_ai_v02_2024.pt
    trapper_ai_v02_2024.yaml          # class map (рядом с весами)
  classification/chriamue_bird_species_classifier/
    model.onnx, config.json, …
  reid/ornimetrics/reid_embedder.onnx
  welfare/ornimetrics/embedder.onnx + welfare_scorer.npz
```

Скрипты:

```bash
./scripts/fetch_chriamue_classifier.sh
./scripts/fetch_ornimetrics_jetson.sh          # reid + welfare only
./scripts/export_trapper_detector_trt.sh         # imgsz=704 default (TRAPPER_IMGSZ=1024 if headroom)
JETSON_PRUNE_DRY_RUN=0 ./scripts/jetson_models_prune.sh app/processor/models
```

### Почему веса есть на Jetson, а локально может не быть

Это нормальный сценарий edge-runtime:

- dev-репозиторий может быть «лёгким» (без полных весов), чтобы не таскать сотни МБ/ГБ в git/workspace;
- боевые веса хранятся на Jetson (`/home/gfer/BirdLense/app/processor/models`, часто bind на SSD);
- deploy синхронизирует код и не должен ломать layout моделей на устройстве.

Если нужно проверить удалённо только наличие файлов (без изменений), используйте:

```bash
ssh gfer@192.168.1.127 'cd /home/gfer/BirdLense && find app/processor/models -maxdepth 4 -type f | sort'
```

Если SSH не проходит (`Permission denied`), сначала восстановить доступ ключом/паролем, затем повторить `make deploy`.

**Не держать на Jetson:** `yolo11n.*`, `best.pt`, `classification/ornimetrics/species_*`, `detection/ornimetrics/`, `.hef`, dev-веса Intel/NUC, `ornimetrics_model_card.md`.

### Безопасная сборка TensorRT (4 GB Nano)

Перезагрузки/отключения часто от **OOM или просадки питания** при `trtexec` + Docker + MAXN:

1. `docker stop birdlense` перед конвертацией (скрипт делает по умолчанию).
2. **704px** — дефолт TrapperAI ONNX/TRT (`TRAPPER_IMGSZ=704`); при запасе RAM — `TRAPPER_IMGSZ=1024`.
3. Один `trtexec` за раз, `TRTEXEC_WORKSPACE_MB=256`.
4. После `.engine` — `docker start birdlense`, smoke `/api/health`.

Классификатор: [chriamue/bird-species-classifier](https://huggingface.co/chriamue/bird-species-classifier) — 525 видов, EfficientNet; `classifier_engine: chriamue`, backend `onnxruntime` (или `torch` если ONNX нет на HF). Ornimetrics — только reid + welfare.

## Мониторинг

- `tegrastats --interval 1000` — встроен в JetPack/L4T.
- `jtop` / `jetson_release` — пакет `jetson-stats` (`sudo -H pip3 install -U jetson-stats`).
- Проверка MAXN: `sudo nvpmodel -q`; путь `nvpmodel` на Nano: `/usr/sbin/nvpmodel`.
- Docker Compose v2: `/usr/local/lib/docker/cli-plugins/docker-compose`.

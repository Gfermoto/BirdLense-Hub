# BirdLense Hub на Jetson Nano

Краткая инструкция для оператора. Полный runbook: [jetson-nano-edge-setup-and-migration.md](../strategy/jetson-nano-edge-setup-and-migration.md).

## Требования

- Jetson Nano B01, JetPack 4.6.1 (L4T r32.7)
- microSD (система) + USB SSD (данные, Docker, веса)
- Docker + `nvidia` runtime
- Сеть: Go2RTC, MQTT, камеры в LAN

## 1. Клонировать ветку

```bash
git clone -b jetson-nano https://github.com/Gfermoto/BirdLense-Hub.git BirdLense
cd BirdLense
```

## 2. Настроить площадку

```bash
cp deploy/profiles/jetson-nano/site.example.env deploy/profiles/jetson-nano/site.env
# Отредактируйте: MQTT, Go2RTC, пароли, UI_BASE_URL (NAT)
nano deploy/profiles/jetson-nano/site.env

cp deploy/profiles/jetson-nano/.env.example app/.env
# Допишите FLASK_SECRET_KEY / PROCESSOR_SECRET (setup сгенерирует при первом запуске)
```

## 3. Установка одной командой

На Jetson (из корня репозитория):

```bash
chmod +x scripts/jetson-setup.sh scripts/*.sh
sudo ./scripts/jetson-setup.sh
```

Этапы: конфиг → скачивание моделей → сборка образа → запуск → проверка API.

### TensorRT (после первого запуска)

На 4 GB Nano Hub останавливается на время сборки:

```bash
./scripts/jetson_finish_trapper_trt.sh
```

Или: `make jetson-trt`

## 4. Проверка

```bash
curl -s http://127.0.0.1:8085/api/ui/status | jq .
# processor, mqtt, video, yolo → "ok"
```

UI: `http://<IP-устройства>:8085` (или внешний NAT-порт).

Пароль настроек — из `site.env` → `SETTINGS_PASSWORD`.

## Модели (на устройстве, не в git)

| Компонент | Путь |
|-----------|------|
| Trapper detector | `app/processor/models/detection/trapper_ai_v02_2024/` |
| Classifier | `app/processor/models/classification/chriamue_bird_species_classifier/` |
| ReID / welfare | `app/processor/models/reid/ornimetrics/`, `welfare/ornimetrics/` |

Скачать вручную:

```bash
make jetson-fetch-models
```

Удалить Intel/legacy веса:

```bash
JETSON_PRUNE_DRY_RUN=0 ./scripts/jetson_models_prune.sh app/processor/models
```

## Обновление

С dev-машины (ветка `jetson-nano`):

```bash
export BIRDLENSE_PLATFORM=jetson_nano
# scripts/deploy.local.sh — DEPLOY_HOST, DEPLOY_URL
make deploy
```

`user_config.yaml` и веса на SSD **не затираются**.

## Стек нейросетей

| Этап | Backend |
|------|---------|
| Детектор TrapperAI | TensorRT `.engine` @704 |
| Классификатор chriamue | ONNX Runtime (CUDA) |
| ReID / welfare | Ornimetrics ONNX |
| Behavior | meta / logistic_json |
| Видео | OpenCV + CPU libx264 (без Intel VA-API) |

Подробнее: [JETSON.md](../../JETSON.md), §0.1 runbook.

## Troubleshooting

| Симптом | Действие |
|---------|----------|
| Processor restart loop | `bash scripts/jetson-post-recreate-bootstrap.sh` после `docker compose up --force-recreate` |
| Нет `.engine` | `make jetson-trt` или временно `make jetson-config JETSON_BOOTSTRAP=1` |
| TRT: `torch.version.cuda is None` | В образе пока CPU torch с PyPI — используйте `make jetson-config JETSON_BOOTSTRAP=1` (`.pt` torch) до wheel Jetson PyTorch в `Dockerfile.jetson` |
| Не пускает в настройки | Проверьте `SETTINGS_PASSWORD` в `site.env`, пересоберите конфиг: `make jetson-config` |

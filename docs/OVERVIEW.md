# Overview (moved)

> **Do not edit this stub.** It exists for old bookmarks and external links to `docs/OVERVIEW.md`.

This page moved to **current documentation**:

**[user/overview.md](user/overview.md)**

---

## Модельный стек

Все модели — ONNX, инференс через ONNX Runtime CUDA EP на `cuda:0`.

| Компонент | Модель | Путь |
|-----------|--------|------|
| Детектор | Trapper AI v02 2024 (YOLO) | `models/detection/trapper_ai_v02_2024/` |
| Классификатор | Birder ConvNeXt EU-707 (birder_eu) | `models/classification/convnext_v2_tiny_eu-common256px/` |
| ReID | Ornimetrics reid_embedder | `models/reid/ornimetrics/` |
| Welfare | Ornimetrics embedder + scorer | `models/welfare/ornimetrics/` |
| Трекер | ByteTrack unstick | — |

## Компоненты

- **web/** — Flask API (OpenAPI), MQTT, Go2RTC, Frigate интеграции
- **processor/** — ONNX GPU инференс, GStreamer NVDEC/NVENC
- **ui/** — React 19 + MUI (Node 22)
- **data/** — SQLite, записи, кропы
- **app_config/** — user_config.yaml

## Сеть

- MQTT (BirdNET, Frigate)
- RTSP / Go2RTC
- Web UI: порт 8085

## Платформа

- Jetson Orin NX 16GB / Orin NANO 8GB
- Docker, NVIDIA runtime, host network, privileged
- NVDEC/NVENC аппаратное кодирование
- `Dockerfile.orin`, `docker-compose.orin.yml`

См. [`strategy/orin-setup-and-migration.md`](strategy/orin-setup-and-migration.md) для полного runbook.
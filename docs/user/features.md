# Возможности BirdLense Hub

## Основные функции

- **Детекция** — Trapper AI (YOLO ONNX GPU) находит птиц и грызунов
- **Классификация** — Birder ConvNeXt EU-707 (ONNX GPU), ~707 видов Европы
- **ReID** — Ornimetrics (ONNX GPU) — идентификация особи
- **Welfare** — Ornimetrics (ONNX GPU) — оценка состояния птицы
- **Трекер** — ByteTrack unstick — стабильное отслеживание в кадре

## Интерфейс

- Timeline (дата + время суток)
- Экспорт CSV / JSON / eBird
- PDF-отчёт
- «Неизвестные» птицы
- iNaturalist, Xeno-canto интеграция
- Prometheus метрики

## Интеграции

- MQTT (BirdNET, Frigate)
- Go2RTC
- Frigate events
- MCP API для внешних агентов

## Платформа

- Jetson Orin NX 16GB / Orin NANO 8GB
- ONNX Runtime CUDA EP
- NVDEC/NVENC аппаратное кодирование
- Docker контейнеризация
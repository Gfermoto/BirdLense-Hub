# BirdLense Hub — обзор

**BirdLense Hub** — open-source система мониторинга птиц на Jetson Orin. Детекция, классификация, ре-идентификация и анализ визитов — всё локально, без облака.

## Как работает

1. IP-камера отправляет RTSP поток
2. Детектор (Trapper AI ONNX) находит птиц в кадре
3. Классификатор (Birder ConvNeXt ONNX) определяет вид
4. ReID (Ornimetrics ONNX) идентифицирует особь
5. Welfare (Ornimetrics ONNX) оценивает состояние
6. Система записывает видео, сохраняет метаданные, отображает в веб-интерфейсе

## Целевая платформа

- Jetson Orin NX 16GB / Orin NANO 8GB
- Docker, NVIDIA runtime
- ONNX Runtime CUDA EP / TensorRT EP
- NVDEC/NVENC аппаратное кодирование

## Модельный стек

| Компонент | Модель | Бэкенд |
|-----------|--------|--------|
| Детектор | Trapper AI v02 2024 (YOLO) | ONNX Runtime CUDA EP |
| Классификатор | Birder ConvNeXt EU-707 | ONNX Runtime CUDA EP |
| ReID | Ornimetrics reid_embedder | ONNX Runtime CUDA EP |
| Welfare | Ornimetrics embedder + scorer | ONNX Runtime CUDA EP |
| Трекер | ByteTrack unstick | CPU |

## Ссылки

- [Быстрый старт](quickstart.md)
- [Установка](install.md)
- [Конфигурация](configuration.md)
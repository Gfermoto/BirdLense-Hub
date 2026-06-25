# Производительность процессора

## Целевая платформа

Jetson Orin NX 16GB / Orin NANO 8GB.

## Оценка производительности

Параметры:
- Детектор: Trapper AI (YOLO ONNX) — imgsz 640
- Классификатор: Birder ConvNeXt (ONNX)
- ReID + Welfare: Ornimetrics (ONNX)

| Компонент | Время на кадр (ориентировочно) |
|-----------|-------------------------------|
| Декодирование (NVDEC) | ~2-5ms |
| Детектор | ~15-30ms |
| Классификатор | ~5-10ms |
| ReID | ~5-10ms |
| Welfare | ~3-5ms |

Общая задержка на кадр с птицей: ~30-60ms.

## Бутылочные горлышки

- Загрузка CPU при большом числе RTSP потоков
- Память GPU: Orin NANO 8GB — до ~4 потоков 1080p
- NVDEC сессий: до 16 параллельных

## Мониторинг

```bash
# Использование GPU
docker exec birdlense-hub nvidia-smi
# Метрики процессора
curl http://localhost:8085/api/health
```
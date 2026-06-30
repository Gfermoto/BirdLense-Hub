<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Hub Logo">
</p>

# BirdLense Hub

Мониторинг птиц у кормушек на **Jetson Orin**: компьютерное зрение (ONNX GPU) для детекции, классификации, идентификации и анализа визитов. Всё на своём железе, без облака.

**Полный ONNX GPU стек:**

| Компонент | Модель | Бэкенд |
|-----------|--------|--------|
| Детектор | Trapper AI v02 2024 (YOLO) | ONNX Runtime CUDA EP / TensorRT EP |
| Классификатор | Birder ConvNeXt EU-707 (birder_eu) | ONNX Runtime CUDA EP |
| ReID | Ornimetrics reid_embedder | ONNX Runtime CUDA EP |
| Welfare | Ornimetrics embedder + scorer | ONNX Runtime CUDA EP |
| Трекер | ByteTrack unstick | CPU (боксы) |

**Документация:** [`docs/`](docs/index.md) · [Быстрый старт](docs/QUICKSTART.md) · [Обзор](docs/user/overview.md)

## Быстрый старт

```bash
cd app
cp .env.example .env          # отредактировать токены
make build && make start
```

Подробнее: [`docs/INSTALL.md`](docs/INSTALL.md) · [`docs/QUICKSTART.md`](docs/QUICKSTART.md)

## Архитектура

```
app/
├── web/          # Flask API (OpenAPI)
├── processor/    # ONNX GPU — детекция, классификация, ReID
├── ui/           # React 19 + MUI (Node 22)
├── data/         # записи, БД
└── app_config/   # конфигурация
```

Makefile: `deploy`, `build`, `start`, `stop`, `logs`, `verify`.

## Орнитология

- Timeline (дата + время суток)
- Экспорт CSV / JSON / eBird
- PDF-отчёт
- Неизвестные птицы
- iNaturalist, Xeno-canto

---

**Платформа:** Jetson Orin NX 16GB / Orin NANO 8GB · Docker · NVIDIA runtime · ONNX Runtime · NVDEC/NVENC · GStreamer
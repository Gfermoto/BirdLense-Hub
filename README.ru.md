<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Hub Logo">
</p>

# BirdLense Hub

Мониторинг птиц у кормушек на **Jetson Orin**: пять нейросетей последовательно — детекция, классификация вида, идентификация конкретной особи, оценка её здоровья и построение траектории. Всё локально, без облака.

## Модельный стек — ONNX GPU

Каждая модель работает на **ONNX Runtime CUDA EP** (`cuda:0`) на GPU Jetson Orin.

| # | Компонент | Модель | Что делает | Бэкенд |
|---|-----------|--------|------------|--------|
| ① | **Детектор** | Trapper AI v02 2024 (YOLO) | Находит птицу или Rodent в кадре, bounding box | ORT CUDA EP |
| ② | **Классификатор** | Birder ConvNeXt EU-707 (birder_eu) | Определяет вид: 707 европейских птиц | ORT CUDA EP |
| ③ | **Трекер** | ByteTrack unstick | Связывает боксы в треки → траектория движения | CPU |
| ④ | **ReID** | Ornimetrics reid_embedder | Узнаёт особь: тот же воробей или другой? | ORT CUDA EP |
| ⑤ | **Welfare** | Ornimetrics embedder + scorer | Mahalanobis-скрининг vs здоровый baseline → флаг на просмотр | ORT CUDA EP |

**Документация:** [`docs/`](docs/index.md) · [Обзор архитектуры](docs/OVERVIEW.md) · [Быстрый старт](docs/QUICKSTART.md)

## Как это работает

```
IP-камера → Детектор (птица?) → Классификатор (какой вид?)
                                  → Трекер (траектория)
                                  → ReID (кто именно?)
                                  → Welfare (здоров?)
                                  → Запись + UI
```

Scoring Engine отсеивает ложные срабатывания (confidence + motion + форма + фон). Первые 60 секунд — авто-калибровка под сцену. Результат — Accept / Review / Reject.

## Быстрый старт

```bash
cd app
cp .env.example .env          # отредактировать токены
make build && make start
```

Подробнее: [Установка](docs/user/install.md) · [Быстрый старт](docs/user/quickstart.md)

## Архитектура

```
app/
├── web/          # Flask API (OpenAPI), MQTT, Go2RTC
├── processor/    # ONNX GPU: детекция, классификация, ReID, Welfare
├── ui/           # React 19 + MUI (Node 22)
├── data/         # записи MP4, БД, кропы
└── app_config/   # user_config.yaml
```

Makefile: `deploy`, `build`, `start`, `stop`, `logs`, `verify`.

## Орнитология

- **Timeline** — дата + время суток (утро/день/вечер/ночь)
- **CSV / JSON / eBird** — экспорт визитов для анализа
- **PDF-отчёт** — месячная сводка: виды, топ-5, графики
- **Неизвестные птицы** — Review-зона + best-guess классификатор
- **Интеграции** — iNaturalist, Xeno-canto, BirdNET (аудио), Telegram

---

**Платформа:** Jetson Orin NX 16GB / Orin NANO 8GB · Docker · NVIDIA runtime · ONNX Runtime CUDA EP · GStreamer NVDEC/NVENC

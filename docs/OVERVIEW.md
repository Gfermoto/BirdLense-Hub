# BirdLense Hub — обзор архитектуры (Orin)

## Назначение

BirdLense Hub — система мониторинга птиц у кормушек на базе Jetson Orin. Пять нейросетевых компонентов работают последовательно: **детекция → классификация → идентификация особи → оценка здоровья → отслеживание траектории**. Всё локально, без облака.

## Поток данных

```
IP-камера → RTSP → Go2RTC (NVDEC)
                         │
                         ▼
              ①  Детектор (Trapper AI ONNX)
                  Бинарный YOLO: птица / Rodent / фон
                         │
                   есть птица?
                    /        \
                  да          нет → пропуск
                  │
                  ▼
              ②  Классификатор (Birder ConvNeXt ONNX)
                  707 видов птиц Европы — вид + уверенность
                  │
                  ▼
              ③  Трекер (ByteTrack unstick)
                  Привязка боксов к трекам → траектория
                  │
                  ▼
              ④  ReID (Ornimetrics reid_embedder ONNX)
                  Эмбеддинг особи → кто именно прилетел?
                  Cosine similarity по галерее кандидатов
                  │
                  ▼
              ⑤  Welfare (Ornimetrics ONNX + NPZ)
                  Оценка состояния: перьевой покров, активность
                  │
                  ▼
            Запись MP4 + кропы + веб-интерфейс
```

## Модельный стек — подробно

Все пять компонентов работают на **ONNX Runtime CUDA EP** (`cuda:0`) на GPU Jetson Orin.

### ① Детектор — Trapper AI v02 2024 (YOLO)

- **Задача:** найти птицу (или Rodent) в кадре, выдать bounding box
- **Архитектура:** YOLO, бинарный классификатор (bird / Rodent)
- **Формат:** ONNX
- **Бэкенд:** ONNX Runtime CUDA EP или TensorRT EP
- **Размер входа:** 704px (`binary_imgsz`)
- **Порог:** `min_confidence_binary` (0.08–0.12)
- **Путь:** `models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx`

### ② Классификатор — Birder ConvNeXt EU-707

- **Задача:** определить вид птицы из 707 классов европейских птиц
- **Архитектура:** ConvNeXt V2 Tiny (birder_eu), предобучен на birds-525 + iNaturalist Europe
- **Формат:** ONNX
- **Бэкенд:** ONNX Runtime CUDA EP
- **Размер входа:** 256px (common)
- **Порог:** `birder_eu_min_confidence` (0.15), best-guess от 0.10
- **Путь:** `models/classification/convnext_v2_tiny_eu-common256px/convnext_v2_tiny_eu-common256px.onnx`
- **Особенность:** кэш классификатора по bounding box + cosine similarity для стабильности между кадрами

### ③ Трекер — ByteTrack unstick

- **Задача:** привязать bounding box'ы к индивидуальным трекам во времени → построить траекторию движения птицы
- **Алгоритм:** ByteTrack (YAML-конфиг), Kalman-фильтр + IoU-ассоциация
- **Бэкенд:** CPU (боксы)
- **Конфиг:** `models/tracker/bytetrack_birdlense.yaml`
- **Особенность:** unstick-режим — восстановление потерянных треков для кормушек с возвратом птиц на то же место

### ④ ReID — Ornimetrics reid_embedder

- **Задача:** узнать конкретную особь — тот же самый воробей или другой?
- **Модель:** Ornimetrics reid_embedder (обучен на птицах, прод-веса ONNX)
- **Формат:** ONNX
- **Бэкенд:** ONNX Runtime CUDA EP
- **Как работает:**
  - Извлекает эмбеддинг из кропа птицы
  - Сравнивает (cosine similarity) с галереей ранее виденных особей того же вида
  - Порог совпадения: `cosine ≥ 0.92` → та же особь
  - Галерея кандидатов кэшируется (TTL 120с) для быстрого поиска
- **Путь:** `models/reid/ornimetrics/reid_embedder.onnx`

### ⑤ Welfare — Ornimetrics embedder + welfare_scorer

- **Задача:** скрининг аномалий состояния — насколько птица отклоняется от распределения «здоровых» в feature space
- **Модели:** `embedder.onnx` (1280-d эмбеддинг кропа) + `welfare_scorer.npz` (`mean`, `inv_cov`)
- **Формат:** ONNX + NPZ
- **Бэкенд:** ONNX Runtime CUDA EP
- **Как работает:**
  - После ReID извлекается эмбеддинг из кропа птицы
  - Mahalanobis distance к здоровому baseline: выше = необычнее (не диагноз, флаг на ручной просмотр)
  - Порог: `processor.welfare.distance_review_threshold` (по умолчанию 75 — калибровать на площадке)
  - При превышении: `welfare_needs_review` + `review_reason=welfare_anomaly`
- **Пути:** `models/welfare/ornimetrics/embedder.onnx`, `models/welfare/ornimetrics/welfare_scorer.npz`
- **Runtime:** `welfare_runtime.py` → `enrich_runtime_welfare_detections()` в finalize после ReID

## Scoring Engine — фильтр ложных срабатываний

Перед сохранением записи каждый визит проходит через **ScoringEngine** — взвешенную оценку качества:

| Фактор | Вес | Описание |
|--------|-----|----------|
| Confidence детектора | высокий | Уверенность YOLO в bounding box |
| Motion score | средний | Интенсивность движения в области |
| Форма (shape) | средний | Соответствие пропорциям птицы |
| Фон (background) | низкий | Яркость/контраст фона |
| Frigate-буст | бонус | Если Frigate подтверждает детекцию |

Зоны принятия решения: **Accept** (сохранить) / **Review** (сохранить с пометкой) / **Reject** (пропустить). Первые ~60 секунд — авто-калибровка порогов под сцену.

## Аппаратное кодирование

- **Декодирование:** NVDEC через GStreamer (`nvv4l2decoder`) — захват lores-потока для детекции
- **Кодирование записи:** NVENC через FFmpeg (`h264_nvenc`) или GStreamer — main-поток в MP4

## Компоненты приложения

- **web/** — Flask API (OpenAPI), MQTT, Go2RTC, Frigate интеграции
- **processor/** — ONNX GPU инференс, GStreamer NVDEC/NVENC, ByteTrack
- **ui/** — React 19 + MUI (Node 22), PWA
- **data/** — SQLite, записи MP4, кропы, decision traces
- **app_config/** — `user_config.yaml`, `default_config.yaml`

## Интеграции

- **Go2RTC / Frigate** — RTSP-потоки с IP-камер
- **MQTT** — события Frigate, детекции BirdNET (аудио)
- **Telegram** — уведомления о визитах
- **OpenWeather / Home Assistant** — погода
- **eBird / iNaturalist / Xeno-canto** — экспорт и справочная информация

## Платформа

- Jetson Orin NX 16GB / Orin NANO 8GB
- Docker, NVIDIA runtime, host network, privileged
- ONNX Runtime CUDA EP (CUDA 13)
- NVDEC/NVENC аппаратное кодирование
- `Dockerfile.orin`, `docker-compose.orin.yml`

См. [`strategy/orin-setup-and-migration.md`](strategy/orin-setup-and-migration.md) для полного runbook.

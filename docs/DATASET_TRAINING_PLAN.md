# План: сбор датасетов и обучение моделей

BirdLense Hub — **исследовательский инструмент** для орнитологии и компьютерного зрения: сбор данных с кормушки, разметка, дообучение моделей. Подходит для научных статей и экспериментов.

Цель: использовать BirdLense Hub для сбора данных, разметки и дообучения моделей детекции/классификации птиц. Максимально задействовать MCP для автоматизации через AI-агентов.

---

## 1. Существующие скрипты и модели

**Инвентарь:** [DATASET_SCRIPTS.md](./DATASET_SCRIPTS.md) — полный список скриптов и моделей.

Кратко: `scripts/datasets/` — NABirds, COCO, OIDv4 → YOLO; `scripts/birds_train*.ipynb` — обучение на RunPod; `processor/models/` — best.pt (binary, classifier).

---

## 2. Пайплайн: сбор → разметка → обучение

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЭТАП 1: Сбор данных                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  BirdLense Hub (live) → data/recordings/YYYY/MM/DD/HHMMSS/video.mp4              │
│  Processor → DB: Video, VideoSpecies (species, frames, bbox)                 │
│  Опция: save_images → crops (нужно доработать)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЭТАП 2: Экспорт в YOLO (новый скрипт)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  export_birdlense_to_yolo.py                                                 │
│  • Читает Video, VideoSpecies из БД                                          │
│  • Для каждой детекции: crop по bbox из frames, сохраняет image + label      │
│  • Фильтр: confidence >= 0.5, min bbox size                                  │
│  • Выход: dataset/train/, dataset/val/, data.yaml                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЭТАП 3: Разметка / коррекция                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Ручная: LabelImg, CVAT, Roboflow                                          │
│  • Полуавто: UI BirdLense Hub — «Исправить вид» для VideoSpecies              │
│  • MCP: AI-агент анализирует low-confidence, предлагает правки              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЭТАП 4: Обучение / дообучение                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  • birds_train.ipynb — детектор (binary или multi-class)                     │
│  • birds_train_cls.ipynb — классификатор                                     │
│  • Дообучение: model.train(data='birdlense_export/data.yaml', epochs=50)      │
│  • RunPod / Colab / локально (GPU)                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЭТАП 5: Деплой новых весов                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Копировать best.pt в processor/models/detection/weights/                   │
│  • Копировать best.pt в processor/models/classification/weights/             │
│  • Перезапуск processor                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. MCP: как задействовать по максимуму

MCP экспортирует OpenAPI BirdLense Hub как инструменты для AI-агентов (Cursor, Claude и др.).

### 3.1 Релевантные MCP-инструменты (из OpenAPI)

Пути относительно `/api/ui/`:

| Инструмент | Использование в пайплайне |
|------------|---------------------------|
| `GET /videos/{id}` | Получить детекции с frames (bbox) для экспорта |
| `GET /timeline` | Список визитов по дате — выбор видео для датасета |
| `GET /species` | Список видов — маппинг id → name для YOLO classes |
| `GET /overview` | Статистика — какие виды чаще, приоритет дообучения |
| `GET /storage/stats` | Объём записей — оценка размера датасета |
| `POST /storage/purge` | Очистка старых записей (после экспорта) |
| `POST /system/recordings/scan` | Импорт новых видео в БД |
| `POST /system/regenerate-tracks` | Пересчёт треков (если изменилась модель) |
| `PATCH /settings` | Включить save_images, изменить min_track_duration |
| `GET /system/activity` | Активность по дням — выбор периодов для экспорта |

### 3.2 Сценарии с MCP

**Сценарий A: Анализ датасета**
- AI запрашивает `/overview`, `/species`, `/storage/stats`
- Формирует отчёт: сколько записей, какие виды, баланс классов
- Рекомендует: «Добавить больше Great Tit — мало примеров»

**Сценарий B: Подготовка экспорта**
- AI вызывает `/timeline` за период
- Для каждого video_id — `/videos/{id}` (frames, species)
- Генерирует скрипт или конфиг для `export_birdlense_to_yolo.py`

**Сценарий C: Коррекция разметки**
- AI получает детекции с low confidence
- Предлагает правку вида (например, «похоже на Blue Tit, не Great Tit»)
- Через новый эндпоинт `PATCH /videos/{id}/species/{vs_id}` (нужно добавить)

**Сценарий D: Автоматизация обучения**
- AI проверяет `/storage/stats` — если накопилось N записей
- Запускает экспорт (внешний скрипт или новый API)
- После обучения — инструкция по деплою весов

### 3.3 Примеры промптов для Cursor (с MCP BirdLense Hub)

- «Получи overview и storage/stats — сколько записей, какие виды чаще всего?»
- «Дай timeline за последние 7 дней — сколько видео с детекциями?»
- «Для video_id 42 получи детекции с frames — какие bbox и виды?»
- «Проанализируй баланс классов: запроси species и overview, предложи приоритеты для дообучения»
- «Сформируй список video_id за март с confidence > 0.7 для экспорта»

### 3.4 Расширения MCP для пайплайна

| Расширение | Описание |
|------------|----------|
| `POST /api/ui/system/export-dataset` | Запуск экспорта в YOLO (фоново) |
| `GET /api/ui/system/export-dataset/status` | Статус экспорта |
| `PATCH /api/ui/videos/{id}/species/{vs_id}` | Исправить вид детекции |
| OpenAPI: описание полей `frames`, `bbox` | Чтобы AI понимал формат |

---

## 4. Новые скрипты и доработки

### 4.1 Обязательные

| # | Скрипт/доработка | Назначение |
|---|-------------------|------------|
| 1 | `scripts/export_birdlense_to_yolo.py` | Экспорт Video+VideoSpecies → YOLO dataset |
| 2 | Доработка `save_images` в processor | Сохранять crops (не full frame) в `data/training_crops/` |
| 3 | `docs/DATASET_SCRIPTS.md` | Описание всех скриптов, примеры запуска |

### 4.2 Опциональные

| # | Скрипт/доработка | Назначение |
|---|-------------------|------------|
| 4 | `scripts/merge_birdlense_with_nabirds.py` | Объединение BirdLense Hub export + NABirds |
| 5 | UI: «Подтвердить» / «Исправить» в VideoDetails | Совместная разметка (как Frigate) |
| 6 | API: confirm, correct для VideoSpecies | Программная коррекция |
| 7 | `POST /system/export-dataset` | API-триггер экспорта |

---

## 5. Дорожная карта

### Фаза 1: Экспорт (1–2 дня)
- [ ] Реализовать `export_birdlense_to_yolo.py`
- [ ] Подключение к БД (SQLite), чтение Video, VideoSpecies
- [ ] Извлечение кадров из video.mp4 по frames
- [ ] Генерация YOLO labels (class_id x_center y_center w h)
- [ ] Train/val split 80/20
- [ ] Документация в DATASET_SCRIPTS.md

### Фаза 2: Сбор crops в реальном времени (опционально)
- [ ] Доработать processor: при `save_images` сохранять crops по видам
- [ ] Путь: `data/training_crops/{species_name}/{timestamp}_{track_id}.jpg`

### Фаза 3: MCP-интеграция (1 день)
- [ ] Добавить в OpenAPI описание `frames`, `bbox` для /videos
- [ ] Новый эндпоинт коррекции вида (если нужен)
- [ ] Примеры промптов для Cursor: «Проанализируй датасет», «Подготовь экспорт»

### Фаза 4: Обучение (существующие ноутбуки)
- [ ] Адаптировать `birds_train.ipynb` под путь `birdlense_export/`
- [ ] Адаптировать `birds_train_cls.ipynb` под classification crops из export
- [ ] Инструкция: RunPod/Colab, деплой весов

### Фаза 5: Совместная разметка (collaborative labeling)
- [ ] UI: «Подтвердить» / «Исправить» на каждой детекции (как во Frigate)
- [ ] Таблица `detection_feedback` или поля в VideoSpecies
- [ ] API: confirm, correct
- [ ] Опции «куда уходят данные»: локально, экспорт, opt-in в сообщество
- [ ] См. [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md)

---

## 6. Формат данных

### VideoSpecies.frames (JSON)
```json
[
  {"t": 2.5, "bbox": [0.1, 0.2, 0.3, 0.4]},
  {"t": 2.6, "bbox": [0.11, 0.21, 0.31, 0.41]}
]
```
- `t` — секунды от начала видео
- `bbox` — [x1, y1, x2, y2] нормализованные (0–1)

### YOLO label (на один кадр)
```
class_id x_center y_center width height
```
- Все значения 0–1
- Из bbox: `x_center = (x1+x2)/2`, `y_center = (y1+y2)/2`, `w = x2-x1`, `h = y2-y1`

### data.yaml (Ultralytics)
```yaml
path: ./birdlense_export
train: train/images
val: val/images
names:
  0: Great Tit
  1: Blue Tit
  2: House Sparrow
  ...
nc: 15
```

---

## 7. Ссылки

**См. также:** [DATASET_SCRIPTS.md](./DATASET_SCRIPTS.md) · [DATASET_SOURCES.md](./DATASET_SOURCES.md) · [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) · [ARCHITECTURE.md](./ARCHITECTURE.md) · [CONFIGURATION.md](./CONFIGURATION.md) · [MCP_SETUP.md](./MCP_SETUP.md) · [API.md](./API.md)

# План развития BirdLense Hub

Идеи и фичи на будущее. Не в порядке приоритета — для обсуждения.

---

## 1. Home Assistant — MQTT Autodiscovery

**Цель:** BirdLense Hub публикует сущности через существующее MQTT-подключение так, чтобы HA автоматически их обнаружил (autodiscovery).

### Текущее состояние

- BirdLense подключается к MQTT (Frigate, BirdNET, publish)
- Публикует в `birdlense/detections` — JSON с species, confidence, timestamp
- HA не обнаруживает автоматически — нужна ручная настройка MQTT sensor

### Что сделать

1. **MQTT Discovery** — публиковать конфиг в `homeassistant/<component>/birdlense_<id>/config`:
   - `homeassistant/sensor/birdlense_last_species/config` — последний обнаруженный вид
   - `homeassistant/sensor/birdlense_last_confidence/config` — confidence
   - `homeassistant/binary_sensor/birdlense_bird_detected/config` — птица у кормушки (on/off)
   - `homeassistant/sensor/birdlense_last_detection_time/config` — время последней детекции

2. **State topics** — обновлять state в топиках, на которые ссылается config:
   - `birdlense/sensor/last_species/state`
   - `birdlense/sensor/last_confidence/state`
   - `birdlense/binary_sensor/bird_detected/state`

3. **Device** — объединить в один device «BirdLense Hub» (device_id, device_name) для удобства в HA.

### Формат config (пример)

```json
{
  "name": "BirdLense Last Species",
  "unique_id": "birdlense_last_species",
  "state_topic": "birdlense/sensor/last_species/state",
  "device": {
    "identifiers": ["birdlense_hub"],
    "name": "BirdLense Hub",
    "model": "Bird Feeder Monitor"
  }
}
```

### Зависимости

- MQTT broker уже настроен
- Один раз при старте — publish config
- При каждой детекции — publish state

---

## 2. Датасет из лучших кадров — экспорт архивом

**Цель:** Лучшие картинки (best_frame) сохраняются в формате YOLO classification (`train/ClassName/img.jpg`), формируют датасет. Пользователь может скачать архивом для дообучения.

### Текущее состояние

- `best_frame` — лучший crop по треку (резкость + размер) — хранится в памяти, передаётся в API
- `save_images` — сохраняет debug-кадры в `data/test/`, не по видам
- `export_birdlense_to_yolo.py` — планируется, не реализован

### Что сделать

1. **Сохранение best_frame на диск** — при merge/записи видео:
   - Путь: `data/dataset/train/<Species_Name>/<video_id>_<track_id>_<frame>.jpg`
   - Формат имени вида: `Scientific (Common)` — как в merged_cls
   - Фильтр: confidence >= 0.5, min crop size
   - Опция в конфиге: `processor.save_dataset_crops: true`

2. **Подтверждение/коррекция** — если пользователь исправил вид в UI:
   - Переместить файл в папку правильного вида (или создать копию)
   - Или помечать в метаданных (JSON) — `corrected_species_id`

3. **API экспорта** — скачать датасет архивом:
   - `GET /api/ui/dataset/export` → `birdlense_dataset_YYYYMMDD.zip`
   - Структура: `train/ClassName/*.jpg`, `val/` (опционально — split по датам или случайно)
   - Метаданные: `dataset_info.json` (источники, лицензия, кол-во по классам)

4. **Разметка** — использовать `species` из VideoSpecies (подтверждённый или исправленный пользователем). Если не подтверждено — использовать YOLO prediction с пометкой.

### Структура архива

```
birdlense_dataset_20260315.zip
├── train/
│   ├── Parus major (Great Tit)/
│   │   ├── 20260315_123456_1_042.jpg
│   │   └── ...
│   └── Garrulus glandarius (Eurasian Jay)/
├── val/                    # опционально, 20% по дате
├── dataset_info.json      # {classes: [...], counts: {...}, sources: [...]}
└── README.txt             # краткое описание
```

### Зависимости

- Доступ к frames/crops из processor при записи
- VideoSpecies.species_id → Species.name для имени папки
- API endpoint + streaming zip (или генерация во временную папку)

---

## См. также

- [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md) — пайплайн сбора и обучения
- [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) — подтверждение/исправление в UI
- [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md) — текущие MQTT-топики
- [CONFIGURATION.md](./CONFIGURATION.md) — конфиг processor, MQTT

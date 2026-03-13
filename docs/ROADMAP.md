# План развития BirdLense Hub

Апгрейды зависимостей и идеи на будущее. Март 2026.

---

## Часть 1: Апгрейды и зависимости

### Выполнено

| # | Действие | Статус |
|---|----------|--------|
| 1 | Docker base `ultralytics/ultralytics:8.4.21` | ✅ |
| 2 | Уязвимости: npm (Vite 6, @tanstack/form 0.42), Python (requests, PyYAML, numpy 2) | ✅ |
| 3 | Конфликт numpy/opencv: lapx удалён, librosa 0.11, matplotlib 3.8 | ✅ |
| 4 | EU-классификатор YOLO11n-cls (birds-525 + iNaturalist) | ✅ [TRAINING.md](./TRAINING.md) |
| 5 | Vite 6 | ✅ |

### Дальнейшие шаги

| # | Действие | Сложность | Риск |
|---|----------|-----------|------|
| 6 | Добавить `ultralytics` в processor/requirements.txt (pin версии) | Низкая | Нет |
| 7 | Апгрейд React 19 | Средняя | Средний |
| 8 | Dependabot: 3 moderate (см. Security репозитория) | Низкая | Нет |

### Текущий стек

| | Версия |
|---|--------|
| **Ultralytics** | 8.4.21 (Docker base) |
| **Архитектура** | two_stage: binary + YOLO11n-cls (EU) / single_stage: nabirds NCNN |
| **EU-модель** | `best.pt` — birds-525 + iNaturalist (~491 вид) |
| **US-модель** | `best_US.pt` — NABirds (резерв) |
| **React** | 18.3.1 |
| **Vite** | 6.4.1 |

---

## Часть 2: Фичи и улучшения

### 1. Home Assistant — MQTT Autodiscovery

**Цель:** BirdLense Hub публикует сущности через MQTT так, чтобы HA автоматически их обнаружил.

**Текущее:** Публикует в `birdlense/detections`. HA не обнаруживает автоматически — нужна ручная настройка MQTT sensor.

**Что сделать:**

1. **MQTT Discovery** — публиковать config в `homeassistant/<component>/birdlense_<id>/config`:
   - `homeassistant/sensor/birdlense_last_species/config` — последний вид
   - `homeassistant/sensor/birdlense_last_confidence/config`
   - `homeassistant/binary_sensor/birdlense_bird_detected/config` — птица у кормушки
   - `homeassistant/sensor/birdlense_last_detection_time/config`

2. **State topics** — обновлять state в топиках, на которые ссылается config.

3. **Device** — объединить в один device «BirdLense Hub».

### 2. Датасет из лучших кадров — экспорт архивом

**Цель:** Лучшие картинки (best_frame) сохраняются в формате YOLO classification, пользователь может скачать архивом для дообучения.

**Текущее:** `best_frame` хранится в памяти, передаётся в API. `save_images` — debug-кадры в `data/test/`, не по видам.

**Что сделать:**

1. **Сохранение best_frame на диск** — путь `data/dataset/train/<Species_Name>/<video_id>_<track_id>_<frame>.jpg`, формат `Scientific (Common)`, фильтр confidence >= 0.5. Опция `processor.save_dataset_crops: true`.

2. **Подтверждение/коррекция** — при исправлении вида в UI переместить файл или пометить в метаданных.

3. **API экспорта** — `GET /api/ui/dataset/export` → `birdlense_dataset_YYYYMMDD.zip` со структурой `train/ClassName/*.jpg`, `val/`, `dataset_info.json`.

4. **Разметка** — использовать `species` из VideoSpecies (подтверждённый или исправленный).

### 3. Прочее

- **Full screen video (iOS)** — средний приоритет
- **Track trajectory overlay** — низкий приоритет

---

См. также: [DATASETS.md](./DATASETS.md), [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md), [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md), [TESTING.md](./TESTING.md), [CONFIGURATION.md](./CONFIGURATION.md).

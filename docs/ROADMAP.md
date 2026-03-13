# План развития BirdLense Hub

Апгрейды зависимостей и идеи на будущее. Март 2026.

---

## Часть 1: Апгрейды и зависимости

### Выполнено


| #   | Действие                                                                          | Статус                         |
| --- | --------------------------------------------------------------------------------- | ------------------------------ |
| 1   | Docker base `ultralytics/ultralytics:8.4.21`                                      | ✅                              |
| 2   | Уязвимости: npm (Vite 6, @tanstack/form 0.42), Python (requests, PyYAML, numpy 2) | ✅                              |
| 3   | Конфликт numpy/opencv: lapx удалён, librosa 0.11, matplotlib 3.8                  | ✅                              |
| 4   | EU-классификатор YOLO11n-cls (birds-525 + iNaturalist)                            | ✅ [TRAINING.md](./TRAINING.md) |
| 5   | Vite 6                                                                            | ✅                              |
| 6   | ultralytics в processor/requirements.txt (pin 8.4.21)                             | ✅                              |


### Дальнейшие шаги


| #   | Действие         | Сложность | Риск    |
| --- | ---------------- | --------- | ------- |
| 7   | Апгрейд React 19 | Средняя   | Средний |


### Текущий стек


|                 | Версия                                                            |
| --------------- | ----------------------------------------------------------------- |
| **Ultralytics** | 8.4.21 (Docker base)                                              |
| **Платформа**   | x86/amd64 (ARM не поддерживается)                                 |
| **Архитектура** | two_stage: binary (.pt) + YOLO11n-cls (EU). single_stage — fallback при отсутствии моделей |
| **EU-модель**   | `best.pt` — birds-525 + iNaturalist (~491 вид)                    |
| **US-модель**   | `best_US.pt` — NABirds (резерв)                                   |
| **React**       | 18.3.1                                                            |
| **Vite**        | 6.4.1                                                             |


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

### 3. Новые предложения

От простого к сложному:

| Фича | Описание | Сложность | Риск |
|------|----------|-----------|------|
| Playback speed (0.5x, 2x) | Кнопки в видеоплеере для замедления/ускорения просмотра | Низкая | Нет |
| Webhook (POST при детекции) | POST на настраиваемый URL с JSON (вид, confidence, время) — для IFTTT, Zapier, своих скриптов | Низкая | Нет |
| CSV/JSON экспорт статистики | Скачать визиты, виды, детекции для анализа в Excel/Python | Низкая | Нет |
| Виджет «Последняя птица» на Overview | Блок «Сегодня в 14:32 — Eurasian Jay» на главной | Низкая | Нет |
| Фильтр по времени суток в Timeline | «Только утро (6–10)», «только вечер» — сузить список визитов | Низкая | Нет |
| PWA improvements | Install prompt «Добавить на главный экран», offline cache для статики | Низкая | Нет |
| «Неизвестные» (низкий confidence) | Отдельный список детекций с confidence < порога для ручной проверки и разметки | Средняя | Нет |
| PDF-отчёт | Месячный отчёт: N видов, топ-5, графики — скачать PDF | Средняя | Нет |
| Bird song player (Xeno-canto) | Кнопка «Воспроизвести песню» на карточке вида — аудио из Xeno-canto API | Средняя | Нет |
| eBird export | Экспорт списка видов в формат eBird для загрузки в приложение | Средняя | Нет |
| Grafana/Prometheus метрики | Эндпоинт `/metrics` — detections_count, species_count для дашбордов | Средняя | Нет |
| Confidence по виду | Разные пороги min_confidence для разных видов (редкие — ниже) | Средняя | Низкий |
| Сравнение записей side-by-side | Два видео рядом (один вид, разные дни) для анализа поведения | Средняя | Нет |
| Экспорт в iNaturalist | Кнопка «Отправить в iNaturalist» — crop + вид для citizen science | Средняя | Нет |
| Web Push | Push-уведомления в браузере вместо/дополнение Telegram | Средняя | Низкий |
| Публичная галерея | Opt-in: загрузка лучших кадров на общий сайт сообщества | Высокая | Средний |
| Календарь миграций | «Вид X обычно появляется в марте» — по историческим данным | Высокая | Нет |
| Сравнение с регионом | «У вас 12 видов, в среднем по региону 8» — требует бэкенд/агрегацию | Высокая | Средний |
| Coral TPU | Ускорение YOLO на Edge TPU (USB Accelerator на x86). Требует смены inference backend | Высокая | Высокий |

---

См. также: [DATASETS.md](./DATASETS.md), [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md), [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md), [TESTING.md](./TESTING.md), [CONFIGURATION.md](./CONFIGURATION.md).
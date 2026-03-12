# Типичные сценарии BirdLense Hub

## Сценарий 1: Минимальная установка (только видео)

**Цель:** Детекция птиц по видео с одной камеры, без MQTT и уведомлений.

1. Установить Go2RTC (standalone или в Frigate).
2. Добавить камеру в Go2RTC.
3. Запустить BirdLense: `make pull` в `app/`.
4. Настройки → Видео: URL Go2RTC (`http://IP:1984`).
5. Настройки → Камеры: добавить stream name.
6. Триггер: OpenCV motion (по умолчанию).

**Результат:** Записи при движении, YOLO-классификация (NABirds — в основном североамериканские виды).

---

## Сценарий 2: Европейские птицы (Frigate + Bird Classification)

**Цель:** Точное определение европейских видов (сойка, синица и т.д.).

1. Frigate с включённым [Bird Classification](https://docs.frigate.video/configuration/bird_classification/) (`classification.bird.enabled: true`).
2. MQTT: Frigate публикует в `frigate/events` с `sub_label`.
3. BirdLense: Настройки → MQTT — broker, топик Frigate.
4. Слияние: YOLO + Frigate автоматически. Один результат на вид, max confidence.

**Результат:** Eurasian Jay вместо Mourning Dove, если Frigate распознал сойку.

---

## Сценарий 3: Аудио (BirdNET-Pi/Go)

**Цель:** Распознавание по голосу в дополнение к видео.

1. BirdNET-Pi или BirdNET-Go публикует в MQTT топик `birdnet`.
2. BirdLense: Настройки → MQTT — broker, топик BirdNET.
3. Слияние: YOLO + Frigate + BirdNET по времени (merge_window).

**Результат:** Вид из аудио добавляется к видео-детекциям или повышает confidence.

---

## Сценарий 4: Уведомления в Telegram

**Цель:** Push при обнаружении птицы.

1. Создать бота (@BotFather → /newbot).
2. Получить chat_id (например, через @RawDataBot).
3. Настройки → Уведомления: токен, chat_id, base_url (URL Hub для ссылок).
4. Включить `link_preview_large` для превью ссылок (Bot API 9.4).

**Результат:** Сообщение «Eurasian Jay Detected» с кнопкой «Open Live» и превью страницы.

---

## Сценарий 5: Кормушка с реле (Tasmota/ESPHome)

**Цель:** Автоматическая выдача корма при детекции.

1. Реле на Tasmota или ESPHome.
2. Настройки → Кормушка: source (mqtt/esphome), топик или URL, длительность.
3. При детекции BirdLense публикует в MQTT или вызывает ESPHome API.

**Результат:** Корм выдаётся при появлении птицы.

---

## Сценарий 6: Деплой на домашний сервер

**Цель:** BirdLense на отдельной машине (Raspberry Pi, NUC, сервер).

1. `cp scripts/deploy.local.sh.example scripts/deploy.local.sh`
2. В deploy.local.sh: `DEPLOY_HOST`, `DEPLOY_URL`, `PROCESSOR_SECRET`
3. SSH config: Host birdlense → IP сервера
4. `make deploy`

**Результат:** Код синхронизируется, контейнер собирается и запускается. Данные (recordings, db) не трогаются.

---

## Сценарий 7: Исследование и дообучение модели

**Цель:** Собрать датасет из записей, дообучить YOLO на европейских птицах.

1. Записи накапливаются в `data/recordings/`.
2. Скрипты: `scripts/datasets/` — загрузка birds-525, iNaturalist Europe.
3. Merge: `merge_classification_datasets.py` — объединение в формате Scientific (Common).
4. Обучение: `scripts/birds_train*.ipynb` — fine-tuning.

Подробнее: [FINETUNE_OPEN_DATASETS.md](./FINETUNE_OPEN_DATASETS.md), [DATASET_MERGE_FORMAT.md](./DATASET_MERGE_FORMAT.md).

---

См. также: [CONFIGURATION.md](./CONFIGURATION.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md).

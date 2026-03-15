# Типичные сценарии BirdLense Hub

## Сценарий 1: Минимальная установка (только видео)

**Цель:** Детекция птиц по видео с одной камеры, без MQTT и уведомлений.

1. Установить Go2RTC (standalone или в Frigate).
2. Добавить камеру в Go2RTC.
3. Запустить BirdLense: `make pull` в `app/`.
4. Настройки → Видео: URL Go2RTC (`http://IP:1984`).
5. Настройки → Камеры: добавить stream name.
6. Триггер: OpenCV motion (по умолчанию).

**Результат:** Записи при движении, YOLO-классификация (EU: birds-525 + iNaturalist, ~491 вид).

---

## Сценарий 2: Европейские птицы (Frigate + Bird Classification)

**Цель:** Точное определение европейских видов (сойка, синица и т.д.).

1. Frigate с включённым [Bird Classification](https://docs.frigate.video/configuration/bird_classification/) (`classification.bird.enabled: true`).
2. MQTT: Frigate публикует в `frigate/events` с `sub_label`.
3. BirdLense: Настройки → MQTT — broker, топик Frigate. **Motion source: Frigate** (триггер записи по событиям Frigate).
4. Слияние: YOLO + Frigate автоматически. Один результат на вид, max confidence.

**Результат:** Eurasian Jay вместо Mourning Dove, если Frigate распознал сойку.

---

## Сценарий 3: Аудио (BirdNET-Pi/Go)

**Цель:** Распознавание по голосу в дополнение к видео.

1. BirdNET-Pi или BirdNET-Go публикует в MQTT топик `birdnet`.
2. BirdLense: Настройки → MQTT — broker, топик BirdNET.
3. Слияние: YOLO + Frigate + BirdNET по времени (merge_window).
4. **Спектрограмма** — генерируется **только** когда в окне записи пришло сообщение от BirdNET о распознавании. Автоматически и обязательно в этом случае. Визуализация аудио для сопоставления с детекциями BirdNET.

**Результат:** Вид из аудио добавляется к видео-детекциям или повышает confidence. Вкладка «Аудио» в плеере показывает спектрограмму.

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

**Цель:** BirdLense на отдельной машине (NUC, x86-сервер). Требуется x86/amd64 — ARM (Raspberry Pi) не поддерживается.

1. `cp scripts/deploy.local.sh.example scripts/deploy.local.sh`
2. В deploy.local.sh: `DEPLOY_HOST`, `DEPLOY_URL`, `PROCESSOR_SECRET`
3. SSH config: Host birdlense → IP сервера
4. `make deploy`

**Результат:** Код синхронизируется, контейнер собирается и запускается. Данные (recordings, db) не трогаются.

---

## Сценарий 7: Экспорт в eBird

**Цель:** Загрузить список видов в eBird.org для citizen science.

1. Timeline → выберите дату и время суток.
2. Меню экспорта (иконка загрузки) → «Экспорт для eBird».
3. Настройки → Расширенные: страна (US, RU и т.д.), регион, название локации.
4. Скачанный CSV импортировать в eBird.org (Checklists → Import).

**Результат:** Чеклист в формате eBird Record.

---

## Сценарий 8: Экспорт в iNaturalist

**Цель:** Отправить кадр детекции в iNaturalist для citizen science.

1. Timeline или страница видео → нажмите иконку Share (Share to iNaturalist) на детекции.
2. Кадр скачивается, открывается inaturalist.org/observations/upload.
3. Перетащите файл в форму, укажите вид (или подтвердите предложенный).

**Результат:** Наблюдение в iNaturalist.

---

## Сценарий 9: Ручная проверка «Неизвестных»

**Цель:** Исправить детекции с низкой confidence.

1. Настройки → Расширенные: порог «Неизвестные» (по умолчанию 0.5).
2. Страница «Неизвестные» — список детекций с confidence ниже порога.
3. Выберите правильный вид, нажмите «Применить» (требуется пароль настроек).
4. Либо откройте видео для визуальной проверки.

**Результат:** Вид исправлен, детекция учитывается в статистике.

---

## Сценарий 10: PDF-отчёт и Grafana

**Цель:** Месячная сводка и дашборды.

1. **PDF:** Overview → «PDF-отчёт» → выберите месяц.
2. **Grafana:** Добавьте Prometheus datasource, scrape `http://birdlense:8080/metrics`. Метрики: `birdlense_detections_total`, `birdlense_species_count`, `birdlense_videos_total`.

**Результат:** Отчёт и графики активности.

---

## Сценарий 11: Исследование и дообучение модели

**Цель:** Собрать датасет из записей, дообучить YOLO на европейских птицах.

1. Записи накапливаются в `data/recordings/`.
2. Скрипты: `scripts/datasets/` — загрузка birds-525, iNaturalist Europe.
3. Merge: `merge_classification_datasets.py` — объединение в формате Scientific (Common).
4. Обучение: `scripts/birds_train*.ipynb` — fine-tuning.

Подробнее: [DATASETS.md](./DATASETS.md).

---

См. также: [CONFIGURATION.md](./CONFIGURATION.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md).

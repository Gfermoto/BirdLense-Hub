# Типичные сценарии BirdLense Hub

[English](../user/scenarios.md)

---

## Сценарий 1: Минимальная установка (только видео)

**Цель:** Детекция птиц по видео с одной камеры, без MQTT и уведомлений.

1. Установить Go2RTC (standalone или в Frigate).
2. Добавить камеры в `streams` go2rtc (имена = `stream_name` в BirdLense). Для **H264 RTSP** добавьте **`ffmpeg:ИМЯ#video=mjpeg`** на каждый поток, если нужен **Live → MJPEG** — см. [Конфигурация → Потоки Go2RTC и MJPEG](./configuration.ru.md#go2rtc-streams-and-mjpeg-live-view) и [`docs/examples/go2rtc-streams.example.yaml`](../examples/go2rtc-streams.example.yaml).
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

## Сценарий 3: Аудио (BirdNET по MQTT)

**Цель:** Распознавание по голосу в дополнение к видео.

**Какой BirdNET использовать:** в Hub **нет** отдельной настройки «Pi или Go». Подходит **любой источник**, который публикует **JSON** на ваш MQTT-топик в формате, который умеет читать процессор (частые варианты — **BirdNET-Go**, **BirdNET-Pi**; см. поля в [CONFIGURATION.ru.md](./configuration.ru.md) § MQTT). Достаточно указать брокер и топик в Настройках.

**Локаль подписи (RU/EN и т.д.):** менять язык в BirdNET **не обязательно** ради слияния с видео. Hub привязывает событие к **каноническому имени вида** в вашей базе по **научному имени** из MQTT (у BirdNET-Go оно обычно есть) и при необходимости по **алиасам** в реестре видов. Подробнее — там же, § MQTT.

1. Ваш аудио-стек (например BirdNET-Go или BirdNET-Pi) публикует распознавания в MQTT — часто топик `birdnet` или свой (задаётся в `mqtt.birdnet_topic`).
2. BirdLense: Настройки → MQTT — брокер, топик BirdNET.
3. Слияние: YOLO + Frigate + BirdNET по времени (`merge_window`).
4. **Спектрограмма** — по умолчанию строится после каждой записи (`processor.generate_spectrogram_always`); если выставить **false**, она строится **только** при событии BirdNET в окне записи (меньше нагрузка). Вкладка «Аудио» в плеере показывает спектрограмму, когда файл есть.

**Результат:** Вид из аудио добавляется к видео-детекциям или повышает confidence; при корректном payload слияние не зависит от того, на каком языке BirdNET показывает название птицы.

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

## Сценарий 6: Деплой на сервер

См. [INSTALL.md](./install.ru.md) — «Деплой на сервер (`make deploy`)» и чеклист [DEPLOY_SERVER.ru.md](./deploy-server.ru.md): `scripts/deploy.local.sh`, **`DEPLOY_URL`** для **`verify-stack`** после выката, при необходимости **`DEPLOY_SSH_PORT`**. После деплоя: `BASE_URL=... make verify` из корня репозитория. Только **x86_64 / amd64** (Intel или AMD); ARM / aarch64 не поддерживаются и не планируются.

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
2. **Grafana:** источник Prometheus, scrape `http://birdlense:8085/api/metrics` (в Docker-сети) или `http://YOUR_HOST:8085/api/metrics`. Метрики: CPU, память, диск, GPU, detections, species, videos.

**Результат:** Отчёт и графики активности.

---

## Сценарий 11: Исследование и дообучение модели

См. [TRAINING.ru.md](../../archive/internal/docs-legacy/TRAINING.ru.md), [datasets](../contributor/datasets.md) (**Актуальные пути**: merge, `brg/`, имена архивов). Скрипты: `scripts/datasets/`, merge → Colab.

---

## Troubleshooting

**Frigate обнаружил птицу, но BirdLense не записал:** см. [TROUBLESHOOTING.md](../user/troubleshooting.md) — пропущенные события, чеклист причин.

---

См. также: [OVERVIEW](./overview.ru.md) · [INSTALL](./install.ru.md) · [CONFIGURATION](./configuration.ru.md) · [GLOSSARY](./glossary.ru.md) · [ARCHITECTURE](../contributor/architecture.md).

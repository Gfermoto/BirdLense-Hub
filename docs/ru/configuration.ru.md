# Конфигурация BirdLense Hub

[English](../user/configuration.md)

---

Конфиг: `app/app_config/user_config.yaml`

Значения по умолчанию в `app/app_config/default_config.yaml`. Пользовательский конфиг переопределяет их (merge).

**Приоритет:** `user_config.yaml` накладывается на `default_config.yaml`, затем в рантайме применяются **оверлеи секретов**: если ниже задана непустая переменная `BIRDLENSE_*`, она подставляется в объединённый конфиг (как правка YAML, но без записи на диск). Отдельные ключи вроде `GO2RTC_URL` по-прежнему переопределяют соответствующие поля там, где это описано.

### Merge, пустые строки и сохранение из UI

- **Рекурсивный merge:** значения из `user_config` перекрывают `default_config` по дереву. Отсутствующий в `user_config` ключ **не** трогает дефолт.
- **Пустая строка — это тоже значение:** запись вида `some_key: ""` в `user_config` **затирает** дефолт пустым значением (это не «вернуться к дефолту»). Типичный сбой: `integrations.scales.mqtt_topic_prefix: ""` — процессор не подписывается на вес, пока не задан явный `mqtt_topic` или не убран ключ из YAML.
- **Сохранение настроек из веб-UI** записывает в `user_config.yaml` **полное смерженное дерево** (как видит рантайм после merge и env), а не только дифф к дефолту. Поэтому: (1) файл со временем разрастается и «фиксирует» значения; (2) обновление `default_config.yaml` в новой версии хаба **не изменит** уже сохранённые в user-файле ключи; (3) секреты из env, попавшие в память merged-конфига, теоретически могут оказаться в YAML при следующем сохранении из UI — в проде предпочтительно держать секреты в **env** и не сохранять настройки без необходимости, либо использовать только `BIRDLENSE_*` без дублей в YAML.
- **Ревизия:** System → ревизия конфигурации (`GET /api/ui/system/config-audit`) дополняется проверками MQTT-весов (брокер, префикс, явные `""` в user YAML).

**Настройки в UI:** большинство параметров можно менять через веб-интерфейс (Настройки → шестерёнка). YAML остаётся для продвинутых сценариев и переменных окружения.

**Связанные документы:** [ACCESS_CONTROL](./access-control.ru.md) · [EN](../contributor/access-control.md) (уровни паролей), [API](./api.ru.md) · [EN](../contributor/api.md) (HTTP), [GLOSSARY](./glossary.ru.md) · [EN](../user/glossary.md) (термины). **Файл env:** [`app/.env.example`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/.env.example) (шаблон для установки). **Контракт:** [OpenAPI](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/openapi.yaml).

**По странице:** [Переменные окружения](#environment-variables) · [Стартовые профили](#starter-profiles) · [Профиль minimal без MQTT](#minimal-profile-no-mqtt) · [Устаревший `motion:`](#legacy-motion-block) · [Processor](#processor) · [Video](#video) · [Retention](#retention) · [Prometheus / Grafana](#prometheus--grafana) · [Метрики System](#system-page-metrics-history) · [Secrets](#secrets) · [См. также](#see-also)

---

## Стартовые профили YAML (`app/configs/`) {#starter-profiles}

Примеры **без секретов**; копируйте в `app/app_config/user_config.yaml`, пароли и токены задавайте только в **env** или локально (не коммитьте).

| Файл | Типичное применение |
|------|---------------------|
| [`minimal.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/configs/minimal.yaml) | Go2RTC + OpenCV motion; **без MQTT-брокера**; YOLO/ByteTrack по потоку камеры |
| [`frigate-only.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/configs/frigate-only.yaml) | Только Frigate по MQTT, без топика BirdNET |
| [`full.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/configs/full.yaml) | Ориентир «как в бою»: несколько камер, Frigate + BirdNET, погода HA, кормушка — `HA_TOKEN`, `MQTT_BROKER` и т.д. в `.env` или YAML локально |

**Бой vs офлайн-тест по файлам:** в проде обычно `video.source: go2rtc`. Для **прогона mp4 из папки** — `video.source: file`, `file_dir` / `file_path`, при необходимости `processor.file_max_record_floor_seconds` (см. строку *(поведение)* в **Video**). `processor.keep_recording_when_no_detections: true` имеет смысл **только** в режиме **file**, если нужно оставлять сессии с **нулём** детекций (кропы, QA). Для **живого Go2RTC** этот флаг **игнорируется** — пустые сессии по-прежнему удаляются, чтобы не забивать диск. При **плейлисте из папки** (`file_path` пуст) на странице **Библиотека** доступна карточка **офлайн-прогона с диска**: список/upload/удаление в `file_dir`, старт/стоп и loop **без перезапуска контейнера** — процессор читает `data/file_test_control/desired.json`, прогресс в `status.json` ([#270](https://github.com/Gfermoto/BirdLense-Hub/issues/270)).

### Профиль minimal без MQTT-брокера {#minimal-profile-no-mqtt}

События Frigate, BirdNET по MQTT и бинарные PIR **требуют** брокер. Если брокер **недоступен**, ещё **не установлен** или нужны **только** Go2RTC + OpenCV + локальный YOLO:

1. Возьмите за основу **[`app/configs/minimal.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/configs/minimal.yaml)** (скопируйте или смержите в `user_config.yaml`).
2. Держите **`mqtt.broker`** пустым и **не задавайте `MQTT_BROKER`** в **`app/.env`** (если другой функции брокер не нужен). Процессор **не** стартует MQTT-агрегатор без брокера — в **Status** может быть `mqtt: error`, пока не появится брокер; **запись и YOLO** идут по цепочке с камеры.
3. В образце явно задан блок **`triggers.*`**: включён OpenCV, выключены Frigate / motion_sensor / scales.

### Устаревший блок `motion:` {#legacy-motion-block}

В старых установках в `user_config.yaml` может оставаться верхнеуровневый **`motion:`**. Хаб **переносит** его в **`triggers.*`**, при возможности **перезаписывает** файл и пишет **WARNING** в лог при этой миграции. В новых конфигах задавайте только **`triggers`**.

---

## Как читать ключи

- В таблицах — **точечные пути**, как в YAML: `video.go2rtc_url` → секция `video:`, поле `go2rtc_url:`.
- Поведение «пустой пароль = открытый хаб» см. [ACCESS_CONTROL](./access-control.ru.md).

## Переменные окружения {#environment-variables}

| Переменная | Описание |
|------------|----------|
| `DATA_DIR` | Каталог данных (/app/data в Docker) |
| `REDIS_URL` | **`app/docker-compose.yml`:** по умолчанию `redis://redis:6379/0` (контейнер `birdlense-redis`). **`docker-compose.image.yml`:** отдельного Redis нет — не задавайте или укажите **внешний** Redis; иначе кэш **в процессе**. Переопределение — в `app/.env`. **Запуск на хосте без compose:** пусто — кэш в памяти процесса. |
| `DATABASE_URL` | Опционально. URI SQLAlchemy. По умолчанию SQLite в `DATA_DIR`. Под высокую запись — PostgreSQL, например `postgresql+psycopg://user:pass@host:5432/dbname`. Операторский гайд: [POSTGRES_MIGRATION.ru.md](../../archive/internal/docs-legacy/POSTGRES_MIGRATION.ru.md). |
| `SQLALCHEMY_POOL_SIZE` | Размер пула PostgreSQL (по умолчанию `5`) |
| `SQLALCHEMY_MAX_OVERFLOW` | Доп. соединения пула PostgreSQL (по умолчанию `15`) |
| `FLASK_SECRET_KEY` | Ключ сессии Flask (защита настроек) |
| `FLASK_MAX_CONTENT_LENGTH` | Лимит тела HTTP в **байтах** для Flask/Werkzeug (по умолчанию ~80 ГиБ в `web/config.py`). У reverse proxy (nginx и т.д.) нужен свой лимит загрузки для больших файлов в **Библиотеке** |
| `PROCESSOR_SECRET` | Защита API processor (X-Processor-Token) |
| `MCP_TOKEN` | Токен MCP (переопределяет mcp.token) |
| `BIRDLENSE_STRICT_API_AUTH` | `1` / `true` — при **production** закрыть анонимный доступ к `/api/ui/*` (сессия, `BIRDLENSE_UI_API_KEY` или MCP Bearer); см. [SECURITY.ru.md](./security.ru.md) |
| `BIRDLENSE_UI_API_KEY` | Секрет для UI API в strict-режиме: **`X-Birdlense-Api-Key`** или **`Authorization: Bearer`** (то же значение). Пусто — только сессия и MCP |
| `BIRDLENSE_PORT` | Порт nginx (по умолчанию 8085) |
| `BIRDLENSE_HIDE_DIRECT_RECORDINGS` | `1` / `true` / `yes` / `on` — не добавлять nginx `location` для `/data/recordings/`; анонимный **`GET /data/recordings/...`** → **403**; воспроизведение — **`/api/ui/videos/:id/stream`**. По умолчанию: если `BIRDLENSE_ENV=production` и включён `BIRDLENSE_STRICT_API_AUTH`, прямые URL к записям скрываются автоматически; иначе alias остаётся включён, пока флаг не задан явно. **Публичный VPS:** [PUBLIC_RECORDINGS.ru.md](./public-recordings.ru.md). |
| `GUNICORN_THREADS` | Число потоков воркера Gunicorn (`gthread`; по умолчанию **16**; `app/scripts/entrypoint.sh`) |
| `CORS_LOCAL_DEV_ORIGINS` | Локальные/dev origins CORS (через запятую): Vite, `birdlense.local`, порт хаба. Дефолт — как раньше в коде; пустая строка — не добавлять этот набор |
| `CORS_DEFAULT_ORIGINS` | Базовые origins CORS (через запятую), если нужны не-localhost адреса по умолчанию |
| `CORS_ORIGINS` | Доп. origins для CORS (через запятую) |
| `TRUSTED_PROXY` | `1` / `true` — учитывать `X-Real-IP` / `X-Forwarded-For` в rate limit за **доверенным** reverse proxy; см. раздел Webhook и [SECURITY.ru.md](./security.ru.md) |
| `OPENWEATHER_API_KEY` | Ключ OpenWeather |
| `XENO_CANTO_API_KEY` | Ключ API v3 Xeno-canto для воспроизведения песен в UI. После merge YAML по-прежнему можно переопределить через `BIRDLENSE_XENO_CANTO_API_KEY` → `secrets.xeno_canto_api_key` |
| `MQTT_BROKER`, `MQTT_PASSWORD` | MQTT (если не в конфиге) |
| `HA_URL`, `HA_TOKEN` | Базовый URL Home Assistant и long-lived token, если не только в YAML (`homeassistant.*`) |
| `GO2RTC_URL` | URL Go2RTC (если не в конфиге) |
| `HF_TOKEN` | Опционально токен Hugging Face для **`huggingface-cli`** и скриптов с датасетами — **веб-процесс хаба не читает** (см. `app/.env.example`) |
| `BIRDLENSE_STARTUP_BACKFILL_SPECIES_TAXA` | `1` — при старте выполнять привязку видов к реестру (`backfill`); по умолчанию выкл.; иначе: `POST /api/ui/system/species-registry/backfill` |
| `BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT` | `1` — при старте удалять legacy-плейсхолдеры после старого «импорта с диска»; по умолчанию выкл.; очистка при сканировании записей всё равно выполняется |
| `BIRDLENSE_STARTUP_REPAIR_SPECIES_METADATA` | `1` — фоновой repair метаданных (картинки) при старте; по умолчанию выкл. |
| `BIRDLENSE_NOTIFY_APP_STARTUP` | `0` — не слать Telegram «App is UP!» при старте; по умолчанию включено |
| `BIRDLENSE_INFERENCE_BACKEND` | Переопределяет `processor.inference_backend` (`torch`, `openvino`, …) — см. [CV_ML_ROADMAP_PHASES.ru.md](../../archive/internal/docs-legacy/CV_ML_ROADMAP_PHASES.ru.md) |
| `BIRDLENSE_INFERENCE_DEVICE` | Переопределяет `processor.inference_device` (`auto`, `cpu`, `cuda`, `intel:gpu`, …) |
| `BIRDLENSE_BINARY_OPENVINO_PATH` | Опциональный путь к IR OpenVINO (каталог или `.xml`) для бинарника; при непустом значении важнее YAML |
| `BIRDLENSE_OPENVINO_PROFILE` | Профиль производительности OpenVINO (`latency` или `throughput`) |
| `BIRDLENSE_OPENVINO_NUM_REQUESTS` | Количество async requests для OpenVINO (`0` = авто-режим runtime) |
| `BIRDLENSE_INFERENCE_AUTO_BENCHMARK` | `1` / `true` / `yes` / `on` — после загрузки стека один `predict` бинарника на пустом кадре; в **`cold_start_predict_ms`** в `data/processor/inference_backend_cache.json` ([#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371)) |
| `BIRDLENSE_SYSTEM_METRICS_INTERVAL_SEC` | Интервал сэмплера метрик «Система» (секунды); по умолчанию `30`; допустимо 10–600 — см. [§ История метрик на странице «Система»](#system-page-metrics-history) |
| `BIRDLENSE_SYSTEM_METRICS_RETENTION_HOURS` | Хранить строки `system_resource_sample` не старше (часы); по умолчанию `72`; допустимо 6–720 |
| `DISABLE_SYSTEM_METRICS_SAMPLER` | `1` / `true` — отключить фоновый сэмплер (тесты, CI) |
| `BIRDLENSE_METRICS_TOKEN` | Если задан — для `GET /metrics`, `/api/metrics`, `/api/metrics/summary` нужен `Authorization: Bearer` — см. [§ Prometheus / Grafana](#prometheus--grafana) |
| `BIRDLENSE_TELEGRAM_BOT_TOKEN` | Переопределяет `notifications.telegram_bot_token` |
| `BIRDLENSE_TELEGRAM_MTPROTO_SECRET` | Переопределяет `notifications.telegram_mtproto_secret` |
| `BIRDLENSE_TELEGRAM_API_HASH` | Переопределяет `notifications.telegram_api_hash` |
| `BIRDLENSE_HA_TOKEN` | Переопределяет `homeassistant.token` |
| `BIRDLENSE_SETTINGS_PASSWORD` | Переопределяет `general.settings_password` (plaintext или bcrypt) |
| `BIRDLENSE_CONTRIBUTOR_PASSWORD` | Переопределяет `general.contributor_password` (plaintext или bcrypt) |
| `BIRDLENSE_MQTT_PASSWORD` | Переопределяет `mqtt.password` |
| `BIRDLENSE_GO2RTC_PASSWORD` | Переопределяет `video.go2rtc_password` |
| `BIRDLENSE_OPENWEATHER_API_KEY` | Переопределяет `secrets.openweather_api_key` |
| `BIRDLENSE_EBIRD_API_KEY` | Переопределяет `secrets.ebird_api_key` |
| `BIRDLENSE_XENO_CANTO_API_KEY` | Переопределяет `secrets.xeno_canto_api_key` |
| `BIRDLENSE_MCP_TOKEN` | Переопределяет `mcp.token` |
| `BIRDLENSE_VAPID_PRIVATE_KEY` | Переопределяет `web_push.vapid_private_key` |
| `BIRDLENSE_REDIS_URL` | Переопределяет `performance.redis_url` |
| `BIRDLENSE_RECORDINGS_MIRROR_SFTP_PASSWORD` | **Опциональное** перекрытие в рантайме для `storage.recordings_mirror.sftp_password` (обычно задаётся в **Библиотека → Хранилище** или в `user_config.yaml`) |
| `BIRDLENSE_RECORDINGS_MIRROR_SFTP_KEY_PASSPHRASE` | **Опциональное** перекрытие для `storage.recordings_mirror.sftp_key_passphrase` |

**Зеркало записей на NAS / SFTP:** хост, пользователь, пароль и опции — в UI хаба (**Библиотека → Хранилище**, админ) или в `user_config.yaml`; в API секреты маскируются. После сохранения UI запрашивает **перезапуск процессора** (флаг), чтобы процесс подхватил конфиг, а кнопка **«Проверить подключение»** проверяет SFTP и доступность удалённого каталога. При `storage.recordings_mirror.enabled: true` процессор после финализации в фоне загружает каталог сессии на SFTP. Пути в БД остаются `data/recordings/...`; воспроизведение с локального диска, пока не включён **`delete_local_after_success`**. **Альтернатива:** смонтировать NAS в `DATA_DIR` или в `recordings/`. См. [INSTALL.ru.md](./install.ru.md) про пути данных.

**Пароли UI:** при сохранении из веб-интерфейса новые значения в виде plaintext **хешируются (bcrypt)** в `user_config.yaml`; старые записи в plaintext продолжают работать, пока не смените пароль. В env можно передать и plaintext, и уже готовый bcrypt-строковый хеш.

См. `app/.env.example`. Секреты генерируются при `make setup` (вызывается из `make start`/`make pull`).

---

## General

| Ключ | Описание |
|------|----------|
| `settings_password` | Пароль **Admin**: настройки, кормушка, система, перезапуск processor. Пусто — без блокировки (типично для дома) |
| `require_auth_for_video_stream` | **`false`** (по умолчанию): гости могут смотреть запись в плеере (`/api/ui/videos/:id/stream`), как в [ACCESS_CONTROL](./access-control.ru.md). **`true`** — поток только с паролем Contributor/Admin (старое поведение). **Публичный хаб:** решать совместно с [PUBLIC_RECORDINGS.ru.md](./public-recordings.ru.md). |
| `contributor_password` | Опционально пароль **Contributor**: правка видов, «Неизвестные», iNaturalist, экспорт датасета, отчёты — **без** настроек/кормушки/системы. Пусто — один уровень пароля (см. [ACCESS_CONTROL](./access-control.ru.md)) |
| `session_idle_minutes` | Сброс сессии входа (admin/contributor) после **N** минут без запросов к `/api/*`. **0** — отключить. По умолчанию **30**. Учитывается, если задан хотя бы один пароль (admin/contributor) или включён production-runtime; см. [SECURITY](./security.ru.md). |
| `enable_notifications` | Включить уведомления (глобально) |
| `notification_excluded_species` | Виды, исключённые из уведомлений |
| `birdnet_url` | Ссылка на веб-интерфейс вашего аудио-стека (BirdNET-Go, BirdNET-Pi и т.д.). Пусто — ссылка/иконка в UI скрыта. От выбора сборки настройки слияния не зависят — важен MQTT. |
| `donate_url` | Ссылка на поддержку. Если задана, показывается только иконка-сердце в шапке. Пусто — скрыто. |

**Платформы:** РФ — [Boosty](https://boosty.to), [DonationAlerts](https://donationalerts.com), [DONAT24](https://donat24.ru), ЮMoney. За рубежом — Ko-fi, GitHub Sponsors, Patreon. Настройки → General → вставить URL страницы.

### Heimdall и метрики Hub

- Heimdall остаётся **ручным дашбордом** для ссылок и виджетов вокруг BirdLense Hub.
- Добавляйте плитки напрямую на URL хаба, например:
  - Prometheus text: `http://<хост>:<порт>/metrics` или `/api/metrics`
  - JSON-снимок: `http://<хост>:<порт>/api/metrics/summary`
- В самом BirdLense больше нет отдельного `heimdall_url` и server-side проверки Heimdall.

На странице «Система» эти URL также показаны в блоке **Наблюдаемость уведомлений** (после входа в настройки).

**Плитки Heimdall:** пошаговый список URL и ограничения импорта в v2 — [HEIMDALL.ru](../../archive/internal/docs-legacy/HEIMDALL.ru.md).

---

## Processor

| Ключ | Описание |
|------|----------|
| `tracker` | Конфиг трекера (bytetrack.yaml) |
| `max_record_seconds` | Макс. запись в секундах |
| `max_inactive_seconds` | Макс. пауза без детекций |
| `post_record_seconds` | Post-roll: добавляется к паузе без детекций перед остановкой записи (сек). Итог = `max_inactive_seconds` + `post_record_seconds`. См. [#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157). |
| `min_seconds_between_recordings` | Минимальная пауза после завершения клипа до старта следующего. По умолчанию `8`. Срезает near-duplicate клипы, когда птица осталась в кадре или Frigate/OpenCV почти мгновенно триггерят новую сессию. `0` — выключить cooldown. |
| `min_confidence_binary` | Порог детектора «птица / не птица». По умолчанию **0.30** (`default_config.yaml`) |
| `min_confidence_binary_bird` | Опционально: отдельный порог **только для боксов Bird** после `track()` (Ultralytics получает `min` всех порогов; отсев по метке в Python). Пример: **0.48** при `min_confidence_binary_rodent: 0.22` — меньше ложных «птиц» (мышь→синица), грызуны не душатся тем же числом. |
| `min_confidence_binary_rodent` | Опционально: порог для боксов **Rodent** после нормализации бинарной головы (веса могут по-прежнему называть класс Squirrel внутри модели). |
| `min_confidence_binary_squirrel` | **Устарело:** при наличии в merge значение **копируется в** `min_confidence_binary_rodent` (совместимость со старым YAML; затем можно удалить squirrel). |
| `bird_skip_classifier_max_area_frac` | Если **> 0**: для **Bird** с площадью bbox ≤ доли кадра (0…1) **не вызывается** видовой классификатор — остаётся generic Bird (решает ложные виды на мелком объекте). По умолчанию **0** (выкл.). Попробуйте **0.012–0.025**; слишком высокое значение заденет мелких синиц у кормушки. |
| `min_track_duration` | Мин. длительность трека YOLO/ByteTrack (сек). Применяется до fusion. Поднимайте при мельканиях, опускайте если короткие визиты пропадают. |
| `min_confidence_to_process` | Порог принятия вида после detector confirmation. По умолчанию **0.40**. Ниже — больше меток, выше — строже. |
| `min_confidence_to_notify` | Минимум combined confidence для **фото-уведомления в Telegram** (после успешного приёма записи на хабе). В поставке **0.46** в `default_config.yaml`; при загрузке конфига `app_config.CONFIDENCE_FLOORS` задаёт **нижний предел 0.30** (меньшие значения поднимаются). Часто задают **выше**, чем `min_confidence_to_process`, чтобы срезать шум в чате при сохранении визитов в БД. Поле есть в **Настройки → Процессор**. После смены порогов в YAML перезапустите **processor**, иначе в контейнере останется старый конфиг в памяти. |
| `species_confidence_overrides` | Пороги по видам: `{"Rodent": 0.28}` для грызунов; `{"Rare Bird": 0.05}` — редкие птицы |
| `ebird_regional_top_auto_confidence` | Если true (по умолчанию), для видов из регионального топа eBird подмешиваются более низкие пороги (нужны `secrets.ebird_api_key`, `ebird.*`). Ручные ключи в `species_confidence_overrides` важнее. См. [#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128). |
| `ebird_regional_top_confidence_delta` | Вычитается из `min_confidence_to_process` для каждого авто-вида из топа (по умолчанию `0.03`). |
| `ebird_regional_top_confidence_floor` | Нижняя граница авто-порога (по умолчанию `0.08`). |
| `birdnet_mqtt_auto_confidence` | Если **true**, для видов из **недавних** сообщений BirdNET по MQTT подмешиваются более низкие пороги классификатора (как у eBird-топа). BirdNET здесь только **confidence-only**: финальный video label он не создаёт. |
| `birdnet_mqtt_bias_delta` | Вычитается из `min_confidence_to_process` для авто-видов из BirdNET (по умолчанию `0.05`). |
| `birdnet_mqtt_bias_floor` | Нижняя граница авто-порога для BirdNET (по умолчанию `0.05`). |
| `multi_camera_groups` | Список групп `id` камер Frigate одной локации, например `[["BirdBox","Forest"]]`. См. [#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153). |
| `multi_camera_confidence_boost` | При событиях Frigate с **одним видом** с **двух и более** камер из одной группы — прибавка к итоговому `confidence` (по умолчанию `0.03`, не выше 1.0). |
| `spectrogram_px_per_sec` | Горизонтальная детализация mel-спектрограммы (пикселей на секунду аудио). |
| `generate_spectrogram_always` | По умолчанию **true**: после **каждой** финализированной записи строить `spectrogram_*.jpg` (FFmpeg + librosa). **false** — только если в окне записи было событие BirdNET по MQTT (меньше нагрузка). |
| `regional_species` | Опциональное сужение classifier scope (пусто — классификатор использует все классы). |
| `detector_scope` | Цели детектора первого уровня. По умолчанию: `["Bird", "Rodent"]`. В EU-классификаторе не-птица — **Rodent**; сырые веса могут отдавать Squirrel, хаб нормализует в Rodent. Background / hard-negative классы детектора должны оставаться вне этого scope; см. [контракт подготовки CV / ML](../../archive/internal/docs-legacy/CV_ML_PREP.ru.md). |
| `classifier_fallback_bird` | Сохранять generic detector label, если detector подтвердил target, а классификатор остался ниже порога. Затем Frigate может продвинуть этот fallback до species label. |
| `included_bird_families` | Список семейств птиц для фильтра (напр. Perching Birds); к Rodent не относится |
| `save_images` | Сохранять кадры детекций |
| `detection_strategy` | В production используется только `two_stage`; другие значения (включая старый `single_stage`) игнорируются с warning. Перед CV / ML rollout удалите их из `user_config.yaml`. |
| `models.binary` | Путь к бинарному детектору (.pt) |
| `models.classifier` | Путь к классификатору (.pt) |
| *(свои веса)* | Runtime API загрузки/сброса удалён. Смена моделей — только через артефакты деплоя (`models/**`) и конфиг (`processor.models.*`). |
| `file_max_record_floor_seconds` | Только **`video.source=file`:** минимальный отрезок по «настенным часам» (сек) до возможного split длинного клипа; по умолчанию **86400**. См. *(поведение)* в **Video**. |
| `keep_recording_when_no_detections` | Только **`video.source=file`** (по умолчанию **false**). Если **true** — оставлять финализированную сессию (валидный mp4) при **нуле** сохранённых детекций (офлайн-пайплайны). Для **`go2rtc` / live** ключ **не действует**; пустые сессии удаляются. |
| `track_regen_parallel_auto_with_manual` | Продвинутая параллельность перегенерации треков (auto + manual scope); тюнинг для ops, только YAML (см. System → track regen в UI). |

---

## Video

| Ключ | Описание |
|------|----------|
| `source` | `go2rtc` или `file` (тест: папка mp4 или один файл в контейнере) |
| `file_path` | Один mp4, абсолютный путь в контейнере; пусто — плейлист из `file_dir` |
| `file_dir` | Папка с `*.mp4` / `*.mov` / `*.mkv` (только файлы в каталоге, без рекурсии). В репозитории по умолчанию **`/app/data/file_test`** (Docker: `./data` хоста → `/app/data`). |
| `file_loop` | Зацикливать плейлист/файл (карточка **прогон с диска** в **Библиотеке** пишет это при включении `source=file`; переключатель там же во время работы процессора) |
| `file_realtime_simulation` | Только **`video.source=file`** (по умолчанию **false**). **true** — шаг кадров по **настенным часам** относительно FPS ролика (имитация реального времени; при отставании пайплайна **кадры пропускаются**). **false** — один кадр на вызов `capture()` (ускоренный прогон, проще отладка). UI: **Настройки → Подключения → прогон с диска (процессор)**. |
| `file_test_max_upload_mb` | Лимит МиБ на один ролик при upload через Hub (**Библиотека** → прогон с диска). В коде зажато **64–65536**, по умолчанию **10240** (>10000 MiB). Прокси может отдать **413** раньше Flask — поднимите nginx `client_max_body_size` под размер ролика. Потолок тела запроса в Flask: **`FLASK_MAX_CONTENT_LENGTH`** (байты); дефолт в `web/config.py` большой, чтобы первым срабатывал лимит из YAML. |
| *(поведение)* | **`video.source=file`** и **плейлист из папки**: после **каждого доигранного файла** сессия **финализируется** (кропы/БД для этого клипа), затем открывается следующий файл. **`processor.max_inactive_seconds`** — не ниже **120** с. **`processor.file_max_record_floor_seconds`** (по умолчанию **86400**) — запас по «настенным часам», чтобы длинный файл не резался дефолтом камеры; уменьшайте только если нужны отрезки по времени. |
| `go2rtc_url` | URL Go2RTC (http://IP:1984) |
| `cameras` | Список: `{id, stream_name, name}` |
| `pre_record_seconds` | Предзапись перед триггером |
| `auto_reconnect` | Автопереподключение к потоку |
| `video_width`, `video_height` | Разрешение |

### Потоки Go2RTC и MJPEG (страница Live)

Типичная камера отдаёт на RTSP **H264**. go2rtc отдаёт его в **MSE** (`/api/stream.mp4`) и в запись; **`/api/stream.mjpeg` без MJPEG-кодека пустой** ([документация go2rtc MJPEG](https://go2rtc.org/internal/mjpeg/)).

Чтобы в **Live → Go2RTC → MJPEG** работал **нативный** multipart MJPEG (не «Поток детекции» процессора), добавьте второй источник **`ffmpeg:`** с тем же **именем потока**, что в BirdLense (`video.cameras[].stream_name` / `go2rtc_src`):

```yaml
streams:
  Forest:
    - rtsp://USER:PASSWORD@192.168.1.101:554/cam/realmonitor?channel=1&subtype=0
    - ffmpeg:Forest#video=mjpeg
  BirdBox:
    - rtsp://USER:PASSWORD@192.168.1.129:554/cam/realmonitor?channel=1&subtype=0
    - ffmpeg:BirdBox#video=mjpeg
```

- Правится в **go2rtc** внутри Frigate или в **go2rtc.yaml** standalone; после изменения — перезапуск go2rtc / Frigate.
- Шаблон: [`docs/examples/go2rtc-streams.example.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/docs/examples/go2rtc-streams.example.yaml).
- **Проверка:** `curl -sI "http://GO2RTC:1984/api/stream.mjpeg?src=BirdBox"` — не должно быть `Content-Length: 0`; тело начинается с JPEG (`ff d8`).
- **Без ffmpeg MJPEG:** Hub на Live всё равно показывает кадр через опрос **`/api/frame.jpeg`** (~4 fps) или включите **«Поток детекции»** (`/processor/live/N`) для MJPEG с оверлеями от процессора.
- **WebRTC** на Live — только `mode=webrtc` в плеере go2rtc; с VPS без TURN часто не поднимается — используйте **MSE** или **MJPEG**.

---

## Motion

| Ключ | Описание |
|------|----------|
| `source` | `opencv` \| `frigate` \| `mqtt` \| `esphome` |
| `frigate_camera_filter` | Камеры Frigate (из cameras) или пусто — все |
| `frigate_label_filter` | Метки Frigate, которые могут запускать запись (`bird`, `Bird`, `squirrel`, `Squirrel` по умолчанию). Сам триггер не назначает итоговый label. |
| `frigate_label_exclude` | Метки для игнорирования (cat, dog — мышь как кошка) |
| `mqtt_topic` | Топик MQTT binary sensor (Tasmota PIR) |
| `esphome_url` | URL ESPHome |
| `esphome_sensor_id` | ID binary_sensor в ESPHome |

---

## MQTT

Одно подключение — топики frigate и birdnet. Триггеры: Frigate, ESPHome, MQTT binary, OpenCV и другие event-источники. Итоговые video labels всё равно строятся через общий detector/classifier fusion path.

| Ключ | Описание |
|------|----------|
| `broker` | Адрес брокера |
| `port` | Порт (1883) |
| `frigate_topic` | Топик событий Frigate |
| `birdnet_topic` | Топик BirdNET |
| `publish_topic` | Топик публикации детекций BirdLense Hub |
| `reconnect_min_delay` | Минимальная задержка reconnect/backoff MQTT (сек) |
| `reconnect_max_delay` | Максимальная задержка reconnect/backoff MQTT (сек) |
| `publish_queue_max` | Лимит исходящей очереди MQTT-публикаций в процессоре (по умолчанию **4000** в `default_config.yaml`; дренаж после reconnect). Связанные gauge: `mqtt_outbound_queue_depth`, счётчики `mqtt_outbound_drops_total`, `mqtt_outbound_publish_errors_total`. См. [PROCESSOR_PERFORMANCE.ru.md](./processor-performance.ru.md#queues-backpressure). |
| `ha_discovery` | Home Assistant MQTT Autodiscovery для сущностей BirdLense. По умолчанию true. Только observe-only: last species / confidence / detection time, присутствие птицы, текущий вес кормушки (если весы идут по MQTT) и связанная availability/device metadata. |

**Топики:** `frigate/events` (Frigate), `birdnet` (BirdNET), `birdlense/detections` (публикация), `birdlense/sensor/last_species/state` (HA), `birdlense/binary_sensor/bird_detected/state` (HA), `birdlense/sensor/feeder_weight/state` (HA), `birdlense/binary_sensor/feeder_bird_present/state` (HA). Реле кормушки: `homeassistant/switch/bird_feeder/command`.

**BirdNET (универсально):** процессор принимает несколько схем имён полей — в частности **BirdNET-Go** (`CommonName`, `ScientificName`, `SpeciesCode`, `Confidence`, `BeginTime`, опционально `BirdImage.URL`) и **BirdNET-Pi** (`Common_Name`, `Confidence_Score`, `Date`, и др.). Отдельно в конфиге не выбирается «Go или Pi»: достаточно, чтобы JSON приходил на `mqtt.birdnet_topic`. **Слияние с видео и приоритеты по FIFO** опираются на **каноническое имя вида** в Hub: при типичном payload с **научным именем** язык подписи в MQTT (русский/английский) не мешает; если научного имени нет, помогают **алиасы** в реестре видов (`species_alias`) и при необходимости `detection.species_mapping`. При Hub только на PostgreSQL без общего файла `birdlense.db` автоматическое сопоставление по каталогу из SQLite недоступно — используйте маппинг в YAML. BirdNET по-прежнему **confidence-only** для финального video label. **Frigate:** `after` — `camera`, `label`, `sub_label` (вид из Bird Classification), `frame_time`. `sub_label` — приоритет над `label` и может продвинуть generic detector fallback, если video detector уже подтвердил target.

**Важно про пропуски:** при потере соединения события MQTT могут быть пропущены и обычно не «догоняются» задним числом (стандартно Frigate публикует их как live stream, без replay). Для истории опирайтесь на retention Frigate записей/клипов.

**Метрики оператора:** `data/diagnostics/processor_runtime_stats.json` — gauge деградации триггеров/MQTT (`trigger_*`, `mqtt_connected`); см. [PROCESSOR_PERFORMANCE.ru.md](./processor-performance.ru.md).

---

## Feed

| Ключ | Описание |
|------|----------|
| `source` | `mqtt` \| `esphome` |
| `duration_seconds` | Длительность включения реле |
| `mqtt_topic` | Топик MQTT реле (Tasmota) |
| `esphome_url` | URL ESPHome |
| `esphome_switch_id` | ID switch/button |
| `esphome_type` | `switch` \| `button` |

**Время последней выдачи:** Hub сохраняет в `data/feed_last_dispense.json` при успешном dispense (MQTT и ESPHome). На Overview в карточке «Управление кормушкой» показывается «Последняя выдача: дата, время».

---

## Home Assistant (REST API)

Общие **URL** и **Long-Lived Access Token** для любых функций, которые ходят в REST API Home Assistant: погода при `weather.source: homeassistant`, весы при `integrations.scales.source: homeassistant` и будущие интеграции. **Окружение:** `HA_URL` и `HA_TOKEN` перекрывают поля в YAML, если заданы.

| Ключ | Описание |
|------|----------|
| `homeassistant.url` | Базовый URL (например `http://homeassistant:8123`) |
| `homeassistant.token` | Long-Lived Access Token (в API маскируется) |

**Устарело (всё ещё читается как запасной вариант):** `weather.ha_url`, `weather.ha_token` — перенесите в `homeassistant.*`; аудит конфига может пометить старые ключи.

---

## Weather

| Ключ | Описание |
|------|----------|
| `source` | `openweather` \| `homeassistant` |
| `ha_entity_id` | При `source: homeassistant` — какую сущность `weather.*` читать (например `weather.home`). URL и токен **не** здесь — см. `homeassistant.*` выше. |

---

## Detection (общий fusion path)

**Production path:** trigger source -> detector (`Bird | Rodent`) -> YOLO classifier -> fusion -> persistence.

**Семантика источников:**
- YOLO detector/classifier — основной источник всех persisted video detections.
- Frigate — helper source: может продвинуть generic detector fallback или добавить confidence boost.
- BirdNET — confidence-only для видео: bias порогов до решения классификатора, без создания final video label.

**Профиль для максимального recall:** если важнее не пропустить мелких птиц, при наличии брокера MQTT включите Frigate-триггер (**`triggers.frigate.enabled`**), держите **`triggers.opencv.check_every_n_frames=1`** (если OpenCV включён параллельно), поднимите `processor.binary_imgsz` до `640`, `processor.min_center_dist` опустите до `0.03-0.05`, `processor.min_box_size_px` держите `<=64`. В сумерках лучше ослаблять light gate, а не выключать детектор целиком.

**Канонические имена:** Common name (Eurasian Jay), не Scientific. `species_mapping` — маппинг вариантов. `species_canonical_mapping.txt` — для «Объединить дубликаты» (System → Записи). Формат: `variant|canonical`.

**Качество каталога:** `app/web/seed/species_suspect_blocklist.txt` — термины для скрытия не-птиц/объектов из фильтрованных списков видов (`GET /api/ui/species?exclude_suspects=1`, когда это явно запрошено). Полный отчёт (подозрительные строки, дубликаты имён для слияния): System → карточка «Качество каталога видов» или `GET /api/ui/system/species-registry/data-quality` (с паролем настроек). Новые детекции по строкам из блоклиста не создают отдельный вид — уходят в «Unknown».

**Соответствие датасету классификатора (EU ~491 / US NABirds ~400):** в `user_config.yaml` секция `species`: `catalog_allowlist_file` — текстовый список классов (одна строка = одно имя, как в merged_cls / после нормализации YOLO). Сгенерировать из вашего `best.pt` (или другого `.pt`): `scripts/datasets/dump_classifier_allowlist.py` → положить рядом с весами, напр. `models/classification/weights/class_names.txt` (путь относительно `app/processor`). `catalog_strict_ingest: true` — вне allowlist новые виды не создаются, детекции привязываются к «Unknown». Уже накопившийся мусор и дубликаты: `POST /api/ui/system/species-catalog/reconcile` (обязательно сначала `{"dry_run": true}`), опции см. ответ API / подсказки в `data-quality`. Сверка классов с БД: System → «Классификатор, каталог и датасет».

**Выход классификатора vs БД / ручные имена:** автоматические метки — только строки из обученной головы внутри `.pt` (merged class list). Новая строка в таблице видов SQLite или правка в UI **не** добавляет новый выход классификатора — например метки «курица» не будет, если такого класса нет в обученной модели. Держите allowlist в соответствии с весами; новые авто-виды — переобучение или смена `.pt` ([TRAINING](../../archive/internal/docs-legacy/TRAINING.ru.md)).

**UX «Неизвестные»:** при strict ingest подписи вне allowlist попадают в **Unknown** (без новой строки вида). Contributor исправляет в разделе **Неизвестные**; массовая уборка — System → качество каталога / reconcile. Отображаемые имена одного таксона согласуйте с каноном выше (`species_mapping`, `species_canonical_mapping.txt`, объединение дубликатов).

| Ключ | Описание |
|------|----------|
| `merge_window_seconds` | Окно слияния MQTT (8 сек) |
| `dedup_window_seconds` | Разрыв > N сек = разные визиты (60 сек) |
| `one_per_species` | Один результат на вид (true) |
| `source_priority` | Порядок разрешения конфликтов между fused sources. Production default: `["yolo", "frigate"]`. |
| `cross_source_confidence_bonus` | При первом подтверждении YOLO track со стороны Frigate — разово прибавить confidence (потолок 1.0). `0` — выключить. |
| `min_confidence_to_store` | Мин. fused confidence для записи в БД (по умолчанию **0.30**). Это же floor для detector-label fallback. |
| `species_mapping` | Маппинг названий видов |

**Трассировка fusion (UI):** на странице ролика кнопка **Трассировка fusion** подгружает последнюю запись `decision_trace` из ActivityLog (сначала по `video_id` в JSON после ingest, иначе по совпадению `video_path`). По каждому треку этапы: **детектор** (общая метка YOLO), **классификатор** (вид, доля голосов, порог), **scores** (кадры, trust band, причина отклонения), **audio** (согласование с BirdNET), **fusion** (несколько камер / Frigate), **outcome** (сохранённый вид и уверенность). API: `GET /api/ui/videos/{video_id}/fusion-trace` — **только сессия оператора или администратора**, не для анонимных зрителей.

**Инференс и контракт имён детектора (CV/ML):** `processor.inference_backend` — `torch` (по умолчанию) или `openvino` для бинарного детектора (экспорт Ultralytics OpenVINO, [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371)). `BIRDLENSE_INFERENCE_BACKEND` переопределяет YAML. Для `openvino` задайте `processor.models.binary_openvino` (каталог экспорта или `.xml`) или `BIRDLENSE_BINARY_OPENVINO_PATH` (абсолютный или относительно корня пакета процессора). Классификатор — по-прежнему `.pt`. `processor.detector_weight_contract`: `off` \| `warn` \| `enforce` — проверка имён классов детектора против `processor.detector_scope` ([#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368)). Фазы: [CV_ML_ROADMAP_PHASES.ru.md](../../archive/internal/docs-legacy/CV_ML_ROADMAP_PHASES.ru.md).

**EU-модель:** `best.pt` с [HF gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) (дефолт `processor.models.classifier`). US — `best_US.pt`. Обучение: [TRAINING](../../archive/internal/docs-legacy/TRAINING.ru.md).

## Retention

| Ключ | Описание |
|------|----------|
| `days` | Удалять записи старше N дней |
| `max_gb` | Макс. размер в GB (опционально) |

---

## Интеграции (весы)

**Источники и возможности:** `mqtt` — MQTT-backed режим: **processor** подписывается на топик веса, пишет `feeder_scale_state.json` / `feeder_scale_history.jsonl`, может **оценивать дельту за ролик** и по желанию **запускать запись** по скачку веса. `esphome` — прямой опрос устройства по ESPHome Web API, только для **live weight / bird_present / tare**. История / дельта / триггер по весу работают только в `mqtt`.

| Ключ | Описание |
|------|----------|
| `integrations.scales.enabled` | Весы у кормушки / умные весы (по умолчанию **false**). |
| `integrations.scales.source` | `mqtt` (по умолчанию) — топики прошивки / ручная MQTT-настройка; `esphome` — ESPHome Web API (только live weight / bird_present / tare). |
| `integrations.scales.mqtt_topic` | Полный топик **веса** (число или JSON с `value`/`weight`/`state`). Если **пусто** и задан **`mqtt_topic_prefix`**, процессор слушает **`{prefix}/weight`**. |
| `integrations.scales.mqtt_bird_present_topic` | Полный топик **птица на платформе** (`ON`/`OFF` или state как у HA). Если **пусто** и задан **`mqtt_topic_prefix`** — **`{prefix}/bird_present`**. Нужен, когда вес на `homeassistant/sensor/.../state`, а присутствие на префиксе прошивки (пример репо: `frigate/bird_present`). |
| `integrations.scales.mqtt_topic_prefix` | Префикс: **`{prefix}/weight`** при пустом `mqtt_topic`; **`{prefix}/bird_present`** при пустом `mqtt_bird_present_topic`; тара в **`{prefix}/command`**, если не задан **`mqtt_command_topic`**. Пример прошивки в репозитории: **`birdlense/scale`** (`esphome/bird-feeder-scale.yaml`). |
| `integrations.scales.mqtt_command_topic` | Явный топик команд (перекрывает `{prefix}/command`). Дублируется в Настройках → Видео (весы MQTT). |
| `integrations.scales.mqtt_tare_payload` | Строка для тары (по умолчанию **`TARE`**); прошивка должна подписаться на command topic. |
| `integrations.scales.esphome_url` | Базовый URL прямого ESPHome Web API, например `http://192.168.1.50`. |
| `integrations.scales.esphome_weight_sensor_id` | `sensor` id веса для `esphome`. По умолчанию: `weight_live_internal`. Хаб читает `GET /sensor/<id>`. |
| `integrations.scales.esphome_bird_present_sensor_id` | Необязательный `binary_sensor` id «птица на платформе» для `esphome`. По умолчанию: `bird_present`. Хаб читает `GET /binary_sensor/<id>`. |
| `integrations.scales.esphome_tare_button_id` | Необязательный `button` id тары для `esphome`. По умолчанию: `manual_tare`. Хаб шлёт `POST /button/<id>/press`. |
| `integrations.scales.weight_estimate_enabled` | Оценка **дельты веса за интервал записи** и сохранение в карточке ролика (по умолчанию **true**). **Независимо** от **`motion_trigger_enabled`**: можно оценивать вес на роликах, запущенных Frigate/движением, без автостарта по весам. Нужен режим `mqtt` и журнал `feeder_scale_history.jsonl` в `DATA_DIR`. Дельта **не** сохраняется, если в ролике есть только детекции из **BirdNET** (`source=audio`) без кадра/трека: звук участвует в распознавании вида, к весам на платформе не привязывается. |
| `integrations.scales.min_delta_kg_for_estimate` | Минимальная дельта (кг): и для **размаха** max−min по окну, и для **скачка** между соседними по времени MQTT-точками (см. ниже). По умолчанию **0.008** (~8 г). |
| `integrations.scales.estimate_require_consecutive_spike` | **true** (по умолчанию): оценка на ролик сохраняется только если за интервал записи есть хотя бы одна пара **подряд идущих** (по времени) показаний с \|Δ\| ≥ `min_delta_kg_for_estimate`. Так отсекается в основном **медленный дрейф** при почти нулевой платформе после тары. **false** — прежняя логика только по max−min (для отладки). Сохраняемое значение по-прежнему **размах** max−min за клип. |
| `integrations.scales.history_max_lines` | Ограничение размера журнала показаний (обрезка с начала), по умолчанию **10000**. |
| `integrations.scales.motion_trigger_enabled` | **false** по умолчанию. **true** — резкое изменение веса на MQTT-топике весов **запускает тот же конвейер записи + YOLO**, что и другие включённые триггеры (**ИЛИ** с Frigate и опционально OpenCV). За окно записи подмешиваются события Frigate/BirdNET (`merge_detections`). Нужны `mqtt.broker`, источник весов с MQTT и топик (**`mqtt_topic`** или **`{mqtt_topic_prefix}/weight`**). В новых конфигах предпочтительнее **`triggers.scales.enabled`**; хаб по-прежнему учитывает legacy `integrations.scales.motion_trigger_*` при сборке эффективных триггеров. |
| `integrations.scales.motion_trigger_min_delta_kg` | Минимум \|Δмассы\| между **двумя последовательными** MQTT-сообщениями (в кг), чтобы считать это триггером. По умолчанию **0.02** (20 г). |
| `integrations.scales.motion_trigger_debounce_seconds` | Минимум секунд между двумя стартами записи по весам (анти-дребезг). По умолчанию **1.5**. |

Процессор сравнивает min/max веса в окне `[start_time, end_time]` ролика. При **`estimate_require_consecutive_spike: true`** (по умолчанию) оценка в БД сохраняется только если за это окно есть соседняя пара показаний с шагом ≥ порога (см. ключ выше); иначе отсекается дрейф — при этом записываемое значение по-прежнему размах max−min. Если дельта не ниже порога — в БД пишется `scales_weight_delta_kg`, в UI показывается блок «Весы (оценка)». Триггеры уведомлений и auto-tare в HA/ESPHome — по-прежнему в [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167).

**Стек как у [умных весов с ESPHome + HA](https://github.com/igiannakas/Homeassistant-scale-with-auto-tare-and-object-detection?tab=readme-ov-file#hardware-setup)** (HX711, ESP32, проксимити, auto-tare в Home Assistant): BirdLense можно подключить двумя способами:
- `mqtt`: подписать processor на топики прошивки веса
- `esphome`: опрашивать само устройство по ESPHome Web API для live weight / bird_present / tare

**BirdLense ESPHome MQTT-прошивка (репо `bird-feeder-scale.yaml`):** используйте `source: mqtt`. По умолчанию достаточно `mqtt_topic_prefix: birdlense/scale` — хаб сам возьмёт **`birdlense/scale/weight`**, **`birdlense/scale/bird_present`** и **`birdlense/scale/command`**. Если раскладка смешанная — оставьте `source: mqtt`, но явно переопределите `mqtt_topic`, `mqtt_bird_present_topic` или `mqtt_command_topic`.

### ESPHome / своя прошивка (`birdlense/scale/*`)

Задайте **`integrations.scales.mqtt_topic_prefix`**: например **`birdlense/scale`**; это значение уже стоит по умолчанию. Оставьте **`mqtt_topic`** пустым, брокер — тот же, что у процессора.

| Топик | Данные | Retain (типично) | Хаб |
|-------|--------|------------------|-----|
| `{prefix}/weight` | Строка с числом | да | `feeder_scale_state.json`, журнал, опционально триггер записи |
| `{prefix}/bird_present` | `ON` / `OFF` | да | поле `bird_present` в состоянии (карточка кормушки) |
| `{prefix}/command` | например `TARE` | нет | публикация с **`POST /api/ui/feed/scale-tare`** (админ); прошивка должна подписаться |

В прошивке публикуйте вес **текстовой десятичной строкой** (в ESPHome — например `str_sprintf` в lambda для `mqtt.publish`). Для тары подпишитесь на command topic (`on_message` в компоненте `mqtt`).

**Пример в репозитории:** [`esphome/bird-feeder-scale.yaml.example`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/esphome/bird-feeder-scale.yaml.example) (локально скопировать в `bird-feeder-scale.yaml`), [`esphome/README.md`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/esphome/README.md).

---

## Notifications (Telegram)

| Ключ | Описание |
|------|----------|
| `general.enable_notifications` | Включить уведомления |
| `notifications.telegram_bot_token` | Токен бота (@BotFather → /newbot) |
| `notifications.telegram_chat_id` | ID чата или канала (например -1001234567890) |
| `notifications.base_url` | URL Hub для ссылок на видео/Live. Если пусто, относительные ссылки не превратятся в полный URL, а Telegram link preview будет менее полезен |
| `notifications.telegram_proxy_type` | `none` — без прокси; `socks_http` — URL ниже (обычный случай); `mtproto` — сервер/порт/секрет как в приложении Telegram + **api_id/api_hash** |
| `notifications.telegram_proxy_url` | При `socks_http`: прокси к Bot API (`socks5h://…`, `http://…`). Пусто — напрямую. В образе web — `requests[socks]`. |
| `notifications.telegram_mtproto_host` / `telegram_mtproto_port` / `telegram_mtproto_secret` | Только при `mtproto`; секрет — hex из приложения Telegram |
| `notifications.telegram_api_id` / `telegram_api_hash` | Только при `mtproto`; выдаётся на **https://my.telegram.org** → API development tools (или env `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`) |
| `notifications.telegram_api_base` | Пусто — `https://api.telegram.org`; иначе база вашего HTTPS-прокси |
| `notifications.telegram_timeout` | Таймаут запросов к Telegram (сек; для текста используется половина) |
| `notifications.telegram_retries` | Число повторов при таймауте/ошибке сети |
| `notifications.compress_photo_over_kb` | Сжимать JPEG больше N КБ (0 — не по размеру) |
| `notifications.telegram_max_side_px` | Макс. сторона кадра в пикселях перед отправкой (0 — не менять) |
| `notifications.message_thread_id` | ID топика в канале с форумом |
| `notifications.disable_notification` | Тихие сообщения (без звука) |
| `notifications.protect_content` | Запретить пересылку и сохранение |
| `notifications.link_preview_large` | true: большие превью ссылок (Bot API 9.4), ссылка добавляется в текст/подпись. Это дополнение к фото, а не замена `sendPhoto` |
| `notifications.use_custom_emoji` | true: icon_custom_emoji_id на кнопках (требует Premium у владельца бота) |
| `notifications.custom_emoji_id_bird` | ID кастомного эмодзи для птиц (из @Stickers) |
| `notifications.custom_emoji_id_chipmunk` | ID emoji для грызунов / мелких млекопитающих (Telegram) |
| `notifications.custom_emoji_id_open_live` | ID для кнопки Open Live |
| `notifications.paid_media_view_star_count` | Stars за просмотр фото (0=бесплатно, 1–25000). sendPaidMedia |
| `notifications.paid_media_forward_star_count` | При бесплатном просмотре: 0=разрешить пересылку, >0=запретить. При платном — пересылка включена. |
| `general.notification_excluded_species` | Виды, исключённые из уведомлений |
| `processor.save_images` | При true — сохранять кадры детекций на диск для отладки. На отправку фото в Telegram не влияет |
| `processor.save_dataset_crops` | По умолчанию **false** (включать явно). При true — сохранять best_frame в `data/dataset/train/<Species>/` для экспорта и дообучения |
| `processor.dataset_min_confidence` | Мин. confidence (0.0–1.0) для сохранения кадра в датасет. По умолчанию 0.5 |

**Как BirdLense отправляет Telegram-уведомление:** сначала пытается отправить именно **фото** (`sendPhoto` / MTProto media) из `best_frame`; если его нет — из bbox-crop по видео; если и это не удалось — полный кадр. При ошибке Telegram или битом превью делается fallback на текстовое сообщение со ссылкой/кнопкой, а причина fallback пишется в наблюдаемость (System → Observability).

**Telegram Bot API 9.4/9.5:** кнопки с эмодзи и стилем (primary), динамическое время `<tg-time format="r">`, большие превью ссылок (`link_preview_large`).

### Если my.telegram.org выдаёт ERROR и не даёт создать приложение

Сайт **https://my.telegram.org** — сервис Telegram; BirdLense на него не влияет. Часто ломается из части сетей (без VPN/с VPN, капча, лимиты).

**Что делать без api_id / api_hash:** не используйте тип прокси **MTProto** в настройках Hub. Выберите **SOCKS5 / HTTP** и укажите URL любого прокси, через который ваш сервер **достучится до `https://api.telegram.org` по HTTPS** (например свой `socks5h://…` на VPS или дома), либо **без прокси**, если доступ к Bot API уже есть. Для этого **пары api_id/api_hash не требуется** — достаточно токена бота и `chat_id`.

Режим **MTProto** в Hub нужен только если вы **намеренно** шлёте трафик через **MTProto-прокси** (как в клиенте Telegram); он технически завязан на Telethon и **обязателен** api_id+api_hash с my.telegram.org — без работающего сайта этот путь недоступен, пока вы не получите ключи другим способом (другая сеть, VPN, другое устройство, помощь знакомого).

Проверенный источник публичных SOCKS5-списков (для быстрого подбора): [ProxyGenerator](https://github.com/proxygenerator1/ProxyGenerator).

Пример проверки прокси (ожидаем `404`/`401` от Telegram API — это нормально, значит канал до Telegram работает):
`curl --proxy socks5h://IP:PORT --max-time 12 -s -o /dev/null -w "%{http_code}" https://api.telegram.org/botINVALID/getMe`

⚠️ Публичные прокси нестабильны и небезопасны для долгой эксплуатации; предпочтительнее свой SOCKS5/HTTPS-прокси.

Автоподбор лучшего прокси на прод-сервере (разовый запуск):
`make refresh-telegram-proxy`

Автонастройка по расписанию (просто для пользователя):
- Установить cron на сервере (по умолчанию каждые 6 часов): `make proxy-rotation-install`
- Проверить статус и последние логи: `make proxy-rotation-status`
- Удалить расписание: `make proxy-rotation-remove`

Скрипт `scripts/refresh-telegram-proxy.sh` тестирует прокси с самого хоста Hub, выбирает самый быстрый рабочий, обновляет `notifications.telegram_proxy_type=socks_http` и `notifications.telegram_proxy_url`, делает backup `user_config.yaml` и перезапускает контейнер только при изменении.

> Важно: после обновления репозитория с новыми скриптами выполните `make deploy` один раз, затем ставьте расписание.

### Кастомные эмодзи на кнопках (Premium)

Переключатель `use_custom_emoji` и поля ID управляют отображением эмодзи на кнопках в сообщениях:

| Режим | Поведение |
|-------|-----------|
| **Выкл** (по умолчанию) | Unicode-эмодзи (🐦, 🐿️, 📺) — видны всем подписчикам |
| **Вкл** | `icon_custom_emoji_id` (Bot API 9.4) — требует **Telegram Premium у владельца бота** |

При включённом переключателе отображаются поля для ID:

- `custom_emoji_id_bird` — для уведомлений о птицах
- `custom_emoji_id_chipmunk` — для грызунов / мышей (слот emoji в Telegram)
- `custom_emoji_id_open_live` — для кнопки «Open Live» (старт приложения, общие сообщения)

Если ID не указан — используется обычный Unicode-эмодзи.

**Как получить ID кастомного эмодзи:**

1. Отправьте сообщение с нужным кастомным эмодзи в чат с ботом [@RawDataBot](https://t.me/RawDataBot) — в ответе будет `custom_emoji_id`.
2. Либо используйте бота [@Stickers](https://t.me/Stickers) для получения ID из стикерпаков.
3. Вставьте числовой ID (например, `5368324170671202286`) в соответствующее поле настроек.

### Web Push

Push-уведомления в браузере (дополнение или альтернатива Telegram). Работает при HTTPS (или localhost).

| Ключ | Описание |
|------|----------|
| `web_push.enabled` | Включается автоматически при первой подписке через UI |
| `web_push.vapid_public_key` | Публичный VAPID-ключ (генерируется автоматически при первом использовании) |
| `web_push.vapid_private_key` | Приватный VAPID-ключ (секрет, маскируется в API) |

**Настройка:** Настройки → Уведомления → «Включить Web Push». Браузер запросит разрешение; подписка сохраняется на сервере. При детекции вида push отправляется всем подписчикам.

**Требования:** HTTPS (или localhost), включённые уведомления (`general.enable_notifications`), `notifications.base_url` для ссылки в push. Подписка через UI теперь требует тот же доступ, что и настройки (`settings_check_access()`), чтобы посторонний клиент в сети не мог молча включить `web_push.enabled`.

## UI

| Ключ | Описание | Где настраивать |
|------|----------|-----------------|
| `unknown_confidence_threshold` | Порог (0–1) для «Неизвестные». По умолчанию **0.48** | Настройки → Процессор → блок «Дополнительно» |

---

## Webhook

| Ключ | Описание |
|------|----------|
| `url` | URL для POST при каждой детекции. JSON: species, confidence, time, source. Для IFTTT, Zapier, своих скриптов |

**Ограничения безопасности:** разрешены только `http`/`https` URL. Приватные / loopback / link-local адреса (`127.0.0.1`, `192.168.x.x`, `10.x.x.x`, `localhost` и т.п.) блокируются, чтобы webhook не использовался как SSRF-прокси во внутреннюю сеть.

**Trusted proxy:** если Gunicorn стоит за доверенным reverse proxy и нужно учитывать `X-Real-IP` / `X-Forwarded-For` для rate-limit, задайте `TRUSTED_PROXY=1` (см. таблицу «Переменные окружения»). Без этого BirdLense берёт IP только из `remote_addr`.

---

## eBird

| Ключ | Описание |
|------|----------|
| `ebird.country` | Код страны (2 символа: US, RU и т.д.) |
| `ebird.state` | Регион (1–3 символа: NY, CA, MOS для Московской обл.) |
| `ebird.location_name` | Название локации для чеклиста |
| `ebird.protocol` | Stationary \| Traveling \| Incidental \| Historical |
| `ebird.species_mapping` | Маппинг eBird → BirdLense для «Сравнение с регионом». eBird использует Gray (US), BirdLense — Grey (EU). Пример: `Gray-headed Woodpecker: Grey-headed Woodpecker` |
| `secrets.ebird_api_key` | Ключ eBird API для карточки «Сравнение с регионом» на Overview. Получить: [ebird.org/api/keygen](https://ebird.org/api/keygen) |

Настройки → Расширенные. Экспорт «Экспорт для eBird» в Timeline не требует API ключа. Ключ нужен для фичи «Сравнение с регионом».

Подсказки для маппинга: в настройках у поля `ebird.species_mapping` кнопка подгружает региональный топ eBird и предлагает строки (регистр / нечёткое совпадение); `GET /api/ui/settings/ebird-species-mapping-suggestions` (тот же доступ, что у настроек). См. [#136](https://github.com/Gfermoto/BirdLense-Hub/issues/136).

Фильтр видов **«Региональные»** использует тот же региональный топ eBird, что и блок сравнения на Migration, **и** виды с хотя бы одной детекцией **BirdNET MQTT** (`detection_provider` = `birdnet_mqtt`). См. [#132](https://github.com/Gfermoto/BirdLense-Hub/issues/132).

**Россия, Московская область:** `ebird.country=RU`, `ebird.state=MOS` (или `MO`). Регион для API: RU-MOS.

---

## MCP

| Ключ | Описание |
|------|----------|
| `enabled` | Включить MCP-сервер |
| `token` | Токен доступа (или MCP_TOKEN в env) |

---

## Prometheus / Grafana {#prometheus--grafana}

Эндпоинты `GET /metrics` и `GET /api/metrics` — формат Prometheus.

**Prometheus** — в `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'birdlense'
    metrics_path: '/api/metrics'
    static_configs:
      - targets: ['birdlense:8085']  # или ваш хост:порт
    scrape_interval: 15s
```

**Метрики:** CPU, память, диск, GPU (если есть), `birdlense_detections_total`, `birdlense_species_count`, `birdlense_videos_total`.

**Опционально (хаб доступен извне):** переменная **`BIRDLENSE_METRICS_TOKEN`** — если задана непустая строка, эндпоинты `GET /metrics`, `GET /api/metrics` и `GET /api/metrics/summary` отвечают **401** без заголовка `Authorization: Bearer <тот же токен>`. В **Prometheus** для scrape добавьте `authorization` / `bearer_token` (см. документацию Prometheus к вашей версии).

**Grafana** — Prometheus datasource, дашборд по метрикам.

### История метрик на странице «Система» {#system-page-metrics-history}

Отдельно от Prometheus: в SQLite таблица `system_resource_sample`, фоновый sampler пишет снимки CPU/RAM/диск/GPU. UI запрашивает `GET /api/ui/system/metrics/history`.

| Переменная окружения | По умолчанию | Диапазон | Назначение |
|----------------------|--------------|----------|------------|
| `BIRDLENSE_SYSTEM_METRICS_INTERVAL_SEC` | `30` | 10–600 | Интервал между снимками (секунды) |
| `BIRDLENSE_SYSTEM_METRICS_RETENTION_HOURS` | `72` | 6–720 | Удаление записей старше (часы) |
| `DISABLE_SYSTEM_METRICS_SAMPLER` | — | `1` / `true` | Не запускать sampler (тесты, отладка) |

### Алертинг (Prometheus + Alertmanager)

Готовые примеры в репозитории (подстройте пороги и имя `job` под ваш `scrape_configs`):

| Файл | Назначение |
|------|------------|
| [`examples/prometheus/birdlense.rules.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/examples/prometheus/birdlense.rules.yml) | Алерты: таргет недоступен, диск/память/CPU, опционально «нет новых детекций за 24 ч» |
| [`examples/prometheus/alertmanager.birdlense.example.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/examples/prometheus/alertmanager.birdlense.example.yml) | Каркас Alertmanager: `route` / `receivers` |

**Prometheus** — добавьте `rule_files` рядом со `scrape_configs`:

```yaml
rule_files:
  - 'birdlense.rules.yml'   # путь к скопированному примеру
```

**Замечания:**

- Правила по умолчанию ожидают scrape с **`job_name: birdlense`** (см. `up{job="birdlense"}`). Если имя job другое — обновите матчеры в файле правил.
- **`BirdlenseDetectionsUnchanged24h`** — опционально: срабатывает в межсезонье или при выключенной кормушке; увеличьте `for`, замьте в Alertmanager или удалите группу `birdlense-optional-activity`.
- Отдельных правил по GPU нет: `birdlense_gpu_usage_percent` экспортируется только при доступной статистике GPU; «зависания» смотрите в **System → Processor logs** и `/api/ui/status`.

Задача: [issue #57](https://github.com/Gfermoto/BirdLense-Hub/issues/57).

---

## Secrets

Координаты и ключи. Настройки → Расширенные. Рекомендуется env: `OPENWEATHER_API_KEY`.

| Ключ | Описание |
|------|----------|
| `openweather_api_key` | OpenWeather API для виджета погоды |
| `xeno_canto_api_key` | Xeno-canto API для воспроизведения птичьих песен (xeno-canto.org/account) |
| `ebird_api_key` | eBird API для сравнения с регионом (ebird.org/api/keygen) |
| `latitude`, `longitude` | Координаты для погоды и eBird |

**Ротация в проде** (бэкап, перезапуск, проверка, откат): [SECRETS_ROTATION.ru.md](../../archive/internal/docs-legacy/SECRETS_ROTATION.ru.md).

---

## Корм для птиц (каталог по умолчанию)

В приложении есть **встроенный список** типичных кормов (ориентация US + EU). **Источник в коде:** [`app/web/seed/seed.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/seed/seed.py) → `seed_bird_food()`. Поля `image_url` ссылаются на `data/images/food/*` в поставке.

**Уже существующие БД:** при каждом старте `seed()` **добавляет только отсутствующие по имени** позиции каталога — обновление образа не создаёт дубликаты. Устаревшая позиция **Apple pieces** при старте **удаляется** (см. `seed.py`); связи с записями видео для неё очищаются. Свой корм по-прежнему можно завести через **`GET` / `POST /api/ui/birdfood`** (см. [API.ru.md](./api.ru.md)).

Задача: [issue #134](https://github.com/Gfermoto/BirdLense-Hub/issues/134).

---

## См. также {#see-also}

[INSTALL](./install.ru.md) · [ARCHITECTURE](./architecture.ru.md) · [ACCESS_CONTROL](./access-control.ru.md) · [API](./api.ru.md) · [SCENARIOS](./scenarios.ru.md) · [GLOSSARY](./glossary.ru.md) · [SECRETS_ROTATION](../../archive/internal/docs-legacy/SECRETS_ROTATION.ru.md) · [PUBLIC_RELEASE_CHECKLIST](../../archive/internal/docs-legacy/PUBLIC_RELEASE_CHECKLIST.ru.md)

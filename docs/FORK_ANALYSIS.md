# Сравнение BirdLense Hub с исходным проектом

Сравнение BirdLense Hub с [BirdLense](https://github.com/AleksandrRogachev94/BirdLense) (upstream).

---

## 1. Что реализовано (добавлено/изменено)

### 1.1 Архитектура и деплой

| Компонент | Исходник | Наш форк |
|-----------|----------|----------|
| **Docker** | Несколько compose (base, dev, prod, server, go2rtc), отдельные Dockerfile для ui/web/processor/nginx | Один `docker-compose.yml`, один `Dockerfile` — всё в одном контейнере |
| **Деплой** | Нет единого скрипта | `scripts/deploy.sh` — tar+ssh, исключает `app/data`, не перезаписывает записи |
| **Образ** | Только локальная сборка | GitHub Actions → `ghcr.io/gfermoto/birdlense-hub:latest`, `make pull` |
| **Версия** | Нет | `VERSION`, теги `v0.1.0-alpha.1`, GitHub Release |

### 1.2 Видео и источники

| Компонент | Исходник | Наш форк |
|-----------|----------|----------|
| **Видео** | Pi Camera (Picamera2), MediaSource | **Go2RTC** — RTSP/HLS с IP-камеры, без RPi |
| **Детекция движения** | PIR (GPIO), Fake | **OpenCV**, **Frigate MQTT**, **MQTT binary**, **ESPHome** |
| **MQTT** | Нет | Frigate events, BirdNET sightings, единый `MQTTEventAggregator` |

### 1.3 Модели

| Компонент | Исходник | Наш форк |
|-----------|----------|----------|
| **Детекция** | NCNN (ARM/RPi) | PyTorch `.pt` (x86/amd64) |
| **Классификация** | NCNN | PyTorch `.pt` |
| **Стратегия** | Single/Two stage | То же + конфиг `detection_strategy` |

### 1.4 UI и настройки

| Компонент | Исходник | Наш форк |
|-----------|----------|----------|
| **Локализация** | Нет | i18n (ru/en), LanguageSwitcher |
| **Настройки** | Один блок | Разделы: 1) Connection (MQTT, Go2RTC), 2) Cameras, 3) Motion, 4) Feed, 5) Notifications, 6) Weather, 7) Security, 8) MCP |
| **Безопасность** | Нет | Пароль доступа к настройкам |
| **FeedCard** | FoodManagement (привязка корма к видам) | FeedCard — кнопка «Выдать корм» (MQTT/ESPHome) |
| **FoodManagement** | Есть | Есть (привязка корма к видам) |

### 1.5 MCP и интеграции

| Компонент | Исходник | Наш форк |
|-----------|----------|----------|
| **MCP** | Есть (базово) | FastMCP, OpenAPI→tools, токен, прокси `/mcp`, `/sse`, docs/MCP_SETUP.md |
| **Погода** | OpenWeather | OpenWeather + исправление координат (запятая→точка) |
| **Записи** | `data/recordings` | `DATA_DIR` + «Сканировать и импортировать» |

### 1.6 Тестирование и документация

| Компонент | Исходник | Наш форк |
|-----------|----------|----------|
| **E2E** | Нет | Playwright (smoke, settings, api), поддержка пароля |
| **Документация** | README | docs: ARCHITECTURE, CONFIGURATION, API, DEPLOYMENT, MCP_SETUP, MQTT, TESTING |

---

## 2. От чего отказались

| Компонент | Причина |
|-----------|---------|
| **Pi Camera** | Цель — x86/Docker, без RPi |
| **PIR (GPIO)** | Нет доступа к GPIO в контейнере |
| **LLM Verifier (Google Gemini)** | Удалён — экономия, упрощение, облачная зависимость |
| **DailySummary** | Удалён из UI (AI-сводки по дням) |
| **AudioProcessor (birdnetlib)** | Аудио только через MQTT (BirdNET-Pi/Go отдельно) |
| **NCNN модели** | Переход на PyTorch для x86 |
| **Множество docker-compose** | Упрощение до одного compose |
| **MediaSource (универсальный)** | Заменён на Go2RTCStreamSource, VideoFileSource |

---

## 3. Что упустили (есть в исходнике, нет у нас)

| Компонент | Описание | Приоритет |
|-----------|----------|-----------|
| **LLM Verifier** | Верификация низкоуверенных детекций через Gemini | Низкий (облако, стоимость) |
| **DailySummary** | AI-сводки по дням в Overview | Средний |
| **Track trajectory overlay** | Визуализация траектории трека в UI | Низкий |
| **Manual focus / HDR** | Настройки камеры Pi | N/A (нет Pi Camera) |
| **Squirrel icon** | Отдельная иконка для белки в уведомлениях | Низкий |
| **Full screen video (iOS)** | Исправление полноэкранного режима на iOS | Средний |
| **3D Printing** | Папка с моделями для печати | README ссылается, папки нет |
| **Pinout instructions** | Инструкции по пинам GPIO | N/A (нет PIR) |
| **Best frame selection (LLM)** | Улучшенный выбор кадра для LLM | N/A |
| **Wiki API User-Agent** | Исправление вызова Wiki API | Низкий (если используется) |

### 3.1 Секция 3D Printing

Папки `3d_printing` в репозитории нет. В README нет ссылки на неё.

### 3.2 Потенциально полезное из upstream

- **Track trajectory overlay** — `14de0d8 Added simple track trajectory overlay in UI`
- **Full screen video iOS** — `1dd6986 Fix full scren video mode on ios`
- **Species thumbnail** — `d001158 Improved species thumbnail representation`
- **Combined confidence** — `1cf1d93 Using combined confidence in strategy detection`

---

## 4. Сводка

| Категория | Количество |
|-----------|------------|
| Реализовано/улучшено | ~25 пунктов |
| Отказались | 8 пунктов |
| Упущено | ~10 пунктов |

**Основные отличия форка:** переход с RPi на x86/Docker, Go2RTC вместо Pi Camera, MQTT (Frigate/BirdNET) вместо PIR и локального аудио, один контейнер, MCP, i18n, пароль настроек, готовый образ на ghcr.io.

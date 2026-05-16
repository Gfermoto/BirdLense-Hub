# BirdLense Hub — обзор проекта

**BirdLense Hub** — открытое ПО для **мониторинга птиц у кормушек, в саду и на площадках**: детекция на видео, классификация видов локальным ML, запись роликов и структурированный таймлайн для операторов, орнитологии и гражданской науки.

[English](../user/overview.md)

---

## Зачем это нужно

- **Приватность:** основная обработка на **вашем** железе (Docker), без облака вендора для распознавания.
- **Совместимость:** [Go2RTC](https://github.com/AlexxIT/go2rtc) для потоков, по желанию [Frigate](https://frigate.video/) + Bird Classification, [BirdNET](https://birdnet.cornell.edu/) по MQTT, Home Assistant, Telegram.
- **Citizen science:** экспорт в **eBird** и **iNaturalist**, сравнение с регионом, датасеты для дообучения.

---

## Кому подойдёт

| Аудитория | С чего начать |
|-----------|----------------|
| **Наблюдатели, кольцеватели** | [INSTALL](../user/install.md) → [SCENARIOS](./scenarios.ru.md) — учёт визитов, экспорт (eBird, CSV), проверка неуверенных детекций |
| **Исследователи, станции** | [CONFIGURATION](./configuration.ru.md), [DATASETS](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/DATASETS.ru.md), [TRAINING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/TRAINING.ru.md) — каталоги, датасеты, свои веса |
| **Frigate / Home Assistant** | [SCENARIOS](./scenarios.ru.md), [CONFIGURATION](./configuration.ru.md) |
| **Разработчик / контрибьютор** | [LOCAL_DEV](./local-dev.ru.md), [Contributing](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md), [ARCHITECTURE](../contributor/architecture.md) |
| **Автор статей / лендинга** | Эта страница + [FEATURES](./features.ru.md) |

---

## Что где крутится

- **Один контейнер:** nginx, веб-API (Flask), опционально MCP и **processor** (видео, YOLO, ByteTrack, FFmpeg, MQTT).
- **Снаружи:** Go2RTC (желательно), MQTT, опционально Frigate, BirdNET-Pi/Go, ESPHome/Tasmota.

Схема и потоки данных: [ARCHITECTURE](../contributor/architecture.md).

---

## Как устроено распознавание

- **Детектор + классификатор (YOLO):** птица или грызун (Rodent) в кадре, затем вид. По умолчанию **EU**-модель (~491 вид); веса US — в [TRAINING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/TRAINING.md).
- **Frigate** может отдавать **Bird Classification** (`sub_label`); результаты сливаются с видео-ML.
- **BirdNET** — слияние по времени при настроенном MQTT.

---

## Карта документации

| Задача | Документ |
|--------|----------|
| Установка и деплой | [INSTALL](../user/install.md) |
| Сценарии «как настроить X» | [SCENARIOS](./scenarios.ru.md) |
| Все параметры | [CONFIGURATION](./configuration.ru.md) |
| Термины | [GLOSSARY](./glossary.ru.md) |
| Список возможностей | [FEATURES](./features.ru.md) |
| Проблемы | [TROUBLESHOOTING](./troubleshooting.ru.md) |
| Тесты и проверка после деплоя | [TESTING](./testing.ru.md) |
| CI и локальный полный прогон (`make ci-local`) | [CI_AND_QUALITY](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/CI_AND_QUALITY.ru.md) |
| Полный индекс | [docs/README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/README.ru.md) |
| Карта разделов для сайта | [SITE_MAP](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/SITE_MAP.ru.md) |

**OpenAPI:** [спецификация YAML](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/openapi.yaml).

---

## Сайт и статьи на базе репозитория

**Этот файл** — сюжет «что и зачем»; **INSTALL** + **SCENARIOS** — быстрый старт; **FEATURES** — витрина возможностей; **ARCHITECTURE** — техника. Правила оформления: [Documentation](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/Documentation.ru.md). Локализация: [I18N_STATUS](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/I18N_STATUS.md).

---

## Версия

Актуальная линейка релизов: бейдж в [корневом README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/README.md) и [Changelog](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md).

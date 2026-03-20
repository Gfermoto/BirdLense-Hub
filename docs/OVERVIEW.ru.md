# BirdLense Hub — обзор проекта

**BirdLense Hub** — открытое ПО для **умной кормушки и наблюдения за садом**: детекция птиц (и белок) на видео, классификация видов локальным ML, запись роликов и таймлайн, которым владеете вы.

[English](./OVERVIEW.md)

---

## Зачем это нужно

- **Приватность:** основная обработка на **вашем** железе (Docker), без облака вендора для распознавания.
- **Совместимость:** [Go2RTC](https://github.com/AlexxIT/go2rtc) для потоков, по желанию [Frigate](https://frigate.video/) + Bird Classification, [BirdNET](https://birdnet.cornell.edu/) по MQTT, Home Assistant, Telegram.
- **Citizen science:** экспорт в **eBird** и **iNaturalist**, сравнение с регионом, датасеты для дообучения.

---

## Кому подойдёт

| Аудитория | С чего начать |
|-----------|----------------|
| **Дом / любитель природы** | [INSTALL](./INSTALL.md) → [SCENARIOS](./SCENARIOS.ru.md) |
| **Пользователь Frigate / HA** | [SCENARIOS](./SCENARIOS.ru.md), [CONFIGURATION](./CONFIGURATION.ru.md) |
| **Разработчик / контрибьютор** | [LOCAL_DEV](./LOCAL_DEV.ru.md), [Contributing](./project/contributing.md), [ARCHITECTURE](./ARCHITECTURE.md) |
| **Автор статей / лендинга** | Эта страница + [FEATURES](./FEATURES.ru.md) |

---

## Что где крутится

- **Один контейнер:** nginx, веб-API (Flask), опционально MCP и **processor** (видео, YOLO, ByteTrack, FFmpeg, MQTT).
- **Снаружи:** Go2RTC (желательно), MQTT, опционально Frigate, BirdNET-Pi/Go, ESPHome/Tasmota.

Схема и потоки данных: [ARCHITECTURE](./ARCHITECTURE.md).

---

## Как устроено распознавание

- **Детектор + классификатор (YOLO):** птица/белка в кадре, затем вид. По умолчанию **EU**-модель (~491 вид); веса US — в [TRAINING](./TRAINING.md).
- **Frigate** может отдавать **Bird Classification** (`sub_label`); результаты сливаются с видео-ML.
- **BirdNET** — слияние по времени при настроенном MQTT.

---

## Карта документации

| Задача | Документ |
|--------|----------|
| Установка и деплой | [INSTALL](./INSTALL.md) |
| Сценарии «как настроить X» | [SCENARIOS](./SCENARIOS.ru.md) |
| Все параметры | [CONFIGURATION](./CONFIGURATION.ru.md) |
| Термины | [GLOSSARY](./GLOSSARY.ru.md) |
| Список возможностей | [FEATURES](./FEATURES.ru.md) |
| Проблемы | [TROUBLESHOOTING](./TROUBLESHOOTING.ru.md) |
| Тесты и проверка после деплоя | [TESTING](./TESTING.ru.md) |
| Полный индекс | [docs/README](./README.ru.md) |
| Карта разделов для сайта | [SITE_MAP](./SITE_MAP.ru.md) |

**OpenAPI:** [спецификация YAML](./project/openapi.md).

---

## Сайт и статьи на базе репозитория

**Этот файл** — сюжет «что и зачем»; **INSTALL** + **SCENARIOS** — быстрый старт; **FEATURES** — витрина возможностей; **ARCHITECTURE** — техника. Правила оформления: [Documentation](./Documentation.ru.md). Локализация: [I18N_STATUS](./I18N_STATUS.md).

---

## Версия

Актуальная линейка релизов: бейдж в [корневом README](./project/root-readme.md) и [Changelog](./project/changelog.md).

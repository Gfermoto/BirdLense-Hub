# Roadmap — BirdLense Hub

[English](./ROADMAP.md)

---

План развития и текущий стек. Март 2026.

---

## Текущий стек


|                 | Версия                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------ |
| **Ultralytics** | 8.4.21 (Docker base)                                                                       |
| **Платформа**   | x86/amd64 (ARM не поддерживается)                                                          |
| **Архитектура** | two_stage: binary (.pt) + YOLO11n-cls (EU). single_stage — fallback при отсутствии моделей |
| **EU-модель**   | `best.pt` — birds-525 + iNaturalist (~491 вид)                                             |
| **US-модель**   | `best_US.pt` — NABirds (резерв)                                                            |
| **React**       | 19.2.4                                                                                     |
| **Vite**        | 6.4.1                                                                                      |


---

## Фичи (выполнено)

- **Home Assistant** — MQTT Autodiscovery (sensor.birdlense_last_species, binary_sensor.bird_detected). См. [CONFIGURATION](./CONFIGURATION.ru.md) — MQTT.
- **Датасет** — best_frame в YOLO format, экспорт ZIP (`GET /api/ui/dataset/export`), коррекция вида перемещает файл. Система → Управление хранилищем.

---

## Консилиум по бэклогу (март 2026)

**Роли (мозговой штурм):** продукт/оператор, безопасность, платформа и CI, ML и данные, интеграции (MQTT, HA, Frigate), UX, документация и open-source гигиена.

**Результат:** задачи заведены как **Issues** на GitHub: [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46)–[#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57).

**Карточки на доске Project** (нужны scope `project` и `read:project` у `gh`):

```bash
gh auth refresh -h github.com -s read:project -s project   # или полный gh auth login с этими scope
bash scripts/github-project-add-backlog-consilium.sh
```

Все открытые issues/PR: `bash scripts/github-project-import-open-items.sh`. Либо вручную в интерфейсе GitHub.

| # | Тема | Issue | Приоритет / зона |
|---|------|-------|------------------|
| 1 | Rate limit для настроек / auth API | [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46) | P2, web |
| 2 | Скан истории git на секреты | [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) | P3, infra |
| 3 | Скрипт `export_birdlense_to_yolo.py` | [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) | P2, processor |
| 4 | Спайк ARM64 Docker | [#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49) | P3, infra |
| 5 | Устойчивость MQTT, док по пропускам | [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) | P2, processor |
| 6 | UI: бэкап/восстановление SQLite | [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) | P3, web |
| 7 | i18n в UI | [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) | P3, web |
| 8 | CI: периодический smoke образа | [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) | P3, infra |
| 9 | CI: тесты контракта OpenAPI | [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) | P3, web |
| 10 | Чеклист видов за год / life list | [#55](https://github.com/Gfermoto/BirdLense-Hub/issues/55) | P3, web |
| 11 | CORS demo → конфиг/env | [#56](https://github.com/Gfermoto/BirdLense-Hub/issues/56) | P3, web |
| 12 | Доки: примеры алертов Prometheus | [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) | P3, docs |

---

## Идеи (backlog)

От простого к сложному:


| Фича                                   | Описание                                                                                      | Сложность | Риск    |
| -------------------------------------- | --------------------------------------------------------------------------------------------- | --------- | ------- |
| ✅ Playback speed (0.5x, 2x)            | Кнопки в видеоплеере для замедления/ускорения просмотра                                       | Низкая    | Нет     |
| ✅ Webhook (POST при детекции)          | POST на настраиваемый URL с JSON (вид, confidence, время) — для IFTTT, Zapier                 | Низкая    | Нет     |
| ✅ CSV/JSON экспорт статистики          | Скачать визиты, виды, детекции для анализа в Excel/Python                                     | Низкая    | Нет     |
| ✅ Виджет «Последняя птица» на Overview | Блок «Сегодня в 14:32 — Eurasian Jay» на главной                                              | Низкая    | Нет     |
| ✅ Фильтр по времени суток в Timeline   | «Только утро (6–10)», «только вечер» — сузить список визитов                                  | Низкая    | Нет     |
| ✅ PWA improvements                    | Install prompt «Добавить на главный экран», offline cache для статики                         | Низкая    | Нет     |
| ✅ «Неизвестные» (низкий confidence)   | Отдельный список детекций с confidence < порога для ручной проверки и разметки                | Средняя   | Нет     |
| ✅ PDF-отчёт                           | Месячный отчёт: N видов, топ-5, графики — скачать PDF. v0.1.8: брендинг, шапка/футер          | Средняя   | Нет     |
| ✅ Bird song player (Xeno-canto)       | Кнопка «Воспроизвести песню» на карточке вида — аудио из Xeno-canto API                       | Средняя   | Нет     |
| ✅ eBird export                         | Экспорт списка видов в формат eBird для загрузки в приложение                                 | Средняя   | Нет     |
| ✅ Grafana/Prometheus метрики         | `/metrics`, `/api/metrics` — CPU, память, диск, GPU, detections, species, videos             | Средняя   | Нет     |
| ✅ Confidence по виду                   | Разные пороги min_confidence для разных видов (редкие — ниже)                                 | Средняя   | Низкий  |
| ✅ Экспорт в iNaturalist               | Кнопка «Отправить в iNaturalist» — crop + вид для citizen science                             | Средняя   | Нет     |
| ✅ Web Push                             | Push-уведомления в браузере вместо/дополнение Telegram                                        | Средняя   | Низкий  |
| ✅ Публичная галерея                   | Opt-in: загрузка лучших кадров на настраиваемый URL. См. [CONFIGURATION](./CONFIGURATION.ru.md) — Gallery | Высокая   | Средний |
| ✅ Календарь миграций                  | «Вид X обычно появляется в марте» — по историческим данным                                    | Высокая   | Нет     |
| ✅ Сравнение с регионом               | Карточка на Overview: ваши виды в топе региона + полный топ региона (eBird API)               | Высокая   | Средний |
| ✅ Закат и рассвет на карточке погоды | Восход, закат, рассвет, сумерки, полдень — дуга солнца (в стиле Horizon Card) на выбранную дату в локации из настроек | Низкая    | Нет     |

### UX backlog

| # | Улучшение | Описание | Статус |
|---|-----------|----------|--------|
| 4 | Календарь активности | MonthPicker — выбор месяца (сейчас только текущий) | ✅ v0.1.8 |
| 5 | Неизвестные — пустое состояние | Подсказка: «Попробуйте другой день. Bird всегда здесь для проверки.» | ✅ |
| 6 | Неизвестные — выбор времени суток | DatePicker + Утро/День/Вечер/Ночь (как Timeline) вместо прокрутки по часам | ✅ v0.1.9 |

---

## Приоритеты на ближайшее время (публично)

| Приоритет | Фокус |
|-----------|--------|
| **Сообщество** | [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions), метка `good first issue`, обратная связь по докам |
| **Качество** | CI на PR (сборка UI + MkDocs `--strict`), Dependabot / зависимости |
| **Документация** | Баннер версии в `mkdocs.yml` = `VERSION`; интерактивный OpenAPI (Redoc) на сайте |
| **Релизы** | Теги + GitHub Release → semver-образ Docker + деплой Pages |

Таблица бэклога выше — смесь истории и идей; перед задачей сверяйтесь с [FEATURES](./FEATURES.ru.md).

---

См. также: [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md), [DATASETS](./DATASETS.ru.md), [TESTING](./TESTING.ru.md), [CONFIGURATION](./CONFIGURATION.ru.md).
# Roadmap — BirdLense Hub

[English](./ROADMAP.md)

Направление развития и текущий стек (**март 2026**). **Что уже в релизах** — [Changelog](./project/changelog.md) и [FEATURES](./FEATURES.ru.md).

---

## Текущий стек


|                 | Версия                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------ |
| **Ultralytics** | 8.4.21 (Docker base)                                                                       |
| **Платформа**   | **только x86/amd64** (Intel или AMD, 64-bit). ARM / Apple Silicon / aarch64 — **не поддерживается и не планируется** |
| **Архитектура** | two_stage: binary (.pt) + YOLO11n-cls (EU). single_stage — fallback при отсутствии моделей |
| **EU-модель**   | `best.pt` — birds-525 + iNaturalist (~491 вид)                                             |
| **US-модель**   | `best_US.pt` — NABirds (резерв)                                                            |
| **React**       | 19.2.4                                                                                     |
| **Vite**        | 6.4.1                                                                                      |


---

## Фичи (выполнено)

- **Home Assistant** — MQTT Autodiscovery (sensor.birdlense_last_species, binary_sensor.bird_detected). См. [CONFIGURATION](./CONFIGURATION.ru.md) — MQTT.
- **Датасет** — best_frame в YOLO format, экспорт ZIP (`GET /api/ui/dataset/export`), коррекция вида перемещает файл. Система → Управление хранилищем.
- **Видео: предыдущий/следующий ролик (тот же день UTC)** — [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) закрыт (**v0.2.6**): `GET /api/ui/videos/:id/neighbors` и стрелки на странице видео.
- **Overview: средняя длительность записи** — [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) закрыт: метрика = средняя длительность одного ролика (`Video`), не агрегат визита; PR [#106](https://github.com/Gfermoto/BirdLense-Hub/pull/106).
- **Публичная галерея (opt-in)** — [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) закрыт (v0.2.4): фоновая загрузка в **app context** Flask; разбор проблем — [CONFIGURATION.ru](./CONFIGURATION.ru.md) → Gallery.

---

## Консилиум по бэклогу (март 2026)

**Роли (мозговой штурм):** продукт/оператор, безопасность, платформа и CI, ML и данные, интеграции (MQTT, HA, Frigate), UX, документация и open-source гигиена.

**Результат:** задачи заведены как **Issues** на GitHub: [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46)–[#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50)–[#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57), [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) (операторский UX — март 2026; фаза B: snackbar «Открыть видео» на Unknowns). **Сделано:** [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) (скан истории git на секреты + SECURITY), [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) (`export_birdlense_to_yolo.py`), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) (MQTT reconnect backoff + ясность по пропускам в доках), [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) (SQLite backup/restore в UI + INSTALL/TROUBLESHOOTING), [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) (locale switch + пилотная локаль `de`), [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) (scheduled smoke по опубликованному `ghcr` образу), [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) (OpenAPI contract smoke в CI + локальный запуск), [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) (галерея: app context в потоке, v0.2.4), [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) (навигация по роликам за день UTC, v0.2.6), [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) (локальный TZ / соседние сутки / доки), [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) (Overview: средняя длительность = **одна запись** `Video`, не визит). [#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49) (ARM Docker) **закрыт** — только x86; в этом бэклоге не учитывается.

**Карточки на доске Project:** через OAuth/`auth refresh` часто крутится device-login — надёжнее **classic PAT** (`repo` + `project`) в `GH_TOKEN` или `scripts/.env.project` (шаблон `scripts/env.project.example`), затем:

```bash
bash scripts/github-project-add-backlog-consilium.sh
```

Все открытые issues/PR: `bash scripts/github-project-import-open-items.sh`. Либо вручную в интерфейсе GitHub.
Синхронизация статусов/assignee/чеклистов: `bash scripts/github-project-sync.sh --assign Gfermoto`.

| # | Тема | Issue | Приоритет / зона |
|---|------|-------|------------------|
| 1 | Rate limit для настроек / auth API | [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46) ✅ `verify-password`, доки, тесты | P2, web |
| 2 | Скан истории git на секреты | [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) ✅ gitleaks-скрипт + SECURITY EN/RU | P3, infra, documentation |
| 3 | Скрипт `export_birdlense_to_yolo.py` | [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) ✅ экспорт в YOLO cls `train/val` | P2, processor |
| 4 | Устойчивость MQTT, док по пропускам | [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) ✅ reconnect backoff + доки | P2, processor |
| 5 | UI: бэкап/восстановление SQLite | [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) ✅ backup/restore в System + docs | P3, web |
| 6 | i18n в UI | [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) ✅ locale switch + пилотная `de` | P3, web |
| 7 | CI: периодический smoke образа | [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) ✅ workflow `Docker image smoke (published)` (`ghcr ... :latest` + `/api/ui/health`) | P3, infra |
| 8 | CI: тесты контракта OpenAPI | [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) ✅ `openapi-contract` в CI + `web/tests/test_openapi_contract.py` | P3, web |
| 9 | Чеклист видов за год / life list | [#55](https://github.com/Gfermoto/BirdLense-Hub/issues/55) | P3, web |
| 10 | CORS demo → конфиг/env | [#56](https://github.com/Gfermoto/BirdLense-Hub/issues/56) | P3, web |
| 11 | Доки: примеры алертов Prometheus | [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) ✅ `examples/prometheus/`, [CONFIGURATION](./CONFIGURATION.ru.md) | P3, docs |
| 12 | Галерея: не работает — разбор и починка (opt-in) | [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) ✅ app context в потоке загрузки + доки/тесты v0.2.4 | P2, web, bug |
| 13 | Ручная коррекция видов: связать «Неизвестные» и правки внутри видео | [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) 📝 A + B в **v0.2.5** (snackbar «Открыть видео» на Unknowns); фаза C — по запросу | P2, web |
| 14 | Навигация по видео: подряд (напр. за день), без сброса в начало списка | [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) ✅ UI + `GET /videos/:id/neighbors` **v0.2.6** | P2, web |
| 15 | Соседи по видео: локальный TZ, переход на соседние сутки, ясность в доках (надстройка к #82) | [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) ✅ локальный день + `cross_day` + доки API/UI | P3, web |
| 16 | Overview: «Средняя длительность» считалась по визитам, а не по записям | [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) ✅ среднее по `Video` (PR [#106](https://github.com/Gfermoto/BirdLense-Hub/pull/106)); подписи RU/EN | P3, web, bug |

### Триаж: Issue или Discussion

| Куда | Когда |
|------|--------|
| **[Issue](https://github.com/Gfermoto/BirdLense-Hub/issues)** | Понятный объём, критерий готовности, метки `area:*` и приоритет — можно класть на **Project**. |
| **[Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions)** | Идея на проработку, несколько вариантов, «делать или нет», сбор мнений до задачи. |

**После консилиума:** новая отслеживаемая работа → Issue, карточка на доске (`github-project-add-backlog-consilium.sh` или вручную), затем **обновить эту таблицу** в ROADMAP в том же или следующем PR.

**Отчётность (вся работа, не только консилиум):** каждая сданная задача — **Issue** (нет карточки — завести) и при необходимости карточка на доске **BirdLense Hub — Roadmap**. По готовности: комментарий (итог + ссылки на PR), **закрыть** Issue, на доске **Status → Done** (при PAT: `bash scripts/github-project-mark-done.sh <номер>`). Для регулярной уборки рассинхрона использовать `bash scripts/github-project-sync.sh --assign Gfermoto` (выравнивает статус/поток по issue-state, назначает исполнителя на open без assignee, репортит задачи без подзадач). Подробности и чеклист — корневой **[CONTRIBUTING.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.ru.md)** § *Issues и доска Project*.

---

## Кандидаты на будущее (ещё без issue)

Темы для отдельных **Issues**, когда появится слот (сейчас не на доске консилиума):

| Тема | Зачем |
|------|--------|
| **Доступность (a11y)** | Клавиатура, фокус, контраст — логично после i18n ([#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52)). |
| **Расширение E2E (Playwright)** | Не только смоук: логин, таймлайн, критичные настройки — баланс с CI и стабильностью. |
| **Секреты в проде** | Документированная ротация / операционный путь для `secrets.*` (дополняет [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47)). |
| **Синхронизация версий стека** | После bump Ultralytics/React/base image — **этот док**, Docker и release notes одним проходом. |
| **Community / донаты в UI** | Лидерборды, бейджи поддержки и т.п. — на стадии идей; ссылка на донаты уже есть: `general.donate_url` — [CONFIGURATION](./CONFIGURATION.ru.md). |

---

## Отгруженные идеи (архив)

Исторический чеклист **от простого к сложному** (все строки — ✅). Сверяйтесь с [FEATURES](./FEATURES.ru.md); **не** воспринимать таблицу как backlog задач.

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
| ✅ Видео: предыдущий/следующий (день UTC) | Страница видео + `GET /api/ui/videos/:id/neighbors` ([#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82)) | Низкая | Нет |

**Новые идеи:** [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions) или Issue по таблице триажа выше.

### UX-улучшения (отгружено)

| Улучшение | Статус |
|-----------|--------|
| Календарь активности (MonthPicker) | ✅ v0.1.8 |
| Неизвестные — пустое состояние (подсказка) | ✅ |
| Неизвестные — время суток (как в Timeline) | ✅ v0.1.9 |

---

## Приоритеты на ближайшее время (публично)

| Приоритет | Фокус |
|-----------|--------|
| **Сообщество** | [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions), метка `good first issue`, обратная связь по докам |
| **Качество** | CI на PR (сборка UI + MkDocs `--strict`), Dependabot / зависимости |
| **Документация** | Баннер версии в `mkdocs.yml` = `VERSION`; интерактивный OpenAPI (Redoc) на сайте |
| **Релизы** | Теги + GitHub Release → semver-образ Docker + деплой Pages |

Таблица **архива** выше — только история. Активная работа — issues **консилиума** и блок **кандидатов**; сверяйтесь с [FEATURES](./FEATURES.ru.md).

---

См. также: [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md), [DATASETS](./DATASETS.ru.md), [TESTING](./TESTING.ru.md), [CONFIGURATION](./CONFIGURATION.ru.md).
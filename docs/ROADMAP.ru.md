# Roadmap — BirdLense Hub

[English](./ROADMAP.md)

Направление развития и текущий стек (**март 2026**). **Что уже в релизах** — [Changelog](./project/changelog.md) и [FEATURES](./FEATURES.ru.md).

---

## Текущий стек


|                 | Версия                                                                                                               |
| --------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Ultralytics** | 8.4.21 (Docker base)                                                                                                 |
| **Платформа**   | **только x86/amd64** (Intel или AMD, 64-bit). ARM / Apple Silicon / aarch64 — **не поддерживается и не планируется** |
| **Архитектура** | two_stage: binary (.pt) + YOLO11n-cls (EU). single_stage — fallback при отсутствии моделей                           |
| **EU-модель**   | `best.pt` — birds-525 + iNaturalist (~491 вид)                                                                       |
| **US-модель**   | `best_US.pt` — NABirds (резерв)                                                                                      |
| **React**       | 19.2.4                                                                                                               |
| **Vite**        | 6.4.1                                                                                                                |


---

## Фичи (выполнено)

- **Home Assistant** — MQTT Autodiscovery (sensor.birdlense_last_species, binary_sensor.bird_detected). См. [CONFIGURATION](./CONFIGURATION.ru.md) — MQTT.
- **Датасет** — best_frame в YOLO format, экспорт ZIP (`GET /api/ui/dataset/export`), коррекция вида перемещает файл. Система → Управление хранилищем.
- **Видео: предыдущий/следующий ролик (тот же день UTC)** — [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) закрыт (**v0.2.6**): `GET /api/ui/videos/:id/neighbors` и стрелки на странице видео.
- **Overview: средняя длительность записи** — [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) закрыт: метрика = средняя длительность одного ролика (`Video`), не агрегат визита; PR [#106](https://github.com/Gfermoto/BirdLense-Hub/pull/106).
- **Публичная галерея (opt-in)** — [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) закрыт (v0.2.4): фоновая загрузка в **app context** Flask; разбор проблем — [CONFIGURATION.ru](./CONFIGURATION.ru.md) → Gallery.
- **Система: графики ресурсов с историей на сервере** — SQLite `system_resource_sample`, `GET /api/ui/system/metrics/history`, UI с окном 6/24/48 ч и живым хвостом; настройки `BIRDLENSE_SYSTEM_METRICS_*` — [CONFIGURATION.ru](./CONFIGURATION.ru.md) → Prometheus / Grafana.

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


| #   | Тема                                                                                         | Issue                                                                                                                                                            | Приоритет / зона         |
| --- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| 1   | Rate limit для настроек / auth API                                                           | [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46) ✅ `verify-password`, доки, тесты                                                                      | P2, web                  |
| 2   | Скан истории git на секреты                                                                  | [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) ✅ gitleaks-скрипт + SECURITY EN/RU                                                                    | P3, infra, documentation |
| 3   | Скрипт `export_birdlense_to_yolo.py`                                                         | [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) ✅ экспорт в YOLO cls `train/val`                                                                      | P2, processor            |
| 4   | Устойчивость MQTT, док по пропускам                                                          | [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) ✅ reconnect backoff + доки                                                                            | P2, processor            |
| 5   | UI: бэкап/восстановление SQLite                                                              | [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) ✅ backup/restore в System + docs                                                                      | P3, web                  |
| 6   | i18n в UI                                                                                    | [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) ✅ locale switch + пилотная `de`                                                                       | P3, web                  |
| 7   | CI: периодический smoke образа                                                               | [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) ✅ workflow `Docker image smoke (published)` (`ghcr ... :latest` + `/api/ui/health`)                   | P3, infra                |
| 8   | CI: тесты контракта OpenAPI                                                                  | [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) ✅ `openapi-contract` в CI + `web/tests/test_openapi_contract.py`                                      | P3, web                  |
| 9   | Чеклист видов за год / life list                                                             | [#55](https://github.com/Gfermoto/BirdLense-Hub/issues/55) ✅ страница Migration: фильтр по годам + таблица (строки и Σ) — без отдельного дублирующего списка     | P3, web                  |
| 10  | CORS demo → конфиг/env                                                                       | [#56](https://github.com/Gfermoto/BirdLense-Hub/issues/56) ✅ demo-host вынесен из hardcoded CORS defaults в `CORS_DEFAULT_ORIGINS` / `CORS_ORIGINS`              | P3, web                  |
| 11  | Доки: примеры алертов Prometheus                                                             | [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) ✅ `examples/prometheus/`, [CONFIGURATION](./CONFIGURATION.ru.md)                                      | P3, docs                 |
| 12  | Галерея: не работает — разбор и починка (opt-in)                                             | [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) ✅ app context в потоке загрузки + доки/тесты v0.2.4                                                   | P2, web, bug             |
| 13  | Ручная коррекция видов: связать «Неизвестные» и правки внутри видео                          | [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) ✅ фазы A+B+C: единый API + snackbar «Открыть видео» + журнал последних ручных правок (Unknowns/Video) | P2, web                  |
| 14  | Навигация по видео: подряд (напр. за день), без сброса в начало списка                       | [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) ✅ UI + `GET /videos/:id/neighbors` **v0.2.6**                                                         | P2, web                  |
| 15  | Соседи по видео: локальный TZ, переход на соседние сутки, ясность в доках (надстройка к #82) | [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) ✅ локальный день + `cross_day` + доки API/UI                                                          | P3, web                  |
| 16  | Overview: «Средняя длительность» считалась по визитам, а не по записям                       | [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) ✅ среднее по `Video` (PR [#106](https://github.com/Gfermoto/BirdLense-Hub/pull/106)); подписи RU/EN | P3, web, bug             |
| 17  | Детекция: ложные срабатывания и «не-животное» — стратегия (two_stage / single_stage+COCO, пороги, веса) | Консилиум: [§ ниже](#detection-strategy-consilium) · связь с [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) | P2, processor, ML        |


### Консилиум: стратегия детекции {#detection-strategy-consilium}

**Задача:** собрать консилиум (продукт/оператор, ML, платформа) и зафиксировать решение, как на проде снижать **ложные срабатывания** и детекции **неодушевлённых объектов**. По договорённости — **после** закрытия текущей волны разработки и ручной приёмки базового сценария; см. [§ «Завершение задач → тестирование оператором»](#completion-then-operator-testing).

**Контекст:** при `detection_strategy: two_stage` и настройках в `user_config.yaml` поведение **не** совпадает с режимом **single_stage** + типичный COCO, где по умолчанию включён авто-фильтр **только животные** (`processor.single_stage_coco_animals_only_auto` — без person и без «вещей»). Деплой кода не подменяет `user_config.yaml`.

**Варианты для сравнения (не исключая комбинации):**

- оставить **two_stage** и подкрутить **`min_confidence_binary`** / **`min_confidence_to_process`**, при необходимости дообучить или заменить бинарный детектор;
- перейти на **single_stage** + COCO (или иная detect-модель) и опереться на фильтр животных / свои классы;
- учесть сценарии с Frigate / дополнительными триггерами.

Документация по ключам: [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) (processor, motion). Расширение классов «не только птицы» пересекается с [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) — на консилиуме решить, ведём ли одну эпик-задачу или выделяем дочерние issues.

**Не забыть (чеклист — чтобы не потерять контекст):**

| Шаг | Что сделать |
|-----|-------------|
| 1 | Зафиксировать **как сейчас на хабе** фрагмент `processor` из `user_config.yaml`: `detection_strategy`, пути `models.binary` / `models.classifier` / `models.single_stage`, `min_confidence_binary`, `min_confidence_to_process`, `single_stage_coco_animals_only_auto`. |
| 2 | Кратко описать **симптомы**: что именно даёт ложные срабатывания / «не-животное» (кадр, время суток, погода — по возможности). |
| 3 | На консилиуме выбрать ветку (two_stage + пороги/модель **или** single_stage + COCO/своя модель **или** гибрид с Frigate и т.д.) и **записать решение** в Issue (один эпик или несколько дочерних). |
| 4 | После решения: обновить **этот ROADMAP** (строка 17 — итог или ссылка на закрытый issue), при смене ключей — **CONFIGURATION** / примеры; на сервере **вручную** поправить `user_config.yaml` при необходимости (**деплой его не перезаписывает**). |
| 5 | Не смешивать с [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) без явного решения: либо одна линия работы, либо отдельные issues со ссылками друг на друга. |


### Триаж: Issue или Discussion


| Куда                                                                     | Когда                                                                                          |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| **[Issue](https://github.com/Gfermoto/BirdLense-Hub/issues)**            | Понятный объём, критерий готовности, метки `area:`* и приоритет — можно класть на **Project**. |
| **[Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions)** | Идея на проработку, несколько вариантов, «делать или нет», сбор мнений до задачи.              |


**После консилиума:** новая отслеживаемая работа → Issue, карточка на доске (`github-project-add-backlog-consilium.sh` или вручную), затем **обновить эту таблицу** в ROADMAP в том же или следующем PR.

**Отчётность (вся работа, не только консилиум):** каждая сданная задача — **Issue** (нет карточки — завести) и при необходимости карточка на доске **BirdLense Hub — Roadmap**. По готовности: комментарий (итог + ссылки на PR), **закрыть** Issue, на доске **Status → Done** (при PAT: `bash scripts/github-project-mark-done.sh <номер>`). Для регулярной уборки рассинхрона использовать `bash scripts/github-project-sync.sh --assign Gfermoto` (выравнивает статус/поток по issue-state, назначает исполнителя на open без assignee, репортит задачи без подзадач). Подробности и чеклист — корневой **[CONTRIBUTING.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.ru.md)** § *Issues и доска Project*.

---

## Кандидаты на будущее (issues заведены)

Темы уже оформлены в отдельные **Issues** и добавлены на доску; приоритизируются по слотам:


| Тема                                       | Зачем                                                                                                                                                                                               |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Доступность (a11y)**                     | [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117) ✅ baseline **v0.2.9**: skip link, фокус, контраст, axe E2E, [A11Y.ru.md](./A11Y.ru.md); дальнейшие улучшения — по новым issues.        |
| **Расширение E2E (Playwright)**            | [#118](https://github.com/Gfermoto/BirdLense-Hub/issues/118): не только смоук — логин, таймлайн, критичные настройки, коррекция видов.                                                              |
| **Секреты в проде**                        | [#119](https://github.com/Gfermoto/BirdLense-Hub/issues/119) ✅: runbook [SECRETS_ROTATION.ru.md](./SECRETS_ROTATION.ru.md) (дополняет [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47)). |
| **Синхронизация версий стека**             | [#120](https://github.com/Gfermoto/BirdLense-Hub/issues/120) ✅: чеклист и `python3 scripts/check-docs-version.py` — см. [VERSIONING.ru.md](./VERSIONING.ru.md).                                                               |
| **Community / донаты в UI**                | [#121](https://github.com/Gfermoto/BirdLense-Hub/issues/121) ✅ MVP: `general.donate_url` — ссылки в шапке, мобильном и меню шестерёнки + карточка «Корм»; см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md). Метрики кликов — вне объёма.                       |
| **Интерактивный life list (планирование)** | [#125](https://github.com/Gfermoto/BirdLense-Hub/issues/125): ручные отметки «видел сам», заметки — отдельно от таблицы миграции; сейчас только беклог и планы в issue, без кода.                   |
| **Системная база видов (канонизация)**     | [#168](https://github.com/Gfermoto/BirdLense-Hub/issues/168): ✅ реализовано — единый реестр видов, нормализация по ID, backfill, фоновые metadata jobs и CI smoke quality-gate для всей базы.       |


### Пожелания пользователей (backlog, маркет 2026)

Отдельные issues для планирования; детали и критерии — в каждом issue.

**Подготовка перед реализацией ([#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131), [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139)):** [чеклист](./PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md).

**Прогресс (март 2026):**

- [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117) — baseline a11y и **v0.2.9** (PR [#187](https://github.com/Gfermoto/BirdLense-Hub/pull/187), release [#188](https://github.com/Gfermoto/BirdLense-Hub/pull/188)); см. [A11Y.ru.md](./A11Y.ru.md).
- [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139) — реализовано и закрыто: убран пункт «Неизвестные», legacy-редирект `/unknowns` → `/timeline?review=1`, режим «На проверке» на Timeline (чип + счётчик), обновлены OpenAPI + API тесты + smoke редиректа.
- [#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131) — реализовано и закрыто: пункт «Каталог» убран из меню, legacy `/species` редиректит на `/migration-calendar`, deep-link `/species/:id` сохранён.
- [#127](https://github.com/Gfermoto/BirdLense-Hub/issues/127) — реализовано и закрыто: блок «Сравнение с регионом» перенесён с Overview на Migration; оставшаяся ссылка-переход с Overview удалена.
- [#130](https://github.com/Gfermoto/BirdLense-Hub/issues/130) — реализовано и закрыто: диаграмма распределения видов на Overview (сектор и легенда) ведёт в Timeline с фильтрами вида и даты.
- [#133](https://github.com/Gfermoto/BirdLense-Hub/issues/133) — реализовано и закрыто: добавлен фильтр периода по датам (день-точность) для Migration; применяется к таблице, но не к региональному справочнику.
- [#129](https://github.com/Gfermoto/BirdLense-Hub/issues/129), [#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153), [#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157) — реализовано и закрыто: BirdNET MQTT bias, multi-camera boost, post-roll записи; см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) → Processor.

**Новые идеи (март 2026) — структурированы в issues и добавлены на доску Project:**


| #   | Тема                                                                                                                                     | Issue                                                        | Приоритет / зона                                             |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 1   | System: счётчик уникальных посетителей                                                                                                   | [#151](https://github.com/Gfermoto/BirdLense-Hub/issues/151) ✅ | P3, web                                                      |
| 2   | После удаления записи возвращать в список, а не на Home                                                                                  | [#152](https://github.com/Gfermoto/BirdLense-Hub/issues/152) ✅ | P2, web, bug                                                 |
| 3   | Multi-camera confidence для камер одной локации                                                                                          | [#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153) ✅ `multi_camera_groups` + boost после merge; [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) | P2, processor                                                |
| 4   | «Суточный паттерн»: клик должен фильтровать по часу                                                                                      | [#154](https://github.com/Gfermoto/BirdLense-Hub/issues/154) ✅ | P2, web, bug                                                 |
| 5   | Несоответствие длительности записи (Home vs страница записи)                                                                             | [#155](https://github.com/Gfermoto/BirdLense-Hub/issues/155) ✅ | P2, web, bug                                                 |
| 6   | Счётчик «на проверке» не обновляется без F5                                                                                              | [#156](https://github.com/Gfermoto/BirdLense-Hub/issues/156) ✅ | P2, web, bug                                                 |
| 7   | Recording quality: pre-roll/post-roll, чтобы не терять прилёты/отлёты                                                                    | [#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157) ✅ `processor.post_record_seconds` (хвост записи); pre-roll по-прежнему `video.pre_record_seconds` (Go2RTC — см. issue) | P2, processor                                                |
| 8   | Реэкспорт: осиротевшие распознавания без вида и без записи                                                                               | [#158](https://github.com/Gfermoto/BirdLense-Hub/issues/158) ✅ | P1, processor, bug                                           |
| 9   | UX consistency: tooltips и встроенные пояснения                                                                                          | [#159](https://github.com/Gfermoto/BirdLense-Hub/issues/159) ✅ | P3, web                                                      |
| 10  | Regenerate tracks: прогресс, 409 и timeout на больших объёмах                                                                            | [#160](https://github.com/Gfermoto/BirdLense-Hub/issues/160) ✅ | P1, web, bug                                                 |
| 11  | Dataset UX: понятный сценарий в Library (обслуживание БД и получение датасета)                                                           | [#161](https://github.com/Gfermoto/BirdLense-Hub/issues/161) ✅ | P2, docs + web                                               |
| 12  | Dataset pipeline: уменьшить необходимость пост-скрипта перед обучением                                                                   | [#162](https://github.com/Gfermoto/BirdLense-Hub/issues/162) ✅ | P2, processor                                                |
| 13  | Detector: добавить классы не-птиц (мыши, белки, кошки)                                                                                   | [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) · см. консилиум [п.17](#detection-strategy-consilium) | P3, processor, research                                      |
| 14  | Classifier strategy: transfer learning (US + локальный датасет)                                                                          | [#164](https://github.com/Gfermoto/BirdLense-Hub/issues/164) | P2, processor, research                                      |
| 15  | Telegram: SOCKS5h proxy в UI и MTProto (`telebot.apihelper.proxy`)                                                                      | [#165](https://github.com/Gfermoto/BirdLense-Hub/issues/165) | P3, web                                                      |
| 16  | Интеграция с Heimdall                                                                                                                    | [#166](https://github.com/Gfermoto/BirdLense-Hub/issues/166) | P3, infra                                                    |
| 17  | Дальний backlog: весы корма/птиц (auto-tare + object detection)                                                                          | [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167) | P3, processor, research                                      |


**Системная инициатива (приоритет P1):**

- [#168](https://github.com/Gfermoto/BirdLense-Hub/issues/168) — эпик «Species Canonical Registry»: не точечные заплатки по отдельным видам, а надёжный контур для всей базы (канонический реестр, универсальный резолвер имён, миграция истории, metadata enrichment, CI-инварианты).
- Фазы эпика закрыты:
  - [#169](https://github.com/Gfermoto/BirdLense-Hub/issues/169) — SSOT-реестр видов (canonical registry) ✅
  - [#170](https://github.com/Gfermoto/BirdLense-Hub/issues/170) — универсальный resolver имён для всех входов ✅
  - [#171](https://github.com/Gfermoto/BirdLense-Hub/issues/171) — backfill + repair целостности исторических данных ✅
  - [#172](https://github.com/Gfermoto/BirdLense-Hub/issues/172) — фоновые metadata jobs (image/description) ✅
  - [#173](https://github.com/Gfermoto/BirdLense-Hub/issues/173) — наблюдаемость и CI quality-gate ✅
- Финальный результат (март 2026): в проде `processed=806`, `matched=806`, `unresolved=0` при старте; добавлены API `seed/backfill/unresolved/health/enrich`, async enrichment status и CI smoke-тест реестра.


| #                                                            | Issue                             | Кратко                                                                                     |
| ------------------------------------------------------------ | --------------------------------- | ------------------------------------------------------------------------------------------ |
| [#127](https://github.com/Gfermoto/BirdLense-Hub/issues/127) | Топ региона + «кто из них у меня» | ✅ блок «Сравнение с регионом» на Migration (см. прогресс выше)                               |
| [#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128) | Авто-пороги для топа региона      | ✅ merge в процессоре + настройки; дельта/пол от `min_confidence_to_process`; ручные overrides важнее; [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) |
| [#129](https://github.com/Gfermoto/BirdLense-Hub/issues/129) | Пороги + MQTT BirdNET             | ✅ Снижение порога классификатора для видов из недавних MQTT BirdNET: `birdnet_mqtt_auto_confidence` и параметры окна/дельты; [CONFIGURATION.ru.md](./CONFIGURATION.ru.md)                    |
| [#132](https://github.com/Gfermoto/BirdLense-Hub/issues/132) | Фильтры видов                     | ✅ каталог: «Региональные» = топ eBird + детекции `birdnet_mqtt`; поле `regional_scope` в `GET /species`; [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) |
| [#134](https://github.com/Gfermoto/BirdLense-Hub/issues/134) | Корм для Европы                   | ✅ расширен `seed.py` + идемпотентное слияние по имени; см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) → «Корм» |
| [#136](https://github.com/Gfermoto/BirdLense-Hub/issues/136) | eBird `species_mapping`           | ✅ API `GET /api/ui/settings/ebird-species-mapping-suggestions`, кнопка в настройках, общий кэш топа eBird; [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) |


---

## Отгруженные идеи (архив)

Исторический чеклист **от простого к сложному** (все строки — ✅). Сверяйтесь с [FEATURES](./FEATURES.ru.md); **не** воспринимать таблицу как backlog задач.


| Фича                                     | Описание                                                                                                              | Сложность | Риск    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------- | ------- |
| ✅ Playback speed (0.5x, 2x)              | Кнопки в видеоплеере для замедления/ускорения просмотра                                                               | Низкая    | Нет     |
| ✅ Webhook (POST при детекции)            | POST на настраиваемый URL с JSON (вид, confidence, время) — для IFTTT, Zapier                                         | Низкая    | Нет     |
| ✅ CSV/JSON экспорт статистики            | Скачать визиты, виды, детекции для анализа в Excel/Python                                                             | Низкая    | Нет     |
| ✅ Виджет «Последняя птица» на Overview   | Блок «Сегодня в 14:32 — Eurasian Jay» на главной                                                                      | Низкая    | Нет     |
| ✅ Фильтр по времени суток в Timeline     | «Только утро (6–10)», «только вечер» — сузить список визитов                                                          | Низкая    | Нет     |
| ✅ PWA improvements                       | Install prompt «Добавить на главный экран», offline cache для статики                                                 | Низкая    | Нет     |
| ✅ «Неизвестные» (низкий confidence)      | Отдельный список детекций с confidence < порога для ручной проверки и разметки                                        | Средняя   | Нет     |
| ✅ PDF-отчёт                              | Месячный отчёт: N видов, топ-5, графики — скачать PDF. v0.1.8: брендинг, шапка/футер                                  | Средняя   | Нет     |
| ✅ Bird song player (Xeno-canto)          | Кнопка «Воспроизвести песню» на карточке вида — аудио из Xeno-canto API                                               | Средняя   | Нет     |
| ✅ eBird export                           | Экспорт списка видов в формат eBird для загрузки в приложение                                                         | Средняя   | Нет     |
| ✅ Grafana/Prometheus метрики             | `/metrics`, `/api/metrics` — CPU, память, диск, GPU, detections, species, videos                                      | Средняя   | Нет     |
| ✅ Confidence по виду                     | Разные пороги min_confidence для разных видов (редкие — ниже)                                                         | Средняя   | Низкий  |
| ✅ Экспорт в iNaturalist                  | Кнопка «Отправить в iNaturalist» — crop + вид для citizen science                                                     | Средняя   | Нет     |
| ✅ Web Push                               | Push-уведомления в браузере вместо/дополнение Telegram                                                                | Средняя   | Низкий  |
| ✅ Публичная галерея                      | Opt-in: загрузка лучших кадров на настраиваемый URL. См. [CONFIGURATION](./CONFIGURATION.ru.md) — Gallery             | Высокая   | Средний |
| ✅ Календарь миграций                     | «Вид X обычно появляется в марте» — по историческим данным                                                            | Высокая   | Нет     |
| ✅ Сравнение с регионом                   | Карточка на Overview: ваши виды в топе региона + полный топ региона (eBird API)                                       | Высокая   | Средний |
| ✅ Закат и рассвет на карточке погоды     | Восход, закат, рассвет, сумерки, полдень — дуга солнца (в стиле Horizon Card) на выбранную дату в локации из настроек | Низкая    | Нет     |
| ✅ Видео: предыдущий/следующий (день UTC) | Страница видео + `GET /api/ui/videos/:id/neighbors` ([#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82))      | Низкая    | Нет     |


**Новые идеи:** [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions) или Issue по таблице триажа выше.

### UX-улучшения (отгружено)


| Улучшение                                  | Статус   |
| ------------------------------------------ | -------- |
| Календарь активности (MonthPicker)         | ✅ v0.1.8 |
| Неизвестные — пустое состояние (подсказка) | ✅        |
| Неизвестные — время суток (как в Timeline) | ✅ v0.1.9 |


---

## Порядок работ: завершение задач → тестирование оператором {#completion-then-operator-testing}

**Договорённость:** сначала **доводим до конца** согласованный объём работ (открытые issues текущей волны / milestone на доске **BirdLense Hub — Roadmap**: PR смержен, issue **закрыт**, при необходимости **`make deploy`**, CI зелёный). **Затем** оператор ведёт **ручное тестирование** на живой установке и передаёт **замечания отдельными новыми issues** (или указывает регрессию в существующем issue) — без параллельного наращивания «хвостов» в той же волне.

**Не путать с бэклогом:** строки в таблице «Новые идеи» без ✅ — это **очередь на будущее**; в объём «до приёмки» входит только то, что **явно взято в работу** на доске. **Консилиум по детекции** ([п.17](#detection-strategy-consilium)) — после стабилизации текущей волны, если отдельно не решено иначе.

---

## Приоритеты на ближайшее время (публично)

### Фокус №1: закрыть мелкие баги и хвосты (до полировки)

Перед любыми задачами по "полировке" UI/UX закрываем накопившийся operational backlog.
Цель этапа: снизить шум, убрать регрессии и стабилизировать ежедневный сценарий работы.

**Порядок работы (без распыления):**

1. **Сначала баги P1/P2**, потом удобства и косметика.
2. Закрываем задачи **волнами** по 3-5 issue, каждая волна завершается тестами и деплоем.
3. Для каждой закрытой задачи: PR, комментарий в issue, перевод карточки в Done.

**Волна A (критичные баги, first):**
- [x] [#158](https://github.com/Gfermoto/BirdLense-Hub/issues/158) — реэкспорт: сироты попадают в выборку при фильтре дат; retention каскадно чистит детекции/визиты; тест `test_retro_export_deletes_orphan_with_date_filter`.
- [x] [#160](https://github.com/Gfermoto/BirdLense-Hub/issues/160) — poll regenerate spectrograms/tracks: `JOB_STATUS_POLL_TIMEOUT_MS` (120s); 409 → attach к job.
- [x] [#152](https://github.com/Gfermoto/BirdLense-Hub/issues/152) — после удаления записи: `state.from` или `/library`; `state` с Timeline/Unknowns и при листании соседей.

**Волна B (P2 баги UX-логики):**
- [x] [#154](https://github.com/Gfermoto/BirdLense-Hub/issues/154) — фильтр по часу из "суточного паттерна".
- [x] [#155](https://github.com/Gfermoto/BirdLense-Hub/issues/155) — рассинхрон длительности записи (Home vs детали).
- [x] [#156](https://github.com/Gfermoto/BirdLense-Hub/issues/156) — счётчик "на проверке" без F5.
- Статус: **закрыто** (issue закрыты, карточки на доске переведены в Done, деплой выполнен).

**Волна C (мелкие задачи и техдолг перед полировкой):**
- [x] [#151](https://github.com/Gfermoto/BirdLense-Hub/issues/151) — счётчик уникальных посетителей.
- [x] [#159](https://github.com/Gfermoto/BirdLense-Hub/issues/159) — consistency tooltips/встроенных пояснений.
- [x] [#161](https://github.com/Gfermoto/BirdLense-Hub/issues/161) — понятный сценарий dataset в Library.
- [x] [#162](https://github.com/Gfermoto/BirdLense-Hub/issues/162) — уменьшить пост-скрипты перед обучением.

**Критерий выхода из этапа "мелкие баги/хвосты":**
- Все issue из волн A+B закрыты (#152/#158/#160 — PR [#176](https://github.com/Gfermoto/BirdLense-Hub/pull/176)).
- По волне C закрыты минимум 2 задачи с максимальной пользовательской ценностью.
- `app/web/tests` зелёные, smoke после деплоя зелёный.

### Фокус №2: подготовка к дообучению (после bug-burndown)

После закрытия волн A+B переходим к "Dataset Readiness":
- канонический экспорт train/val/test + манифест версии датасета;
- quality-gates (дубликаты, leakage, пустые классы, min per class);
- воспроизводимость (паспорт датасета и фиксированные фильтры);
- CI smoke на сборку и валидацию выгрузки.

**Срез 1 ✅:** экспорт Hub — `dataset_info.json` v2 (`manifest` + `quality`), опциональный `test` split, параметр `strict_quality`; см. [DATASETS.ru.md](./DATASETS.ru.md). Влито в `dev`, PR в `main`: [#174](https://github.com/Gfermoto/BirdLense-Hub/pull/174).

**Срез 2 ✅:** `strict_quality` дополняется отказом выгрузки, если класс отброшен из‑за `min_images_per_class` (без скрытого «недонабора» ярлыков); чекбокс в Library при «готово к train». PR [#175](https://github.com/Gfermoto/BirdLense-Hub/pull/175).

**Фокус №2 (итог по плану):** train/val/test + манифест v2 + quality/leakage/strict + fingerprint + CI smokes + срез 2 — **закрыто в коде**; дальнейшее — только по новым issues.


| Приоритет        | Фокус                                                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Сообщество**   | [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions), метка `good first issue`, обратная связь по докам |
| **Качество**     | CI на PR (сборка UI + MkDocs `--strict`), Dependabot / зависимости                                                      |
| **Документация** | Баннер версии в `mkdocs.yml` = `VERSION`; интерактивный OpenAPI (Redoc) на сайте                                        |
| **Релизы**       | Теги + GitHub Release → semver-образ Docker + деплой Pages                                                              |


Таблица **архива** выше — только история. Активная работа — issues **консилиума** и блок **кандидатов**; сверяйтесь с [FEATURES](./FEATURES.ru.md).

---

См. также: [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md), [DATASETS](./DATASETS.ru.md), [TESTING](./TESTING.ru.md), [CONFIGURATION](./CONFIGURATION.ru.md).
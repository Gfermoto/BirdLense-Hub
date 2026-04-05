# Консилиум: аудит (RU, архив заметок)

Дата: `2026-03-30`. Не дублирует актуальный [ROADMAP.ru.md](./ROADMAP.ru.md) — это снимок обсуждения для истории.

*Уточнение путей (2026-04): закрыт [#198](https://github.com/Gfermoto/BirdLense-Hub/issues/198) — публичные маршруты вида разнесены по `ui_*_routes`; ниже для summary указан актуальный файл.*

## Большой консилиум BirdLense Hub

Этот документ фиксирует findings-first аудит BirdLense Hub по направлениям:
- доверие к `species` данным и карточкам видов;
- startup side-effects и self-healing логика;
- доверие к processor pipeline;
- web/ui, CI/E2E и deploy reliability.

## Executive Summary
Утрата доверия к системе вызвана не одним багом, а комбинацией архитектурных проблем:

1. В каталог видов может попадать недостоверная семантика.
Причина: цепочка `raw label -> Species -> external enrichment` допускает запись нерелевантных изображений и описаний без жесткой валидации таксона.

2. Приложение делает слишком много изменяющих действий на старте.
Причина: `create_app()` не только поднимает веб, но и мутирует БД, запускает cleanup/repair и может инициировать внешние сетевые операции.

3. Processor pipeline допускает правдоподобные, но неверные результаты.
Причина: слабые quality gates, опасные merge-эвристики, режимы детекции с не-птичьими классами и confidence logic, ориентированная на прохождение, а не на доказуемость.

4. Пользовательские регрессии слишком легко доходят до прода.
Причина: PR-защита сосредоточена на build и части API-тестов, но не на обязательных browser-level сценариях критичных страниц.

Ниже findings упорядочены по severity, затем приведены стартовые операции с verdict, матрица user-facing маршрутов и волны ремонта.

## Critical Findings

### C1. Недостоверные species-карточки являются системным дефектом data pipeline
Симптомы уровня заказчика:
- в карточках видов появляются `миска`, `нож`, `цветок`, `женщина`, `туалет`, `Unknown`;
- внешне карточка выглядит заполненной, но семантически не соответствует птице.

Корневая причина:
- `Species` может создаваться из сырого имени, которое не прошло строгий canonical resolve;
- затем enrichment в [app/web/util.py](/home/gfer/BirdLense/app/web/util.py) подбирает внешние данные по строковому поиску в Wikipedia/iNaturalist;
- при отсутствии жесткой taxon-level валидации система принимает «похожий» внешний результат как истину.

Основные точки риска:
- [app/web/services/visit_processor.py](/home/gfer/BirdLense/app/web/services/visit_processor.py)
- [app/web/services/species_registry_service.py](/home/gfer/BirdLense/app/web/services/species_registry_service.py)
- [app/web/util.py](/home/gfer/BirdLense/app/web/util.py)
- [ui_species_media_routes.py](../app/web/routes/ui_species_media_routes.py) (карточка вида / summary / медиа); оркестратор [ui_routes.py](../app/web/routes/ui_routes.py)

Почему это критично:
- каталог видов становится недостоверным даже без падения API;
- заказчик видит уверенно оформленную, но ложную карточку;
- ошибка выглядит не как «баг отображения», а как подмена фактов.

### C2. `create_app()` выполняет опасные data mutations и recovery-операции
Корневая причина:
- в [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) старт веба совмещен с `seed`, registry backfill, cleanup, background repair и опциональным enrich.

Почему это критично:
- рестарт приложения меняет данные;
- отладка инцидентов становится нетривиальной: невозможно быстро ответить, «что изменил последний рестарт»;
- любое ошибочное условие cleanup/repair становится destructive path на каждом запуске.

### C3. Processor pipeline не доказывает корректность видов до записи в БД
Корневая причина:
- в [app/processor/src/detection_strategy.py](/home/gfer/BirdLense/app/processor/src/detection_strategy.py), [app/processor/src/species_normalizer.py](/home/gfer/BirdLense/app/processor/src/species_normalizer.py), [app/processor/src/decision_maker.py](/home/gfer/BirdLense/app/processor/src/decision_maker.py) используются эвристики, которые делают результат правдоподобным, но не обязательно истинным.

Ключевые риски:
- single-stage COCO может пропускать не только птиц;
- MQTT merge может усиливать или подменять вид по временным/приоритетным эвристикам;
- confidence и voting легко дают «достаточно хороший» ответ без реального semantic gate.

Почему это критично:
- downstream web уже работает с данными как с фактом;
- ложная species assignment дальше загрязняет каталог, визиты, summary и датасеты.

## High Findings

### H1. Read-path `/species/:id/summary` имеет write side-effect
В [ui_species_media_routes.py](../app/web/routes/ui_species_media_routes.py) эндпоинт summary может инициировать enrichment и `commit`.

Риск:
- обычное открытие карточки способно менять БД;
- поведение страницы зависит от состояния кэша и внешних источников;
- read API перестает быть безопасным и воспроизводимым.

### H2. В системе нет единого источника истины для species mapping
Сейчас сосуществуют:
- processor-side mapping;
- registry aliases;
- seeded hierarchy;
- live-created `Species` rows;
- manual/override logic в enrichment.

Риск:
- дубликаты видов;
- разные имена для одного таксона;
- несогласованность между processor и web.

### H3. Startup notifications и startup repair остаются частью критического пути
В [app/web/notifications.py](/home/gfer/BirdLense/app/web/notifications.py) и [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) старт всё еще содержит внешние или фоновые side-effects.

Риск:
- непредсказуемый cold start;
- усложненная эксплуатация;
- ложное ощущение «self-healing», когда система фактически скрывает корневой дефект.

### H4. E2E не является обязательным gate перед поставкой
См.:
- [.github/workflows/e2e-scheduled.yml](/home/gfer/BirdLense/.github/workflows/e2e-scheduled.yml)
- [.github/workflows/ci-pr.yml](/home/gfer/BirdLense/.github/workflows/ci-pr.yml)
- [.github/workflows/deploy.yml](/home/gfer/BirdLense/.github/workflows/deploy.yml)

Риск:
- браузерные регрессии могут проходить PR и проявляться только после деплоя;
- критичные страницы не имеют гарантированного smoke на каждый merge.

## Medium Findings

### M1. Startup cleanup и repair операции недостаточно отделены от migrations
Даже если каждая отдельная операция задумывалась как safe-repeat, их совместное выполнение внутри `create_app()` затрудняет reasoning и аудит.

### M2. Контрактные и API-тесты не покрывают весь user-facing surface
Особенно недозащищены:
- video details;
- timeline при грязных данных;
- migration в реальных UI ветках;
- species summary/data-quality paths.

### M3. Система использует `metadata_status`, но не имеет trust model
Нужны отдельные понятия:
- `verified`;
- `best_effort`;
- `suspect`;
- `quarantined`;
- `operator_confirmed`.

Без этого поле `ok` означает только «что-то найдено», а не «данным можно доверять».

### M4. Некоторые merge/repair flows плохо наблюдаемы
Нехватает:
- отдельных audit logs;
- операционных счетчиков;
- dry-run/report режима;
- явного operator acknowledgement для risk-bearing jobs.

## Наблюдения по конкретным пользовательским примерам

Примеры:
- `species/816` — миска
- `species/815` — нож
- `species/447` — цветок вместо жаворонка
- `species/745` — неизвестный
- `species/48` — рыжая женщина

Это не пять несвязанных инцидентов, а минимум четыре класса дефектов:

1. `Raw label contamination`
   в БД попадает имя, которое не прошло строгий canonical gate.

2. `Wrong external enrichment`
   строка резолвится во внешний объект, который не соответствует птице.

3. `Hierarchy/alias drift`
   один и тот же логический вид может жить в нескольких row/alias формах.

4. `Unknown and bucket leakage`
   служебные или umbrella entries ведут себя как обычные species cards.

## Verdict по startup операциям

| Операция | Файл | Verdict |
|---|---|---|
| `db.create_all()` и schema-safe `ALTER` | [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) | `allowed` |
| `seed()` и базовая иерархия | [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) | `allowed` |
| `ensure_species_registry_seeded()` | [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) | `gated` |
| `backfill_species_taxa(dry_run=False)` | [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) | `forbidden on startup` |
| `_cleanup_legacy_import_placeholders()` | [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) | `gated` |
| `repair_recently_reset_species_metadata()` thread | [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) | `forbidden on startup` |
| `SPECIES_METADATA_ENRICH_ON_START` thread | [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) | `forbidden on startup` |
| `notify_app_startup()` | [app/web/app.py](/home/gfer/BirdLense/app/web/app.py) | `gated` |
| system metrics sampler | [app/web/routes/ui_system_routes.py](/home/gfer/BirdLense/app/web/routes/ui_system_routes.py) | `allowed` |

Правило:
- старт приложения должен поднимать веб;
- heavy maintenance jobs должны запускаться явно;
- destructive или external side-effects на старте должны быть opt-in, а не default.

## Critical Routes vs Protection

| Маршрут / сценарий | Текущая защита | Gap |
|---|---|---|
| species catalog / species summary | частичный pytest, нет trust validation | нет semantic/data-quality gates |
| video details | частичный backend pytest | нет обязательного PR browser smoke |
| timeline | backend tests есть, browser protection слабая | нет обязательного smoke после deploy |
| migration | часть pytest + условный E2E | E2E может skip при бедной БД |
| unknowns | backend tests есть | слабая защита от деградации UI/slow paths |
| startup / deploy | health check | health не доказывает корректность пользовательских сценариев |

## Главные корневые причины

### 1. Смешение read, write и repair обязанностей
Один и тот же runtime-path:
- обслуживает пользователя;
- лечит данные;
- обогащает metadata;
- меняет registry state.

### 2. Best-effort эвристики там, где нужна доказуемость
Система старается «заполнить карточку» вместо того, чтобы честно признать `unverified`.

### 3. Неединый canonical pipeline
Processor, web registry, aliases, hierarchy и enrichment не образуют один жесткий contract.

### 4. Слабая PR-level защита браузерных и data-quality инцидентов
API и build страхуются лучше, чем реальный UX и доверие к данным.

## Волны ремонта

### Wave A: Containment
Цель: остановить дальнейшее загрязнение и неожиданную мутацию данных.

Шаги:
- запретить dangerous startup jobs по умолчанию;
- убрать write-side-effects из read API;
- ввести quarantine для suspect species metadata;
- добавить быстрый PR smoke на критичные маршруты.

### Wave B: Data Trust Restoration
Цель: восстановить доверие к каталогу видов.

Шаги:
- ввести trust model для `Species` metadata;
- построить bulk audit существующих species rows;
- отделить verified vs best-effort vs quarantined metadata;
- добавить operator workflow для сомнительных карточек.

### Wave C: Processor Trust and Quality Gates
Цель: перестать писать в web/db неподтвержденные «факты».

Шаги:
- ужесточить bird-only guarantees;
- пересмотреть merge с MQTT и `Bird` handoff;
- улучшить confidence/voting semantics;
- добавить pre-write semantic gates.

### Wave D: CI / E2E Hardening
Цель: чтобы тяжелые user-facing регрессии не доезжали до прода.

Шаги:
- сделать узкий E2E обязательным на PR;
- добавить `eslint`/UI checks в CI;
- расширить OpenAPI/API smoke для critical endpoints;
- добавить post-deploy smoke кроме `/health`.

### Wave E: Architectural Cleanup
Цель: снизить сложность и сделать систему предсказуемой.

Шаги:
- декомпозировать processor и startup logic;
- развести maintenance jobs и request-serving code;
- сделать maintenance flows наблюдаемыми, dry-run friendly и идемпотентными.

## Рекомендуемый порядок исполнения

```mermaid
flowchart TD
  containment[WaveAContainment] --> dataTrust[WaveBDataTrust]
  containment --> ciHardening[WaveDCIHardening]
  dataTrust --> processorTrust[WaveCProcessorTrust]
  ciHardening --> processorTrust
  processorTrust --> architecture[WaveEArchitecture]
```

## Минимальные immediate actions

1. Заморозить все необязательные startup repair/enrich paths.
2. Убрать запись в БД из `/species/:id/summary`.
3. Ввести `suspect/quarantined` статус для species cards.
4. Обязать PR-level browser smoke хотя бы для `species`, `video`, `timeline`, `migration`.
5. Подготовить разовый bulk report по уже загрязненным species rows.

## Вывод
BirdLense сейчас страдает не от отсутствия логики, а от избытка неразделённых эвристик и self-healing поведения в чувствительных местах. Система слишком охотно превращает «похоже» в «истину» и слишком легко мутирует данные в runtime. Главный приоритет — сначала вернуть доказуемость и предсказуемость, а уже затем продолжать feature work.

# SOTA Execution Roadmap (2026 H2)

Связанные документы:
- `docs/strategy/SOTA_ALL_WAVES_MASTER_PLAN_2026.md`
- `docs/reports/sota_issue_backlog_2026-05.md`
- GitHub Project: <https://github.com/users/Gfermoto/projects/2>
- SOTA issue filter: <https://github.com/Gfermoto/BirdLense-Hub/issues?q=is%3Aissue+is%3Aopen+label%3Aprogram%3Asota>
- Acceptance epic: <https://github.com/Gfermoto/BirdLense-Hub/issues/517>
- Active P0 blockers: <https://github.com/Gfermoto/BirdLense-Hub/issues/555>, <https://github.com/Gfermoto/BirdLense-Hub/issues/556>, <https://github.com/Gfermoto/BirdLense-Hub/issues/557>

## Таймлайн

| Фаза | Период | Основная цель | Обязательные issue |
|------|--------|---------------|--------------------|
| A | День 0-30 | Контроль рисков и измеримость | SOTA-0-01, SOTA-0-02, SOTA-1-01, SOTA-1-02, SOTA-2-01, SOTA-2-02, SOTA-5-01, SOTA-8-01, SOTA-8-02 |
| B | День 31-60 | Упрочнение runtime и ML-контуров | SOTA-1-03, SOTA-2-03, SOTA-2-04, SOTA-2-05, SOTA-3-01, SOTA-3-02, SOTA-5-02, SOTA-6-01 |
| C | День 61-90 | Масштабирование качества и снижение энтропии | SOTA-3-03, SOTA-4-01, SOTA-4-02, SOTA-4-03, SOTA-6-02, SOTA-7-01, SOTA-7-02, SOTA-5-03 |
| D | День 91-120 | Стабильное governance-управление | SOTA-9-01, SOTA-9-02 + re-eval всех P0/P1 |

## Критический путь

1. `SOTA-0-02` (error budget gate)  
2. `SOTA-2-02` (golden set gate)  
3. `SOTA-5-01` (DORA metrics)  
4. `SOTA-8-01` + `SOTA-8-02` (security control plane)  
5. `SOTA-5-02` (deploy rollback contract)

Если любой элемент критического пути не завершён, переход к следующей фазе блокируется.

## Политика приоритетов

- Внутри каждой фазы задачи на стабилизацию, багфиксы и hardening выполняются раньше feature-инициатив.
- Feature-задачи не должны увеличивать риск по P0/P1 в reliability/security/ML.
- Любая новая функциональность требует подтверждения, что текущие quality/security gates остаются зелёными.

## KPI по фазам

### Фаза A
- Error budget policy активна в CI/CD.
- Golden set gate включён и блокирует деградации.
- Базовые security-control матрицы введены.

### Фаза B
- Drift detection + retrain trigger в рабочем контуре.
- UI/API contract gate стабилен, anti-flake policy активна.
- Rollback path доказан на тестовом сценарии.

### Фаза C
- Документация переведена на Diataxis-подход в целевых разделах.
- Интеграции имеют формализованные контракты и smoke checks.
- Tooling backlog сокращён и имеет owners.

### Фаза D
- Review board работает циклично.
- Policy-as-code управляет релизными исключениями.
- Удержание KPI по reliability/security/ML в течение минимум одного релизного цикла.

## Ритм исполнения

- Еженедельно: checkpoint по всем open P0.
- Раз в 2 недели: пересмотр рисков и приоритетов P1/P2.
- Ежемесячно: board-review с переоценкой SOTA KPI.

## Операционные board-фильтры

- P0 стабилизация: <https://github.com/Gfermoto/BirdLense-Hub/issues?q=is%3Aopen+is%3Aissue+label%3Aprogram%3Asota+label%3Apriority%3AP0>
- Фаза A (0-30): <https://github.com/Gfermoto/BirdLense-Hub/issues?q=is%3Aopen+is%3Aissue+label%3Aprogram%3Asota+milestone%3A%22SOTA+Phase+A+%280-30%29%22>
- Фаза B (31-60): <https://github.com/Gfermoto/BirdLense-Hub/issues?q=is%3Aopen+is%3Aissue+label%3Aprogram%3Asota+milestone%3A%22SOTA+Phase+B+%2831-60%29%22>
- Фаза C (61-90): <https://github.com/Gfermoto/BirdLense-Hub/issues?q=is%3Aopen+is%3Aissue+label%3Aprogram%3Asota+milestone%3A%22SOTA+Phase+C+%2861-90%29%22>
- Фаза D (91-120): <https://github.com/Gfermoto/BirdLense-Hub/issues?q=is%3Aopen+is%3Aissue+label%3Aprogram%3Asota+milestone%3A%22SOTA+Phase+D+%2891-120%29%22>

## Readiness Snapshot (Go/No-Go)

Дата валидации: **2026-05-30**

- Wave-SOTA scope (`program:sota` #528–#554): **27/27 CLOSED**.
- Приоритеты open в `program:sota`: **P0=0**, **P1=0**, **P2=0**.
- Acceptance-critical open issues: **#517 + #555 + #556 + #557**.
- Текущее состояние качества: governance/control-plane сильно продвинут, но customer acceptance и outcome-gates по доменному качеству ещё не закрыты.

**Решение:** `NO-GO` для финального acceptance до закрытия `#555/#556/#557` и hard acceptance gates эпика `#517`.

## Текущий критический путь (re-baselined)

1. `#555` — корректный trigger/support/fusion contract + moratorium + bbox/tracks.
2. `#556` — data/UI регрессии (orphan visit, timeline semantics/filters, bird dropdown).
3. `#557` — dataset/export/retrain governance (detector/classifier/behavior/ReID).
4. `#517` hard gates: 14-day reproducible parity + superiority KPI hold + no critical perf regressions.

## Риски реализации

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Долгие ML-эксперименты без gates | High | High | Блок релиза без SOTA-2-02 и SOTA-2-03 |
| Security drift между docs и runtime | Medium | High | Единая control mapping матрица (SOTA-8-01) |
| E2E flaky рост блокирует velocity | Medium | Medium | Anti-flake policy + quarantine |
| Разрастание one-off scripts | High | Medium | Ownership/lifecycle policy для scripts |


# SOTA Roadmap — текущий статус (2026-05-31)

## Program vs acceptance

- `program:sota` wave (`#528–#554`): **27/27 CLOSED**
- Acceptance epic: [#517](https://github.com/Gfermoto/BirdLense-Hub/issues/517) — **OPEN**
- Current P0 blockers:
  - [#555](https://github.com/Gfermoto/BirdLense-Hub/issues/555)
  - [#556](https://github.com/Gfermoto/BirdLense-Hub/issues/556)
  - [#557](https://github.com/Gfermoto/BirdLense-Hub/issues/557)

## Hard rule

Ни один поток не считается завершённым без:

1. **Backend + UI parity** (исправления в обоих слоях, если затронут пользовательский workflow),
2. evidence по доменным quality outcome-метрикам,
3. verify/deploy и rollback-пути без критичных регрессий.

## Acceptance path (priority order)

| Priority | Issue | Focus |
|---------|-------|-------|
| P0 | #555 | Trigger/support/fusion contract, moratorium, bbox/tracks, empty-bbox fix |
| P0 | #556 | Orphan visit + timeline semantics/filters + bird dropdown |
| P0 | #557 | Dataset policy (detector/classifier/behavior/ReID), export governance, domain retrain loop |
| Gate | #517 | 14-day parity hold + superiority KPI + stability/perf gates |

## Operational note

SOTA-control artifacts (gates/runbooks/reports) считаются foundation-layer.  
До закрытия `#555/#556/#557` и hard acceptance `#517` состояние релиза: **NO-GO**.

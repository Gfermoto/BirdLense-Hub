# SOTA Issue Backlog (Wave-Based)

Источник: `docs/strategy/SOTA_ALL_WAVES_MASTER_PLAN_2026.md`

Статус публикации в GitHub:
- Создано **27 issues**: `#528`-`#554` (SOTA-0-01 … SOTA-9-02)
- Текущий статус `program:sota`: **27/27 CLOSED**
- Быстрый фильтр open (ожидаемо пустой): <https://github.com/Gfermoto/BirdLense-Hub/issues?q=is%3Aissue+is%3Aopen+label%3Aprogram%3Asota>
- Acceptance epic после закрытия wave-SOTA: [#517](https://github.com/Gfermoto/BirdLense-Hub/issues/517)

## Правила приоритизации

- **P0** — блокирует надёжность/безопасность/качество решений, выполняется в первую очередь.
- **P1** — критично для масштаба и устойчивого роста.
- **P2** — улучшение эффективности и управляемости.

## Backlog

| ID | Priority | Wave | Название | Тип |
|----|----------|------|----------|-----|
| SOTA-0-01 | P0 | 0 | Baseline Snapshot Contract | Reliability |
| SOTA-0-02 | P0 | 0 | Error Budget Policy & Gate | Reliability/Governance |
| SOTA-1-01 | P0 | 1 | Health/Readiness Contract Hardening | Runtime |
| SOTA-1-02 | P0 | 1 | API Security Controls (OWASP Map) | Security/API |
| SOTA-1-03 | P1 | 1 | OpenAPI Governance (Spectral + CI) | API Quality |
| SOTA-2-01 | P0 | 2 | Decision Engine Contract | ML Core |
| SOTA-2-02 | P0 | 2 | Golden Set Mandatory Gate | ML Quality Gate |
| SOTA-2-03 | P0 | 2 | ML Drift Monitoring & Retrain Triggers | MLOps |
| SOTA-2-04 | P1 | 2 | Champion/Challenger & Shadow Pipeline | MLOps |
| SOTA-2-05 | P1 | 2 | ML Technical Debt Scorecard (28 checks) | ML Governance |
| SOTA-3-01 | P0 | 3 | UI Contract Integrity Guard | Frontend/API |
| SOTA-3-02 | P1 | 3 | Playwright Anti-Flake Program | QA |
| SOTA-3-03 | P1 | 3 | Critical UX Flow Reliability Suite | QA/UX |
| SOTA-4-01 | P1 | 4 | Docs Diataxis Refactor Plan | Docs |
| SOTA-4-02 | P1 | 4 | Docs Drift CI Gate | Docs/CI |
| SOTA-4-03 | P0 | 4 | Runbook Coverage for Top Incidents | Ops Docs |
| SOTA-5-01 | P0 | 5 | DORA Metrics Instrumentation | Engineering Metrics |
| SOTA-5-02 | P0 | 5 | Deploy Idempotency & Rollback Contract | Release Reliability |
| SOTA-5-03 | P1 | 5 | SLSA Build Track Progression | Supply Chain |
| SOTA-6-01 | P1 | 6 | Integration Contract Registry | Integrations |
| SOTA-6-02 | P1 | 6 | Event Burst & Reconnect Resilience | Integrations |
| SOTA-7-01 | P1 | 7 | Scripts Ownership & Lifecycle | Tooling |
| SOTA-7-02 | P2 | 7 | CLI Contract Standardization | Tooling |
| SOTA-8-01 | P0 | 8 | SSDF Control Mapping Implementation | Security Program |
| SOTA-8-02 | P0 | 8 | Secrets & Vulnerability Response Hardening | Security Ops |
| SOTA-9-01 | P1 | 9 | Reliability & Security Review Board | Governance |
| SOTA-9-02 | P1 | 9 | Policy-as-Code for Release Governance | Governance/CI |

## Рекомендованные теги GitHub

- `program:sota`
- `wave:0` ... `wave:9`
- `priority:p0|p1|p2`
- `track:reliability|ml|security|docs|ci|ui|integrations|tooling|governance`

## Definition of Done для каждого issue

- [ ] Изменения в коде/конфиге готовы
- [ ] Автотесты и quality gates обновлены
- [ ] Runbook/документация обновлены
- [ ] Приложены метрики before/after
- [ ] Есть rollback/mitigation план

## Post-SOTA blockers (current)

После закрытия wave-SOTA `#528–#554` финальная приёмка остаётся заблокированной следующими issue:

- [#555](https://github.com/Gfermoto/BirdLense-Hub/issues/555) — trigger/support/fusion contract + moratorium + bbox/tracks/empty-bbox.
- [#556](https://github.com/Gfermoto/BirdLense-Hub/issues/556) — orphan visit + timeline semantics/filters + bird dropdown.
- [#557](https://github.com/Gfermoto/BirdLense-Hub/issues/557) — consilium, dataset policy and domain retrain loop.

Правило закрытия для этих потоков: обязательный **Backend + UI parity** и evidence по доменным outcome-метрикам (не только compliance-gates).


# SOTA All-Waves Master Plan 2026

**Статус:** Re-baselined execution (wave-controls done, outcome acceptance pending)  
**Цель:** довести BirdLense Hub до SOTA-уровня по надёжности, ML-качеству, безопасности, API/UI и операционной управляемости.  
**Основание:** внутренняя волновая модель + внешний бенчмарк лучших практик.

---

## 0) Current execution reality (2026-05-31)

- `program:sota` wave issues (`#528–#554`) are completed as control-plane foundation.
- Final acceptance remains blocked by:
  - [#517](https://github.com/Gfermoto/BirdLense-Hub/issues/517) hard acceptance gates,
  - [#555](https://github.com/Gfermoto/BirdLense-Hub/issues/555) trigger/support/fusion + moratorium + bbox/tracks,
  - [#556](https://github.com/Gfermoto/BirdLense-Hub/issues/556) backend/ui regressions,
  - [#557](https://github.com/Gfermoto/BirdLense-Hub/issues/557) dataset governance council loop.
- Mandatory closure rule for these streams: **Backend + UI parity + field evidence**.

Weekly governance is now mandatory:

1. outcome metrics refresh (`quality_outcome_metrics`),
2. error-budget + golden-set refresh,
3. weekly SOTA reality-check report with explicit go/hold decision.

---

## 1) SOTA-критерии (Definition of SOTA for BirdLense)

Считаем цель достигнутой только при выполнении всех классов критериев:

1. **Product reliability SOTA**
   - SLO/SLI формализованы на сервис, API и ML-пайплайн.
   - Есть error-budget policy, автоматически влияющая на релизы.
   - MTTR и Change Failure Rate в целевых диапазонах.

2. **ML runtime SOTA**
   - Golden set gate обязателен для всех модельных изменений.
   - Model/data drift мониторинг, retrain loop, champion/challenger.
   - Training-serving skew контролируется контрактами и тестами.

3. **Security SOTA**
   - API и supply-chain защищены по OWASP API Top 10 + ASVS + SSDF.
   - Secrets, SBOM/provenance, vulnerability response и disclosure-процесс формализованы.

4. **Engineering execution SOTA**
   - DORA-метрики доступны и используются в релиз-решениях.
   - Docs-as-code и тестовая пирамида поддерживают быстрый и безопасный флоу изменений.

---

## 1.1) Приоритеты реализации для BirdLense

Фокус исполнения этого плана:

1. **Primary:** отладка текущих контуров, устранение регрессий, закрытие технического долга reliability/ML/security.
2. **Secondary:** доведение процессов, тестов, документации и CI до лучших отраслевых образцов.
3. **Tertiary:** новые функции и расширения возможностей (только после прохождения hardening-гейтов и без риска срыва P0/P1).

Правило приоритета в конфликте задач:
- bugfix/hardening > quality automation > feature delivery.

---

## 2) Внешняя референсная база (deep research)

Ниже — обязательные стандарты/источники, на которые опирается план:

- **SRE / reliability**
  - Google SRE Workbook: error budget policy  
    <https://sre.google/workbook/error-budget-policy/>
  - Google SRE: implementing SLOs  
    <https://sre.google/workbook/implementing-slos/>

- **Security / secure SDLC**
  - NIST SSDF SP 800-218 v1.1  
    <https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-218.pdf>
  - OWASP API Security Top 10 (2023)  
    <https://owasp.org/www-project-api-security/>
  - OWASP ASVS  
    <https://owasp.org/www-project-application-security-verification-standard/>
  - CISA Secure by Design  
    <https://www.cisa.gov/securebydesign>

- **Supply chain**
  - SLSA framework  
    <https://slsa.dev/>

- **ML systems / technical debt**
  - Google Rules of ML  
    <https://developers.google.com/machine-learning/guides/rules-of-ml>
  - Hidden Technical Debt in ML Systems (NeurIPS)  
    <https://papers.neurips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems.pdf>
  - Testing & Monitoring of ML Systems (28 checks)  
    <https://research.google.com/pubs/archive/aad9f93b86b7addfea4c419b9100c6cdd26cacea.pdf>

- **Observability / telemetry**
  - OpenTelemetry semantic conventions  
    <https://opentelemetry.io/docs/specs/semconv>

- **Delivery performance**
  - DORA metrics reference  
    <https://cloud.google.com/blog/products/devops-sre/using-the-four-keys-to-measure-your-devops-performance>

- **Testing & docs quality**
  - Practical Test Pyramid (Martin Fowler)  
    <https://martinfowler.com/articles/practical-test-pyramid.html>
  - Playwright best practices  
    <https://playwright.dev/docs/best-practices>
  - Diataxis framework  
    <https://www.diataxis.fr/>

---

## 3) Волновой deep-audit план (expanded)

### Wave 0 — Baseline & Control Plane

**Задача:** зафиксировать «истину состояния» и исключить спорные интерпретации.

**Глубокий аудит:**
- Сверить прод, `dev`, CI и документацию по версиям, конфигам, ключевым флагам.
- Заморозить baseline-набор метрик и golden-клипов.
- Поднять single source of truth для release-go/no-go.

**SOTA-практики:**
- Error budget policy как gate на релизы (Google SRE).
- Change policy, привязанная к SLO burn-rate.

**Критерий выхода:**
- Репродуцируемый baseline-отчёт + автоматический расчёт error budget.

---

### Wave 1 — Runtime Hub (nginx/flask/processor/mcp)

**Задача:** исключить runtime-рассинхрон и «ложно-зелёный» health.

**Глубокий аудит:**
- Развести health/readiness/liveness и зафиксировать их контракт.
- Проверить согласованность auth, rate limit, API error-handling.
- Убрать скрытые single-point-of-failure между web и processor.

**SOTA-практики:**
- API verification по OWASP ASVS V4 + API Top 10 risk mapping.
- OpenAPI-first governance с автоматическим линтингом и contract checks.

**Критерий выхода:**
- Нет сценариев, где сервис «up», а ключевые функции деградированы без алерта.

---

### Wave 2 — ML Pipeline & Decision Quality

**Задача:** закрыть архитектурный разлом `raw>>0, accepted=0` и стабилизировать качество.

**Глубокий аудит:**
- Пройти end-to-end: capture -> detect -> quality -> fusion -> arbitration -> persist.
- Проверить training-serving skew, feature drift, threshold contract.
- Ввести количественную оценку ML technical debt.

**SOTA-практики:**
- Google Rules of ML + anti-patterns из Hidden Technical Debt.
- Mandatory golden-set CI gate.
- Champion/challenger + shadow mode перед promotion.
- Drift monitoring (data + prediction + delayed quality labels), retrain trigger policy.

**Критерий выхода:**
- Любая модель/порог не может попасть в prod без прохождения parity + golden + rollback-plan.

---

### Wave 3 — Web/UI & User-Facing Reliability

**Задача:** сделать UI устойчивым, тестируемым, предсказуемым в CI и в полевых сценариях.

**Глубокий аудит:**
- Контракт OpenAPI -> generated TS -> runtime response consistency.
- Проверка критических flows (`timeline`, `videos`, `settings`, `live`) в e2e.
- Локализация/доступность/перформанс на длинных списках и медленных каналах.

**SOTA-практики:**
- Test pyramid: максимум unit/service, минимум brittle e2e.
- Playwright web-first assertions, strict locator policy, anti-flake protocol.

**Критерий выхода:**
- Flaky tests не блокируют roadmap (quarantine policy), но и не скрываются retry-практиками.

---

### Wave 4 — Documentation & Knowledge System

**Задача:** убрать doc drift и превратить docs в рабочий инструмент управления качеством.

**Глубокий аудит:**
- Структура EN/RU, moved-stubs, валидность ссылок, команд и путей.
- Согласованность docs vs Makefile/CI/deploy scripts.
- Runbook coverage для top incidents.

**SOTA-практики:**
- Diataxis-классификация (tutorial/how-to/reference/explanation).
- Docs quality gates в CI (strict build + link integrity + stale checks).

**Критерий выхода:**
- Новые инциденты закрываются обновлением runbook не позднее одного релизного цикла.

---

### Wave 5 — CI/CD, Deploy, Operations

**Задача:** сделать поставку изменений одновременно быстрой и безопасной.

**Глубокий аудит:**
- Полная трассировка release-path от коммита до прод smoke.
- Проверка preflight/deploy/verify сценариев на идемпотентность и откат.
- Нормализация prod env checks и secrets discipline.

**SOTA-практики:**
- DORA instrumentation (deployment frequency, lead time, CFR, MTTR).
- SLSA-прогресс (provenance/signing/hardened build path).
- Secure-by-design требования в release checklist.

**Критерий выхода:**
- Решения о релизе принимаются по метрикам и gate-правилам, а не вручную «по ощущению».

---

### Wave 6 — Integrations & Edge Ecosystem

**Задача:** убрать «серую зону» между hub и периферией (ESPHome, MQTT, Frigate, Arduino, RTSP Mic).

**Глубокий аудит:**
- Инвентаризация интеграций, topic contracts, schema contracts.
- Анализ деградаций при packet loss, reconnect, event burst.
- Верификация совместимости версий и backward compatibility.

**SOTA-практики:**
- Contract testing для интеграций.
- Observability-first: явные SLI для событийных потоков.

**Критерий выхода:**
- Интеграции имеют формализованные контракты и автоматические smoke/test сценарии.

---

### Wave 7 — Scripts & Tooling Governance

**Задача:** сократить операционный хаос от большого набора скриптов.

**Глубокий аудит:**
- Классификация scripts по критичности, владельцу, частоте использования.
- Дедупликация, deprecation-политика, проверка безопасности и idempotency.
- Проверка локальных/серверных path assumptions.

**SOTA-практики:**
- Tool catalog + lifecycle policy.
- Standardized CLI contracts (`--help`, exit codes, structured logs).

**Критерий выхода:**
- Нет критичных prod-операций, выполняемых «one-off» скриптами без owner/runbook.

---

### Wave 8 — Cross-Cutting Security

**Задача:** единая security-модель на весь стек.

**Глубокий аудит:**
- Threat modeling по ключевым данным/потокам.
- API authz/authn, secrets handling, dependency risks.
- Incident response + vulnerability disclosure workflow.

**SOTA-практики:**
- SSDF mapping (PO/PS/PW/RV) на существующие процессы.
- OWASP API Top 10 risk register + mitigation owner.
- CISA Secure-by-Design evidence pack.

**Критерий выхода:**
- По каждому high-risk сценарию есть: prevention, detection, response.

---

### Wave 9 — Synthesis, Governance, Continuous Improvement

**Задача:** превратить разовые аудиты в постоянную систему улучшений.

**Глубокий аудит:**
- Сведение findings в единый backlog c owner, SLA и risk score.
- Дедуп root causes между wave-областями.
- Проверка эффективности закрытых инициатив (before/after).

**SOTA-практики:**
- Quarterly reliability/security/ML review board.
- Policy-as-code для ключевых gates.

**Критерий выхода:**
- Roadmap живёт как процесс, а не как одноразовый документ.

---

## 4) Нарезка на issue-пакеты (готовый backlog)

Формат: `SOTA-<wave>-<seq>`.

| ID | Wave | Title | Priority | Deliverable |
|----|------|-------|----------|-------------|
| SOTA-0-01 | 0 | Baseline Snapshot Contract | P0 | Авто-отчёт baseline + golden metrics snapshot |
| SOTA-0-02 | 0 | Error Budget Policy & Gate | P0 | Policy + CI/CD gate на budget state |
| SOTA-1-01 | 1 | Health/Readiness Contract Hardening | P0 | Единый контракт health/readiness + алерты |
| SOTA-1-02 | 1 | API Security Controls (OWASP Map) | P0 | Матрица API risk -> control -> test |
| SOTA-1-03 | 1 | OpenAPI Governance (Spectral + CI) | P1 | `.spectral.yaml`, lint job, quality threshold |
| SOTA-2-01 | 2 | Decision Engine Contract | P0 | Формализация detect/score/policy/persist контракта |
| SOTA-2-02 | 2 | Golden Set Mandatory Gate | P0 | Блок релиза при непрохождении golden checks |
| SOTA-2-03 | 2 | ML Drift Monitoring & Retrain Triggers | P0 | Drift dashboard + retrain policy |
| SOTA-2-04 | 2 | Champion/Challenger & Shadow Pipeline | P1 | Shadow eval + promotion checklist |
| SOTA-2-05 | 2 | ML Technical Debt Scorecard (28 checks) | P1 | Скоринг готовности ML production path |
| SOTA-3-01 | 3 | UI Contract Integrity Guard | P0 | OpenAPI↔TS↔runtime consistency gate |
| SOTA-3-02 | 3 | Playwright Anti-Flake Program | P1 | Locator policy, retry policy, quarantine policy |
| SOTA-3-03 | 3 | Critical UX Flow Reliability Suite | P1 | Стабильный smoke/e2e на критических сценариях |
| SOTA-4-01 | 4 | Docs Diataxis Refactor Plan | P1 | Карта docs по квадрантам Diataxis |
| SOTA-4-02 | 4 | Docs Drift CI Gate | P1 | Link/stale/command validity checks |
| SOTA-4-03 | 4 | Runbook Coverage for Top Incidents | P0 | Runbook matrix + coverage KPI |
| SOTA-5-01 | 5 | DORA Metrics Instrumentation | P0 | DF/LT/CFR/MTTR pipeline |
| SOTA-5-02 | 5 | Deploy Idempotency & Rollback Contract | P0 | Проверка и доказуемый rollback path |
| SOTA-5-03 | 5 | SLSA Build Track Progression | P1 | Provenance + signed attestations plan |
| SOTA-6-01 | 6 | Integration Contract Registry | P1 | Реестр MQTT/edge контрактов |
| SOTA-6-02 | 6 | Event Burst & Reconnect Resilience | P1 | Нагрузочные сценарии + remediation |
| SOTA-7-01 | 7 | Scripts Ownership & Lifecycle | P1 | Owner/criticality/deprecate матрица |
| SOTA-7-02 | 7 | CLI Contract Standardization | P2 | Стандарт flags/logging/exit-code |
| SOTA-8-01 | 8 | SSDF Control Mapping Implementation | P0 | Контрольная матрица SSDF -> repo process |
| SOTA-8-02 | 8 | Secrets & Vulnerability Response Hardening | P0 | End-to-end response workflow |
| SOTA-9-01 | 9 | Reliability & Security Review Board | P1 | Регулярный governance цикл |
| SOTA-9-02 | 9 | Policy-as-Code for Release Governance | P1 | Автоматические rule-gates |

---

## 5) Roadmap из issue-пакетов

### Phase A (0-30 дней) — Stop bleeding, control, visibility

**Цель:** закрыть P0-риск и включить измеримость.

Включает:
- `SOTA-0-01`, `SOTA-0-02`
- `SOTA-1-01`, `SOTA-1-02`
- `SOTA-2-01`, `SOTA-2-02`
- `SOTA-5-01`
- `SOTA-8-01`, `SOTA-8-02`

**Gate выхода из фазы:**
- Есть error-budget gate, golden gate, security control map, DORA visibility.

---

### Phase B (31-60 дней) — Reliability hardening & ML maturity

Включает:
- `SOTA-1-03`
- `SOTA-2-03`, `SOTA-2-04`, `SOTA-2-05`
- `SOTA-3-01`, `SOTA-3-02`
- `SOTA-5-02`
- `SOTA-6-01`

**Gate выхода из фазы:**
- ML drift/retrain loop активен, UI/API contracts стабильны, rollback path проверен.

---

### Phase C (61-90 дней) — Scale quality & reduce entropy

Включает:
- `SOTA-3-03`
- `SOTA-4-01`, `SOTA-4-02`, `SOTA-4-03`
- `SOTA-6-02`
- `SOTA-7-01`, `SOTA-7-02`
- `SOTA-5-03`

**Gate выхода из фазы:**
- Документация и tooling управляемы, интеграции и supply chain защищены.

---

### Phase D (91-120 дней) — Governance & continuous SOTA

Включает:
- `SOTA-9-01`, `SOTA-9-02`
- Re-evaluation всех P0/P1 по фактическим метрикам.

**Gate выхода из фазы:**
- Проект работает в режиме постоянного улучшения с policy-as-code.

---

## 6) Шаблон issue (для GitHub)

```md
## Goal
<какую SOTA-дыру закрываем>

## Context
- Wave: <N>
- Related standards: <SRE/SSDF/OWASP/...>
- Baseline metric: <значение>
- Target metric: <значение>

## Scope
- In scope:
  - ...
- Out of scope:
  - ...

## Deliverables
- [ ] Code / config changes
- [ ] Tests / gates
- [ ] Runbook/docs update
- [ ] Before/after metrics attached

## Acceptance criteria
- [ ] Технический контракт выполнен
- [ ] CI gates зелёные
- [ ] Prod/field smoke валидирован
- [ ] Regression risk documented
```

---

## 7) Принципы исполнения

- **Evidence-first:** каждое решение подтверждается метриками и репродуцируемыми проверками.
- **No silent regressions:** любой риск имеет детектор, а не только фикс.
- **Security as default:** у пользователя не должно быть «обязательных ручных хардненингов», чтобы быть в безопасном режиме.
- **Small batches, hard gates:** маленькие изменения, жёсткие quality/security/reliability gates.
- **Docs are part of done:** без обновлённого runbook/change-note задача не считается закрытой.
- **Stabilize-first delivery:** функциональные расширения допускаются только если не откладывают закрытие открытых P0/P1 по качеству и надёжности.

---

## 8) Следующий шаг

1. Держать критический путь `#555/#556/#557 -> #517` как release-blocking.
2. Не закрывать потоки без weekly SOTA reality-check артефакта.
3. Обновлять roadmap/issue backlog при каждом изменении acceptance-статуса.


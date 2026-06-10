> **См. также:** [refactoring_consortium_plan.md](../refactoring_consortium_plan.md) · [EPIC #601 — Консилиум: архитектурная программа Hub](https://github.com/Gfermoto/BirdLense-Hub/issues/601)

# Wave 2 — Web / UI / Config (Consortium)

**Дата:** 2026-06-10  
**Роль:** Web/UI/Config specialist  
**Источник:** `docs/strategy/simplification_optimization_proposal.md` + обход кода  
**Статус:** draft (без кода, без `gh issue create`)

---

## 0. Scope и метрики (факт из репо)

| Зона | Масштаб | Якорные файлы |
|------|---------|---------------|
| Web routes | 35 модулей | `app/web/routes/` |
| Web services | 129 файлов | `app/web/services/` |
| OpenAPI | ~5784 строк | `app/web/openapi.yaml` |
| default_config | 1283 строк | `app/app_config/default_config.yaml` |
| UI API layer | 31 модуль | `app/ui/src/api/` |
| Settings UI | 43 файла | `app/ui/src/pages/Settings/` |
| CI (PR) | 8 jobs | `.github/workflows/ci-pr.yml` |

---

## 1. Критическая оценка proposal (линза Web/UI/Config)

### 1.1. Что proposal попадает точно

**HTTP/UI.** Proposal (#4) верно фиксирует смешанную модель: `client.ts` уже даёт CSRF для axios-interceptor и `csrfFetch`, но **~20+ модулей** продолжают вызывать `axios`/`fetch` напрямую (`speciesOverviewDetections.ts`, `systemAuditMetrics.ts`, `timeline.ts`, `labelling.ts`, `dataset.ts`, `settingsYamlDb.ts`, `motionPreview.ts`). Последствия: разный парсинг ошибок (`getApiErrorMessage` только в `api.tsx`), неодинаковые `credentials`, тесты мокают axios vs fetch по-разному.

**Config.** 1283 строк `default_config.yaml` + deep merge в `app_config.py` (`merge_dicts`, migrations, confidence floors, pydantic) — cognitive load реальный. UI через `ProcessorSection` + 20+ блоков экспонирует сотни ключей; `simpleMode` уже есть, но **частичный** (скрывает Frigate/OpenVINO/dataset, не tier-metadata).

**Web services.** 129 сервисов — proposal (#7 DRY ingest) обоснован: `processor_routes.py` (~270+ LOC контрактов) vs `services/processor_ingest/*` — граница есть, но diagnostics/readiness/funnel/domain-health **пересекаются** (`readiness_service`, `system_diagnostics_service`, `component_status_service`, `system_domain_health_service`).

**Readiness/funnel.** Уже production-grade контракт:
- `persist_funnel_service.py` — `persist_funnel_summary@v1`, пороги из `readiness.*` config
- `readiness_service.py` — `quality_ready = funnel_ok ∧ yolo_ok`; HTTP 503 при degraded core checks
- OpenAPI описывает `quality_ready` отдельно от `ready`

Proposal недооценивает **стоимость изменения** этих payload — на них завязаны `verify-stack.sh`, `check-quality-gates.sh`, nightly governance.

### 1.2. Где proposal завышен или рискован

| Пункт proposal | Риск | Комментарий |
|----------------|------|-------------|
| Phase 4: 129→80 services | Scope creep | Без domain map merge сломает import graph и тесты; не даёт user-visible win |
| Schema-driven Settings (Phase 4) | Effort >> Impact | Уже есть `check-settings-ui-coverage.py` + ручные блоки; полный JSON Schema → форма — отдельный EPIC |
| «Pydantic end-to-end settings» (#149 DRY) | Частично есть | `settings_patch_service` + `validate_merged_config_pydantic` уже на PATCH; полная замена YAML UI — breaking |
| UI HTTP unification Phase 1 | Занижен effort | `speciesOverviewDetections.ts` alone — 30+ axios calls; нужен typed wrapper, не «переименовать fetch» |
| Config tiers «без UI change» Phase 0 | Противоречие | Tiers без UI = только docs; ценность — когда `simpleMode` ↔ tier sync + deprecated keys hidden |

### 1.3. Что proposal правильно НЕ трогает

- `strict_ui_api_auth_service.py` + allowlist (`/api/ui/health`, `/api/ui/readiness`, CSRF, settings password flow)
- OpenAPI as SoT + CI drift check (`codegen:openapi` + `git diff openapi-types.ts`)
- Deploy exclude `user_config.yaml` (`scripts/public/deploy.sh` rsync exclude + filter `P`)
- Readiness/funnel metrics schema

### 1.4. Пробелы proposal (Wave 2 должна добавить)

1. **Settings coverage guard** — `scripts/check-settings-ui-coverage.py` + `test_settings_ui_coverage_guard.py`; любое скрытие ключей должно обновлять allowlist, иначе CI падает.
2. **Session idle + health** — `session_idle_service.py` exempt `/api/ui/health`; новые polling endpoints не должны триггерить logout.
3. **CI job `openapi-contract`** — перегружен (ruff, golden gate, stress, 20+ benchmark pytest); web-only refactor не должен блокироваться processor golden, но сейчас блокируется.
4. **`/api/ui/health` vs `/api/ui/readiness`** — health лёгкий (`ui_status_push_routes.py`); readiness тяжёлый (DB, funnel). Proposal путает «health dashboard facade» (#148) с заменой контрактов.

---

## 2. Предложения по рефакторингу (с жёсткими ограничениями)

### 2.1. UI HTTP — единая точка входа (Phase 1)

**Цель:** один `apiRequest<T>()` поверх существующего `client.ts` (CSRF + credentials + timeout).

**План:**
1. Расширить `client.ts`: unified error type, JSON parse, `getApiErrorMessage` integration.
2. Миграция **по доменам** (не big-bang): labelling → dataset → settingsYamlDb → timeline exports → speciesOverviewDetections (last, largest).
3. Оставить axios только как transport внутри wrapper **или** удалить после миграции (package.json audit).

**НЕ ломать:**
- CSRF header `X-Birdlense-CSRF-Token` на mutating methods (tests: `client.test.ts`)
- `withCredentials: true` / `credentials: 'include'` для session auth
- Relative `BASE_API_URL = '/api/ui'` (same-origin deploy)

**Не трогать:** blob/export URLs в `timeline.ts` (raw fetch для download может остаться с явным comment «binary export exception»).

### 2.2. Config tiers (Phase 0–2)

**Tier model (proposal):**

| Tier | Аудитория | UI | Config source |
|------|-----------|-----|---------------|
| Basic | Operator | `simpleMode=true` (default) | subset keys in ProcessorSection |
| Advanced | Contributor | `PageModeToggle` → full | все текущие блоки |
| Expert | Admin | Advanced + YAML import/export | raw keys + `system/tuning-workbench` |

**Backend (без deploy break):**
- Mark deprecated in `default_config.yaml` comments (already pattern: «runtime may ignore»)
- `deprecated_keys_present()` warnings on PATCH — **сохранить** в API response
- Новые keys только в `default_config.yaml`; `user_config` merge unchanged

**НЕ ломать:**
- `merge_dicts(default, user)` order in `app_config.load_and_merge_configs()`
- `CONFIDENCE_FLOORS`, `SENSITIVE_KEYS`, contributor-only paths
- Deploy: rsync `--exclude=app/app_config/user_config.yaml` + server backup `.bak.deploy-*`
- Idempotent `merge_user_config_regen_defaults.py` post-deploy

### 2.3. Web services — точечный DRY (Phase 2, не Phase 4 merge)

**Приоритет 1 — ingest facade:** обернуть processor POST paths в `processor_ingest` gateway (уже начато) — routes только HTTP + auth.

**Приоритет 2 — observability composite (read-only):**
- Новый thin `operational_dashboard_service.py` **агрегирует** existing builders:
  - `build_persist_funnel_summary`
  - `build_component_status_payload_safe`
  - `build_security_gates_payload`
- **Не менять** поля существующих endpoints; optional `?view=compact` только если OpenAPI extended.

**Приоритет 3 — settings R/W:** усилить `settings_patch_service` — единственная точка PATCH validation (уже почти так).

**НЕ ломать:**
- `persist_funnel_summary@v1` schema keys
- `quality_ready` computation logic
- `strict_quality_ready` in `system_domain_health_service.py` (отдельный strict block)

### 2.4. OpenAPI + codegen discipline

Любое изменение response shape:
1. `app/web/openapi.yaml`
2. `npm run codegen:openapi`
3. `test_openapi_contract.py`
4. UI types compile (`typecheck`)

Spectral governance: `scripts/verify_openapi_governance.py` в CI.

### 2.5. CI simplification (Wave 2 meta)

| Проблема | Предложение |
|----------|-------------|
| `openapi-contract` job смешивает web + processor golden | Split: `web-contract` (ruff web, openapi, strict auth) vs `processor-golden` |
| Docker job duplicate coverage | Keep single source: `make ci-local` doc as entry |
| Settings guard orphan | Run `check-settings-ui-coverage.py` in CI explicitly (сейчас только pytest wrapper) |

**НЕ ослаблять:** `verify-prod-env-smoke`, `test_strict_ui_api_auth.py`, coverage ≥80% on `strict_ui_api_auth_service.py` + csrf.

---

## 3. Draft GitHub Issues

### Issue W2-01 — UI HTTP wrapper и миграция labelling/dataset

**Labels:** `wave2`, `ui`, `tech-debt`, `phase-1`  
**Priority:** P1  
**Phase:** 1

**Body:**
Ввести `apiRequest<T>()` в `app/ui/src/api/client.ts` (CSRF, credentials, typed errors). Мигрировать `labelling.ts`, `dataset.ts`, `settingsYamlDb.ts` с raw fetch на wrapper. Сохранить поведение `csrfFetch` для multipart/binary.

**Acceptance:**
- [ ] `npm run test`, `typecheck`, `lint` green
- [ ] `client.test.ts` покрывает wrapper errors
- [ ] Mutating calls отправляют CSRF header
- [ ] Нет новых прямых `fetch` для JSON API в migrated files

---

### Issue W2-02 — UI HTTP: миграция axios-heavy modules (batch 2)

**Labels:** `wave2`, `ui`, `phase-1`  
**Priority:** P1  
**Phase:** 1

**Body:**
Мигрировать `birdFoodFeed.ts`, `favorites.ts`, `weatherRegion.ts`, `camerasHealth.ts`, `video.ts` на unified client. `speciesOverviewDetections.ts` — отдельным PR (size).

**Acceptance:**
- [ ] axios call count в `src/api/` снижен ≥50%
- [ ] Existing vitest files updated (mock unified client)
- [ ] Production strict auth smoke unchanged

---

### Issue W2-03 — Config tiers: документ + metadata в default_config

**Labels:** `wave2`, `config`, `documentation`, `phase-0`  
**Priority:** P2  
**Phase:** 0

**Body:**
Документировать Basic/Advanced/Expert tiers. В `default_config.yaml` добавить YAML comments `# tier: basic|advanced|expert` и `# deprecated: true` для legacy keys (без удаления). Audit list «runtime may ignore» keys.

**Acceptance:**
- [ ] Doc in `docs/strategy/consortium/config_tiers.md`
- [ ] `check_legacy_processor_config.py` still green
- [ ] No change to merge semantics

---

### Issue W2-04 — Settings UI: sync simpleMode с config tiers

**Labels:** `wave2`, `ui`, `settings`, `phase-2`  
**Priority:** P2  
**Phase:** 2

**Body:**
Расширить `simpleMode` hiding по tier metadata: OpenVINO, Frigate fusion, dataset, advanced confidence — уже частично есть; добавить Birdnet extended / behavior blocks toggle. Persist mode in localStorage.

**Acceptance:**
- [ ] `check-settings-ui-coverage.py` green (update allowlist if needed)
- [ ] PATCH still sends full form values (hidden fields preserved from loaded settings)
- [ ] `test_settings_ui_coverage_guard.py` passes

---

### Issue W2-05 — Readiness: finalize breakdown in funnel (read-only extension)

**Labels:** `wave2`, `web`, `observability`, `phase-0`  
**Priority:** P2  
**Phase:** 0

**Body:**
Расширить readiness checks с breakdown finalize stages **если** данные уже в `SessionRuntimeMetrics.payload_json` — без изменения `quality_ready` formula. Optional nested object under `checks.pipeline_funnel`.

**Acceptance:**
- [ ] `quality_ready` logic unchanged in `readiness_service.py`
- [ ] `test_readiness_service.py`, `test_persist_funnel_service.py` green
- [ ] OpenAPI updated if new fields exposed

---

### Issue W2-06 — Operational dashboard facade (no endpoint removal)

**Labels:** `wave2`, `web`, `refactor`, `phase-2`  
**Priority:** P3  
**Phase:** 2

**Body:**
Extract shared aggregation from readiness/diagnostics/domain-health into internal facade; routes call facade. Zero removal of public fields in `/api/ui/readiness`, `/api/ui/system/domain-health`.

**Acceptance:**
- [ ] `verify-stack.sh --strict-quality` unchanged behavior
- [ ] `test_system_domain_health_service.py` green

---

### Issue W2-07 — Strict auth: decorator audit (no allowlist regression)

**Labels:** `wave2`, `web`, `security`, `phase-1`  
**Priority:** P1  
**Phase:** 1

**Body:**
Audit new routes since #279; ensure `@before_request` strict gate uses central lists. Document process for adding public GET endpoints. Optional: reduce per-route duplicate checks **without** shrinking `_STRICT_ALLOWLIST` / `_PUBLIC_GET_*`.

**Acceptance:**
- [ ] `test_strict_ui_api_auth.py` extended for any new public routes
- [ ] `/api/ui/health` returns 200 without session in production strict mode
- [ ] `verify-prod-env-smoke` green

---

### Issue W2-08 — OpenAPI: pipeline-funnel + readiness schema hardening

**Labels:** `wave2`, `openapi`, `phase-1`  
**Priority:** P2  
**Phase:** 1

**Body:**
Ensure `/readiness`, `/system/pipeline-funnel` schemas match `persist_funnel_service` output (`schema`, rates, alerts). Regenerate TS types.

**Acceptance:**
- [ ] `git diff --exit-code openapi-types.ts` after codegen
- [ ] `test_openapi_contract.py` green
- [ ] UI `camerasHealth.ts` readiness types accurate

---

### Issue W2-09 — CI: split web-contract vs processor-golden jobs

**Labels:** `wave2`, `ci`, `phase-1`  
**Priority:** P2  
**Phase:** 1

**Body:**
Split `openapi-contract` job: web lint/contract/auth separate from processor golden gate + stress. Faster feedback for UI/web PRs.

**Acceptance:**
- [ ] PR touching only `app/ui/` can pass without processor golden (path filters)
- [ ] Full CI on `main`/nightly unchanged coverage
- [ ] `make ci-local` docs updated

---

### Issue W2-10 — Settings PATCH: pydantic error messages UX

**Labels:** `wave2`, `web`, `ui`, `phase-2`  
**Priority:** P3  
**Phase:** 2

**Body:**
Surface `SettingsPatchValidationError.issues` to UI as field-level errors (today generic save error). No change to validation rules.

**Acceptance:**
- [ ] Invalid PATCH returns 400 with structured issues array (OpenAPI documented)
- [ ] Settings save shows first N issues
- [ ] Contributor/admin path restrictions unchanged

---

### Issue W2-11 — Deprecated config keys: UI warning polish

**Labels:** `wave2`, `ui`, `config`, `phase-2`  
**Priority:** P3  
**Phase:** 2

**Body:**
Improve `_settings_warnings.deprecated_keys_present` display in Settings (already partially in `index.tsx`). Link to config audit endpoint.

**Acceptance:**
- [ ] Warning after save lists deprecated keys
- [ ] Keys remain in user_config (not stripped on deploy)

---

### Issue W2-12 — Processor routes ingest DRY (web-only slice)

**Labels:** `wave2`, `web`, `phase-2`  
**Priority:** P2  
**Phase:** 2

**Body:**
Move remaining idempotency/hash helpers from `processor_routes.py` into `services/processor_ingest/`. Routes ≤ HTTP + `_check_processor_secret`.

**Acceptance:**
- [ ] `test_processor_videos_smoke.py` green
- [ ] Processor secret gate unchanged
- [ ] No OpenAPI path changes

---

## 4. Cross-critique: Wave 1 (processor/CV) vs Wave 2 (web/UI/config)

Wave 1 (из proposal §3, §7, §8 — finalize, legacy pipeline, go2rtc, OpenVINO, except narrowing) и Wave 2 пересекаются. Риск **scope creep** — когда web-рефактор тянет processor semantics.

| Тема Wave 1 | Wave 2 зависимость | Конфликт / синергия |
|-------------|-------------------|---------------------|
| **Finalize декомпозиция** | W2-05 readiness breakdown | Синергия: web только **отображает** новые stage metrics; не менять finalize |
| **Remove `pipeline_mode: legacy`** | W2-03/W2-04 config tiers | Конфликт: скрытие legacy keys в UI до migration window → ops не смогут rollback; **сначала** migration note + audit, потом UI hide |
| **OpenVINO bootstrap validation** | Settings OpenVino block (simpleMode hides) | Синергия: readiness `yolo_detector` check уже есть; UI tier must not hide critical error surfacing on System page |
| **HTTP unification (UI)** | Wave 1 не трогает | Wave 2 isolated — **не блокировать** на finalize split |
| **Web services 129→80** | Wave 1 ingest load ↑ | Конфликт: merge services while changing processor_routes — **запретить** в Phase 2 ingest period |
| **except Exception narrowing (processor)** | Funnel metrics noise ↓ | Синергия: меньше false «healthy» sessions; `quality_ready` станет строже — зафиксировать baseline перед Wave 1 |

**Рекомендация sequencing:**
1. Wave 2 Phase 0–1 (HTTP, OpenAPI, CI split) **parallel** Wave 1 Phase 0 measure
2. Wave 2 Phase 2 (tiers, facade) **after** Wave 1 legacy migration decision
3. Не объединять «HTTP unification» с «schema-driven forms» в один PR

**HTTP unification vs scope creep:** unification — bounded (~8–12 files, no API change). Scope creep — settings schema generator + service merge + readiness redesign в одном milestone. Держать W2-01/02 отдельно от W2-06/10.

---

## 5. Anti-regression acceptance criteria (Wave 2 gate)

### 5.1. Production security

| Check | Command / test | Expected |
|-------|----------------|----------|
| Strict auth gate | `test_strict_ui_api_auth.py` | 403 on private routes without session when `BIRDLENSE_STRICT_API_AUTH=1` + production |
| Health allowlist | GET `/api/ui/health` no auth | 200 |
| Readiness allowlist | GET `/api/ui/readiness` no auth | 200/503 body valid (not 403) |
| Prod env script | `verify-prod-env.sh` | exit 0 with required secrets |
| CSRF | `test_csrf_service.py`, `client.test.ts` | mutating requests require token |

### 5.2. OpenAPI contract

| Check | Expected |
|-------|----------|
| `npm run codegen:openapi` + git diff | no drift on committed types |
| `test_openapi_contract.py` | green |
| `verify_openapi_governance.py` | green |

### 5.3. Readiness / funnel / quality_ready

| Invariant | Location |
|-----------|----------|
| `quality_ready === (funnel.status != 'degraded') && (yolo_detector.status == 'ok')` | `readiness_service.py:280-282` |
| Funnel schema `persist_funnel_summary@v1` | `persist_funnel_service.py` |
| Thresholds from config `readiness.funnel_lookback_hours`, `max_fp_empty_opencv_rate`, etc. | config-driven, not hardcoded in UI |
| `strict_quality_ready` block | `system_domain_health_service.py` unchanged semantics |
| External scripts | `scripts/check-quality-gates.sh`, `scripts/public/verify-stack.sh --strict-quality` pass on golden fixture |

### 5.4. Config / deploy

| Invariant | Expected |
|-----------|----------|
| Deploy rsync | `user_config.yaml` excluded |
| Server backup | `.bak.deploy-*` before sync |
| PATCH settings | writes user_config only via API, merge preserves secrets placeholders |
| default_config | shipped with deploy; user overrides win |

### 5.5. UI / CI

| Check | Expected |
|-------|----------|
| `npm run test`, `typecheck`, `lint`, `build` | green |
| `test_settings_ui_coverage_guard.py` | green after tier changes |
| `make ci-local` (or split web job) | green before merge |

### 5.6. Rollback triggers (stop ship)

- Любой 403 на `/api/ui/health` или `/api/ui/readiness` в strict prod
- Изменение `quality_ready` formula без ADR + script updates
- OpenAPI breaking change without version bump
- Deploy overwriting `user_config.yaml`
- CSRF bypass on settings PATCH / labelling mutations

---

## 6. Резюме для consortium

Wave 2 должна **сжать cognitive load** (HTTP, settings tiers, CI feedback) **без** изменения prod security contour, funnel semantics и deploy data safety. Proposal верен в диагнозе UI HTTP и config surface; завышает service merge и schema-driven UI в ближайших фазах. Wave 1 processor work **не блокирует** W2-01/02/07/09; **блокирует** aggressive legacy key hiding (W2-04).

**Приоритетный минимум (4–6 нед):** W2-01, W2-02, W2-07, W2-08, W2-09 + Phase 0 W2-03.

---

*Подготовлено по состоянию репозитория 2026-06-10. Дополняет `simplification_optimization_proposal.md`, не заменяет EPIC #606–#612.*

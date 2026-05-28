# SOTA roadmap — handoff для QA (2026-05-28)

**Ветка:** `dev`  
**Эпик:** [#491](https://github.com/Gfermoto/BirdLense-Hub/issues/491)  
**Уже закрыты:** SOTA-02…14, #506, #516

Закрытие issues = **готово к приёмочному QA на VPS**, не отмена доработок по результатам поля.

---

## Волна 1 — Конфиг (#492 SOTA-01)

| Критерий | Где |
|----------|-----|
| Pydantic / JSON Schema merge | `app/app_config/config_schema.py`, `schema/birdlense_config.schema.json` |
| Fail-fast при загрузке | `app_config.validate_merged_config*` в `app_config.py` |
| Тесты | `app/web/tests/test_config_pydantic_schema.py` |
| Док | `docs/ru/config-schema.ru.md` |

**QA:** сохранить битый ключ в Settings → ошибка; `make ci-local` green.

---

## Волна 2 — Классификация и fusion (#507, #508)

| Issue | Доставлено |
|-------|----------|
| **507** | Birder EU 707 (#516), `weighted_arbiter_*`, rodent/bird gates, `birder_eu_min_confidence` |
| **508** | `trigger_graph` в `recording_session_summary` + System UI `TriggerGraphDashboardCard`; VideoDetails: `decision_reasons`, `detection_provider` |

**QA:** запись с птицей → System → Trigger graph; VideoDetails → источник/причины; нет «тихого» пустого клипа при Frigate+MQTT (после hotfix `frigate_standalone_require_blind_yolo`).

---

## Волна 3 — Каталог и аудио (#509; #506 закрыт)

| Критерий | Где |
|----------|-----|
| 707+Rodent allowlist, idealize | `catalog_idealize.py`, `issue_506_checklist.md` |
| Group label → audio term | `audio_search_term_for_species_name` + тесты |
| KPI probe (opt-in) | `species.catalog_probe_audio_on_coverage` |

**QA:** `scope=allowlist` → 708; species-directory; опционально probe audio в coverage snapshot.

---

## Волна 4 — Производительность (#510–#512)

| Issue | Доставлено |
|-------|----------|
| **510** | `FinalizeWorker` queue, classifier task queue caps/drops, `recording_finalize` metrics |
| **511** | `FrameContext` / `RoiRef` в hot path (`frame_processor.py`) — foundation W1.2 |
| **512** | `track_regen_serialize_inference*`, interprocess lock, `GET …/regenerate-tracks/status`, **409** if running, timeouts в config |

**QA:** regen одного ролика при idle processor; не 409 loop; live не падает 137 за 1h; `./scripts/diagnose_detection_today.sh`.

---

## Волна 5 — API и UI (#513–#515)

| Issue | Доставлено |
|-------|----------|
| **513** | Job-статус для regen / catalog repair / export (отдельные endpoints + polling), не единый `POST /jobs` |
| **514** | Индексы visits/videos (#003 perf), timeline API + pagination patterns |
| **515** | `/species`, species-directory, System dashboard (catalog + trigger graph), PageHelp частично |

**QA:** длинный regen → poll status до `done`; Timeline на прод-объёме < целевого p95 (зафиксировать факт); новый оператор находит каталог vs system.

---

## Глобальные проверки QA

1. `make ci-local` на `dev`
2. VPS: `make verify` / health
3. Две камеры (любые id) — **один** `user_config`, без per-camera overrides
4. Golden: `make validate-pipeline-golden` (если в CI scope)
5. Доки: `docs/contributor/roadmap.md`, `AGENTS.md`

---

## Post-QA (не блокирует закрытие волны)

- Единый `POST /api/ui/jobs` (#513 stretch)
- Полный zero-copy ROI в classifier crops (#511 stretch)
- Postgres timeline p95 на 10k visits (#514 field measure)

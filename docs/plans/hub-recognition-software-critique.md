# Hub recognition — software critique (not site tuning)

Date: 2026-07-19 · Branch: `orin` · Epic: #666

This document evaluates BirdLense Hub as **software**, not an Orin/Frigate install.
No threshold advice. No dual-camera folklore.

## Verdict

Hub optimizes a **recording / persistence product**. Ornithological recognition
(`named` taxa with provenance) is a budget-starved side effect. Agents keep
tuning site knobs because those knobs move `db_persist_success`; species quality
has no hard software contract in CI or runtime gates.

## Ranked root causes

### RC1 — Critical: conflicting product contracts

| Contract | “Win” |
|----------|--------|
| Persist (`binary_track_first`) | YOLO Bird + bbox → DB |
| Visit eligibility | Bird / Unknown / Rodent still visit-eligible |
| Notify | named + not review |
| Documented SLO (`visit_contract`) | named / `named_share_hub` |
| Session summary | `db_persist_success = video_id is not None` |

Evidence: `persist_mode.py`, `visit_eligibility.py`, `visit_contract.py`,
`recording_finalize.py` (`db_persist_success`), `docs/user/runbooks.md`.

**Remediation:** one typed `RecognitionOutcome`
(`presence | review | named_accept | named_reject`). Persist/UI/notify/visit
derive from it. CI and go-gates use taxonomy metrics, not `db_persist_success`.

**Progress (2026-07-19):** `RecognitionOutcome` stamped on persist rows; session
summary exposes `recognition_outcomes` / `taxonomy` / `presence`;
`named_share_hub` = `hub_taxonomy_win`; visit/notify honor review-only.
Remaining: PresenceRecorder vs SpeciesRecognizer service split (radical arch).

### RC2 — Critical: classify is not a product stage

Documented linear order: detect → classify → decide → persist.
Actual finalize: budget-capped deferred classify (default ~2 tracks / ~2500 ms)
→ decide → MQTT fusion → salvage → persist.

Evidence: `finalize_classification.py`, `recording_finalize.py` order,
`linear_pipeline.py` stage comments vs reality.

**Remediation:** first-class `SpeciesHypothesis` stage with fail-closed
`skip_reason`. Separate latency SLO from recognition completeness (async
classify + patch visit allowed).

**Progress (2026-07-19):** defaults aligned (8s/6 tracks/3 kf);
`classify_skip_reason` stamped on budget/timeout/no_crop/deferred/unknown_abstain
and copied into decision rows; `pipeline_stage=classify_enrich` when classifier
touched. Async patch-visit still open.

### RC3 — High: dual decision engines + post-hoc salvage

Default `pipeline_mode=linear` short-circuits `DecisionMaker`; legacy
best-guess path is largely dead. Salvage / Frigate / anchor restore can invent
or stamp `decision_kind` after arbitration.

Evidence: `decision_maker.py` linear early return; `salvage.py`;
anchor restore in `recording_finalize.py`.

**Remediation:** one decision function. Salvage emits presence evidence only,
never silent species accept.

**Progress (2026-07-19):** salvage review-only; `legacy` forced to linear;
legacy cascade quarantined behind test-only `pipeline_mode=dual`. Full delete
of dual body still open.

### RC4 — High: Frigate/MQTT entangled in core

Defaults enable Frigate trigger; blind health uses Frigate-only frames;
`frigate_site` role and fusion standalone live in core config.
Hub-absent is possible mechanically, not first-class.

Evidence: `default_config.yaml` triggers; `detection_fusion.py`;
`visit_contract.apply_frigate_named_accept`.

**Remediation:** protocols `TriggerSource` / `BoxProvider` / `SpeciesHint` /
`SpeciesAuthority`. Hub-only profile unloads Frigate modules. Named Frigate
never enters Hub go-metrics.

**Progress (2026-07-19):** `tuning_role: hub_only` +
`app_config/profiles/hub_only.example.yaml` (Frigate trigger/salvage/authority
off). Full module unload / protocol interfaces still open.

### RC5 — High: no closed learning loop in product

Review → export / active-learning buffer. No runtime adapter (LoRA /
prototype memory / site thresholds) fed by corrections.

Evidence: `feedback_loop_service.py`; Birder weights load-once
(`birder_eu_classifier.py`).

**Remediation:** versioned `SiteAdapter` + canary; until then, review-queue KPIs
are product metrics, not ML-ops side tools.

**Progress (2026-07-19):** `site_adapter.py` manifest + canary noop;
`feedback_loop_status.site_adapter` KPI. Weights/LoRA apply still open.

### RC6 — High: CI golden validates tracks, not species

`make validate-pipeline-golden` with `--skip-heavy` passes unit track stubs.
Live gate can pass with zero named species.

Evidence: `scripts/pipeline_golden_gate.py`, `test_yolo_golden_clips_gate.py`.

**Remediation:** labeled Hub-only clip pack as merge gate; track-only golden
renamed as detector gate only.

**Progress (2026-07-19):** detector vs taxonomy split landed —
`make validate-detector-golden` / `make validate-species-golden`,
`RecognitionOutcome` + `benchmarks/species_golden_cases.json`. Live pack
scaffold: `benchmarks/species_live_hub_only/` +
`make validate-species-live-hub-only` (empty pack skips; `--require-clips` for
strict CI). Clip runtime eval still open.

### RC7 — Medium: weak open-set / Unknown handling

Birder prefers best named over Unknown; deferred maps empty/Unknown → Bird
presence; best-guess can become `accepted_species` with needs_review.

Evidence: `birder_eu_classifier.py`; `linear_pipeline._species_from_classifier`.

**Remediation:** explicit abstention; `Unknown` ≠ presence Bird; never map
abstain → named_accept without calibration.

**Progress (2026-07-19):** Birder honest argmax (no prefer-named-over-Unknown);
linear maps Unknown-only events → `classify_skip_reason=unknown_abstain` +
presence Bird review_only (not named_accept).

### RC8 — Medium: site roles in core defaults

`feeder_close` / `feeder_far` / `frigate_site` encode install physics into
`default_config` and role merge used by salvage/authority.

Evidence: `default_config.yaml` `camera_tuning_by_role`;
`linear_pipeline._role_preset`.

**Remediation:** capability profiles from stream probe; feeder/Frigate names
only in install examples.

### RC9 — Medium: observability conflates reliability, presence, taxonomy

`db_persist_success`, track counters, and `primary_signal=species_classifier`
(for any `accepted_species`) mislead dashboards and agents.

Evidence: `recording_finalize.py` session summary; `runtime_contract.py`.

**Remediation:** namespaces `reliability.*` / `presence.*` / `taxonomy.*`.

**Progress (2026-07-19):** session summary `taxonomy` / `presence` /
`recognition_outcomes`; `primary_signal=species_classifier_review` for uncertain
named. Full `reliability.*` metric rename still open.

## Why agents keep “tuning the site”

Responsive levers (roles, Frigate salvage, binary floors) move empty-UI /
empty-DB symptoms. Species quality is deferred, untested, and not the runbook
gate — so deep product work has nothing to grab.

## Radical architecture (SOTA-shaped)

1. Split **PresenceRecorder** vs **SpeciesRecognizer** (shared media, separate SLOs).
2. Hypothesis store: temporal crops + logits + abstain (not one finalize crop).
3. Explicit authority graph; no silent promote.
4. Eval-in-CI: Hub-only labeled suite as merge gate.
5. Learning loop: review → adapter version → canary.
6. Delete dual pipelines (linear/legacy mythology).
7. Camera as `StreamBundle` data — zero feeder/Frigate names in decision core.

## Explicit non-goals for this critique

- Orin SSH, Frigate MQTT dials, dual-cam offsets as “the fix”
- Raising/lowering `min_confidence_*` as SOTA strategy

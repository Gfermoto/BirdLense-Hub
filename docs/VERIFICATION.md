# Quality verification (operators & maintainers)

Short log of automated checks. Full cycle: [CONTRIBUTING.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md), [TESTING.md](./TESTING.md).

Shared install/deploy smoke contract: `make verify` (or `scripts/verify-stack.sh --base-url ...`) checks `/api/ui/health`, `/api/ui/readiness`, and `/api/ui/status`.

## 2026-05-14 — Runtime SLI threshold gate (C2)

For operational alerting before/after deploy:

```bash
make verify-runtime-sli
```

This gate reads `/metrics` and fails when thresholds are violated:
- `birdlense_processor_heartbeat_stale != 0` (by default required)
- `birdlense_processor_heartbeat_age_seconds > 240` (default max age)
- HTTP slow-ratio (`>1000ms`) exceeds `0.20` with at least `20` samples

Thresholds are configurable via env:
`MAX_HEARTBEAT_AGE_SECONDS`, `MAX_HTTP_OVER_1000MS_RATIO`, `MIN_HTTP_SAMPLE_COUNT`, `REQUIRE_HEARTBEAT_STALE_ZERO`.

## 2026-05-02 — Persistent ML proof gate (local + hub)

To prevent "works now, lost after deploy" regressions, run one reproducible gate:

```bash
make ml-proof
```

What `ml-proof` enforces:
- `ml-proof-local`: synthetic/unit checks for Wave 5-12 ML artifacts (OpenVINO profile, decode benchmark, continuity/INT8/shadow/canary/full-rollout/action shortlist scripts + OpenVINO selector/runtime tests).
- `ml-proof-hub`: checks real deployed hub via SSH:
  - `detector_continuity_report@v1` from live SQLite,
  - `track_continuity_eval@v1`,
  - OpenVINO smoke inside container (`Core().available_devices`, `intel:gpu` inference steady latency),
  - final `ml_proof_hub_report@v1` in `/tmp/bl_metrics/ml_proof_hub_report.v1.json`.

Gate fails (`exit != 0`) when any of these fails: continuity, track continuity SLO, GPU visibility, GPU latency threshold, or OpenVINO model runtime error.

## 2026-05-02 — Fusion A/B gate (duplicates + YOLO share + calendar delta)

To validate the fusion layer after policy changes:

```bash
make ml-fusion-ab-hub
```

Or run locally on a DB snapshot:

```bash
DB=app/data/db/birdlense.db OUT=/tmp/fusion_ab_report.v1.json make ml-fusion-ab-local
```

Artifact `fusion_ab_report@v1` includes:
- YOLO vs Frigate provider share (`yolo_share_vs_frigate`),
- duplicate video groups and duplicate `video_species` groups in the selected window,
- overlap ratio of generic `Bird` rows with specific species rows,
- optional `encounters` vs `max_simultaneous` delta from `/api/ui/migration-calendar/compare`.

## 2026-05-02 — Wave 1 / #402 detector-first baseline

Minimum package for [#403](https://github.com/Gfermoto/BirdLense-Hub/issues/403) and [#411](https://github.com/Gfermoto/BirdLense-Hub/issues/411): a dedicated continuity artifact from SQLite and a baseline protocol gate over benchmark JSON.

1. Generate continuity artifact from the live DB:

```bash
python3 scripts/ml_detector_continuity_report.py --db app/data/db/birdlense.db --days 14 --out /tmp/detector_continuity_report.v1.json
```

2. Build baseline protocol (`benchmark_track_regen@v1` baseline vs candidate):

```bash
python3 scripts/ml_baseline_protocol.py \
  --baseline-report /tmp/baseline_report.json \
  --candidate-report /tmp/candidate_report.json \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --out /tmp/ml_baseline_protocol.v1.json
```

3. Gate passes when `ml_baseline_protocol@v1` has `ok=true` and `detector_continuity_report@v1` has both `track_gate_ok=true` and `crop_gate_ok=true`.

## 2026-05-02 — Wave 2 / #404 versioned eval dataset

To keep offline benchmark gates (`#407`) reproducible, freeze the eval set as a versioned artifact:

```bash
python3 scripts/ml_build_eval_dataset.py \
  --videos-root app/data/recordings \
  --labels-json /tmp/gold_labels.json \
  --out-dir app/data/eval_datasets
```

Output: `app/data/eval_datasets/<dataset_id>/manifest.json` (+ `gold_labels.json` when labels are provided).  
`manifest.json` stores per-clip `sha256`, size, mtime, and label coverage (`labels_coverage`) so baseline/candidate comparisons run on the same frozen set.

## 2026-05-02 — Wave 3 / #407 offline benchmark gate

Unified detector-first gate runner:

```bash
python3 scripts/ml_offline_benchmark_gate.py \
  --baseline-report /tmp/baseline_report.json \
  --candidate-report /tmp/candidate_report.json \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --out /tmp/offline_benchmark_gate.v1.json
```

The script combines:
- `compare_benchmark_reports` (recall regression checks),
- `ml_baseline_protocol@v1` (quality + continuity),
- `label_eval` sample-size gate.

Final verdict is `offline_benchmark_gate@v1` field `ok`.

## 2026-05-02 — Wave 4 / #405 detector shortlist + license/compliance

Generate shortlist artifact for detector candidates:

```bash
python3 scripts/ml_detector_shortlist.py \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --offline-gate-report /tmp/offline_benchmark_gate.v1.json \
  --out /tmp/detector_shortlist_report.v1.json
```

Artifact `detector_shortlist_report@v1` includes:
- candidates table (quality/latency/openvino/license/risk),
- shortlist (2-3 candidates, excluding `license.status=blocked`),
- `compliance_verdict`,
- dedicated `bird_only_verdict` (`viable` / `not_viable`).

## 2026-05-02 — Wave 5 / #412 OpenVINO async+hints profile

Profile OpenVINO combinations (device + hint + frame_step) on the same clip subset and emit a reproducible artifact:

```bash
python3 scripts/ml_openvino_async_profile.py \
  --videos-root app/data/recordings \
  --max-videos 3 \
  --out /tmp/ov_async_profile_report.v1.json
```

Artifact `ov_async_profile_report@v1` includes:
- per-profile benchmark rows (status, runtime, fused/raw tracks, optional label_eval recall),
- `best_profile` chosen by minimal mean runtime (tie-breakers: recall, then fused track count),
- final `ok=true` when at least one profile completes successfully.

## 2026-05-02 — Wave 6 / #413 decode path benchmark

Compare `opencv` vs `ffmpeg_vaapi` decode/capture paths on the same replay clip:

```bash
python3 scripts/ml_decode_path_benchmark.py \
  --video app/data/file_test/sample.mp4 \
  --frames 300 \
  --out /tmp/decode_path_benchmark.v1.json
```

Artifact `decode_path_benchmark@v1` includes:
- backend rows (`video_decode_resize_benchmark@v1`) for `opencv` and `ffmpeg_vaapi`,
- fps, p95 frame delay, and drop-rate deltas,
- gate `drop_rate_improved_20pct` for Wave 1 quality check.

## 2026-05-02 — Wave 7 / #414 track continuity eval

Build continuity SLO verdict from `detector_continuity_report@v1`:

```bash
python3 scripts/ml_track_continuity_eval.py \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --out /tmp/track_continuity_eval.v1.json
```

Artifact `track_continuity_eval@v1` includes:
- `empty_track_with_detection_rate` (target `<= 1.0%`),
- `track_emit_success_rate` (target `>= 99.5%`),
- explicit gate verdicts per metric + final `ok`.

## 2026-05-02 — Wave 8 / #415 INT8 candidate gate

Evaluate INT8 candidate vs baseline with latency/quality/continuity thresholds:

```bash
python3 scripts/ml_int8_candidate_eval.py \
  --baseline-report /tmp/baseline_report.json \
  --candidate-report /tmp/int8_candidate_report.json \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --out /tmp/int8_candidate_eval.v1.json
```

Artifact `int8_candidate_eval@v1` includes:
- latency improvement ratio (target `>= 20%`),
- quality degradation in pp (target `<= 1 pp`),
- continuity gate status + `go_no_go`,
- rollback instructions for production fallback.

## 2026-05-02 — Wave 9 / #408 shadow rollout candidate

Build shadow gate verdict from 2+ shadow windows (no impact on user path):

```bash
python3 scripts/ml_shadow_rollout_report.py \
  --window-report /tmp/shadow_window_1.json \
  --window-report /tmp/shadow_window_2.json \
  --critical-incidents 0 \
  --out /tmp/shadow_rollout_report.v1.json
```

Artifact `shadow_rollout_report@v1` includes:
- per-window disagreement rates from `label_eval` mismatch,
- runtime incident counter,
- gate verdict (`canary_ready` / `hold`) and final `ok`.

## 2026-05-02 — Wave 10 / #409 canary + auto-stop + rollback drill

Build canary/rollback decision artifact:

```bash
python3 scripts/ml_canary_rollback_report.py \
  --baseline-sli /tmp/baseline_sli.json \
  --canary-sli /tmp/canary_sli.json \
  --rollback-sli /tmp/rollback_sli.json \
  --out /tmp/canary_rollback_report.v1.json
```

Artifact `canary_rollback_report@v1` includes:
- canary latency/error SLO gates,
- rollback restoration gate (`rollback_restores_baseline_sli`),
- auto-stop condition + practical rollback steps in playbook.

## 2026-05-02 — Wave 11 / #410 full rollout 100% + 72h watch

Build final 72h watch report and go/no-go decision:

```bash
python3 scripts/ml_full_rollout_watch_report.py \
  --before-report /tmp/baseline_report.json \
  --after-report /tmp/post_rollout_report.json \
  --watch-window /tmp/watch_d1.json \
  --watch-window /tmp/watch_d2.json \
  --watch-window /tmp/watch_d3.json \
  --out /tmp/full_rollout_watch_report.v1.json
```

Artifact `full_rollout_watch_report@v1` includes:
- before/after quality and runtime deltas,
- per-window SLI checks (p95/error/uptime),
- `go_no_go` verdict + backlog for the next detector iteration.

## 2026-05-02 — Wave 12 / #406 action-model shortlist + MVP recipe

Build action-model shortlist and lock MVP training recipe:

```bash
python3 scripts/ml_action_model_shortlist.py \
  --min-dataset-clips 800 \
  --out /tmp/action_model_shortlist.v1.json
```

Artifact `action_model_shortlist@v1` includes:
- ranked action-model candidates,
- selected MVP model,
- fixed training recipe (`epochs/lr/sampler/loss/metrics`),
- domain-shift risks + mitigation plan.

## 2026-04-28 — documentation sync (roadmap, security, CV/ML index)

| Check | Result |
|-------|--------|
| `python3 scripts/check-docs-version.py` | OK (`VERSION` ↔ `mkdocs.yml`, `app/ui/package.json`, `app/web/openapi.yaml`) |
| `python3 scripts/check_site_map_meta_paths.py` | OK |
| `mkdocs build --strict` | OK |

**Doc updates in repo:** ROADMAP EN/RU — April 2026 backlog labels, Species UI note **v0.3.7+**, registry outcome wording; SECURITY EN/RU — “Last updated” / gitleaks baseline April 2026; docs README EN/RU — row linking GitHub epic [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367); [CV_ML_PREP](./CV_ML_PREP.md) intro ties prep to epic **#367**; [HUB_EPICS_TRACKER](./HUB_EPICS_TRACKER.md) — parallel CV/ML section.

## Offline fusion calibration

1. Export processor decision traces to CSV:

```bash
python3 scripts/export_fusion_training_data.py --out /tmp/fusion_traces.csv --source db
```

2. Evaluate calibration and selective-prediction metrics:

```bash
python3 scripts/eval_fusion_calibration.py --data /tmp/fusion_traces.csv --label-col valid_track_label --slice-field audio_evidence --slice-field decision_kind
```

3. If you have a trained fusion state, add `--model-path app/processor/models/fusion/fusion_state.pt`.

## 2026-04-02 — cleanup, backend tail removal, final polish

| Check | Result |
|-------|--------|
| `python -m pytest tests/test_api.py tests/test_species_registry.py -q` (`app/web`) | 96 passed |
| `npm run build` (`app/ui`) | OK |
| Public `GET /api/ui/health` | `200 {"status":"ok"}` |
| Public `GET /api/ui/status/debug` without auth | `403 {"error":"Password required"}` |
| Public `POST /api/ui/system/species-registry/enrich-metadata` | `404 Not Found` |
| Public `POST /api/ui/system/species-registry/repair-cards` | `404 Not Found` |
| Production catalog diagnostics | duplicate names `0`, classifier/catalog drift `0`, dataset drift `0` |

**Key fixes shipped in repo:**
- Removed dead legacy UI files that previously allowed old dangerous Library controls to survive in the tree.
- Closed the public debug surface behind settings access and removed unused sync species-registry maintenance routes.
- Synced TESTING / CONFIGURATION / ARCHITECTURE docs with the live route behavior and current UI model.

## 2026-03-29 — critical UI fix

| Check | Result |
|-------|--------|
| Prev/next recording on `/videos/:id` | Fixed `ReferenceError` (undefined `listReturnState`); see [CHANGELOG.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) [Unreleased] |
| `make test-web` (Docker, `app/`) | 100 passed |
| `npm run build` (`app/ui`) | OK |

**Manual smoke on hub:** open a clip from Timeline → prev/next → back returns to list; direct URL (no `state`) → stepping still works; browser back follows history.

**Not run here:** scheduled Playwright E2E (daily workflow; see [TESTING](./TESTING.md) §1), full `make docs` unless MkDocs changed.

## 2026-04-01 — stabilization audit and safety hardening

| Check | Result |
|-------|--------|
| `python -m pytest app/web/tests/test_system_stabilization.py app/web/tests/test_security_hardening.py -q` | 12 passed |
| `python -m pytest app/web/tests/test_species_catalog_reconcile.py -q` | 4 passed |
| `npm run build` (`app/ui`) | OK |
| Production `storage/stats` after 2026-03-24 | Files present on disk through 2026-04-01 |
| Production `overview` / `timeline` after 2026-03-24 | No detections / visits after 2026-03-24; archive exists but ingest did not produce `video_species` / `species_visit` |

**Key fixes shipped in repo:**
- Library now reflects real archived recordings and no longer exposes dangerous maintenance flows.
- System maintenance supports honest preview/apply for orphan cleanup and visit time realignment.
- Production safety no longer allows empty-password bootstrap for settings/system access.
- Species merge preserves missing metadata on the surviving catalog row.
- Overview includes visits that overlap the selected day, including cross-midnight cases.

**Operator interpretation for the live hub:** if a day is highlighted in Library but empty in Overview or Timeline, recordings exist on disk but detections were not stored for that day. This is now easier to diagnose without mixing archive visibility and DB maintenance in one screen.

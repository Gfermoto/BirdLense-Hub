# Runbook оператора

## Ежедневные проверки

```bash
# Health
make verify

# Логи
make logs

# GPU
docker exec birdlense nvidia-smi
```

## Еженедельно

```bash
# Проверить свободное место
df -h /app/data

# Очистить старые записи (через веб-UI)
```

3. Verify `PROCESSOR_SECRET` is a real value in `app/.env`, not a literal placeholder.

## Frigate saw event, Hub did not persist clip/visit

1. Fix the incident window first: camera id + local time (MSK) + Frigate event/clip reference.
2. Collect Hub evidence in a narrow window (`T-2m .. T+2m`): processor logs, recording file state, and `/api/ui/system/ml-runtime`.
3. For maintainers, classify with a single reason code and standard report template:
   [Hub incident protocol](../contributor/hub-incident-protocol.md).
4. If root cause is unknown, do not tune thresholds yet; first complete missing evidence from the protocol checklist.

## PT detector canary (low-resolution stream)

Use this when you want to validate PyTorch detector weights (`.pt`) against the current backend without a full rollout.

1. **Freeze baseline (24h)** on current config:
   - `domain-health` snapshot
   - Frigate-vs-Hub mismatch count
   - recording artifact failures (`ingest_gate` reason codes)
   - processing guardrails (p95 detect latency + CPU)
2. **Enable PT canary** on one camera/time window:
   - set detector backend to PT (`processor.inference_backend: torch`)
   - keep stream low-resolution and leave all other thresholds unchanged
   - keep rollback-ready copy of previous config.
3. **Run canary for 24h** and compare to baseline:
   - mismatch rate vs Frigate
   - playable artifact rate
   - `FUSION_*` / `REC_FILE_*` reason-code distribution
   - latency and CPU guardrails.
4. **Go / no-go decision**:
   - **go**: mismatch not worse than baseline and no guardrail regression
   - **no-go**: mismatch worsens or guardrails regress -> rollback immediately.
5. **Rollback**:
   - restore previous backend/config
   - restart stack
   - re-run `make verify` and capture post-rollback `domain-health`.

## Weekly reliability KPI review and decision log

Use this cadence to keep reliability work continuous and auditable.

Cadence and owner:

- run every week (same weekday/time)
- assign one incident owner for KPI review and follow-up issue creation
- use last 7 days for trend and last 24h for acute alerts.

Data source and capture:

1. Fetch `GET /api/ui/system/domain-health`.
2. Record KPI snapshot in one shared issue comment (or ops note) using this minimum set:
   - `parity_mismatch_rate_24h`
   - `parity_mismatched_windows_24h`
   - `recording_artifact_failures_24h`
   - `video_encoding_transitions_24h`
   - `ingest_gate_reason_code_counts_24h` (top causes)
3. Add camera/day-night diagnostics:
   - `parity_camera_split_24h`
   - `parity_hotspots_24h` (high-volume cameras with elevated mismatch rate)
4. Verify guardrails:
   - `strict_quality.strict_quality_ready`
   - p95 detect latency + CPU from runtime diagnostics.

Decision rules:

- if mismatch trend worsens week-over-week, create follow-up issue and assign owner
- if `recording_artifact_failures_24h > 0`, open P1 incident immediately
- if `parity_hotspot_count_24h > 0`, open/refresh camera-focused follow-up issue per hotspot
- if `video_encoding_flapping` alert is true, lock config changes and investigate runtime transitions before next deploy.

Decision log template:

```markdown
### Reliability weekly review — YYYY-MM-DD
- Reviewer: <name>
- Window: <start>.. <end>
- KPI snapshot:
  - parity_mismatch_rate_24h: <value>
  - parity_mismatched_windows_24h: <value>
  - recording_artifact_failures_24h: <value>
  - video_encoding_transitions_24h: <value>
  - top_mismatch_causes: <reason_code:count, ...>
- Camera split highlights:
  - <camera>: mismatch=<x/y>, day=<a/b>, night=<c/d>
- Decisions:
  - <keep / rollback / tune / investigate>
- Follow-up issues:
  - #<id> <title> (owner: <name>, due: <date>)
```

## Weekly SOTA reality check (mandatory while #666 is open)

Use this ritual until acceptance epic [#666](https://github.com/Gfermoto/BirdLense-Hub/issues/666) is closed.
(Replaces closed [#517](https://github.com/Gfermoto/BirdLense-Hub/issues/517).)

1. Generate/refresh artifacts:
   - `docs/reports/error_budget_gate/error_budget_gate_latest.json`
   - `docs/reports/golden_set_gate/golden_set_gate_latest.json`
   - `docs/reports/quality_outcome/quality_outcome_metrics_latest.json`
   - `docs/reports/sota_reality/sota_reality_check_latest.md`
   - `docs/reports/sota_reality/sota_consilium_baseline_*.json` (Orin funnel + named_share)
2. Validate acceptance SLO (24h window) — **Hub-first**:
   - `yolo_blind_confirmed` ≤ 0.15 per camera
   - `db_persist_success` ≥ 0.90 among sessions with tracks
   - **`visit_quality.named_share_hub` ≥ 0.40** among Hub (non-Frigate) persisted rows
   - mixed `named_share` / `frigate_agreement` are **informative only** (Frigate may be absent)
   - `classifier_finalize_outcome` present in session summaries
    - detector golden must pass **without MQTT/Frigate** (`make validate-detector-golden`; alias `validate-pipeline-golden`)
    - taxonomy / species golden must pass Hub-only cases (`make validate-species-golden`) — track stubs alone are not a species pass
3. Confirm no skipped critical ML gates (unless explicit override ticket is attached).
4. Attach one weekly comment to [#666](https://github.com/Gfermoto/BirdLense-Hub/issues/666) with:
   - outcome metrics trend (blind_rate, tracks_coverage, **named_share_hub**, empty_bbox_rate),
   - Hub-only vs Frigate-assisted split,
   - backend+ui parity verification notes,
   - decision (`hold` / `go` / `rollback`) and linked issues.

Hard rule: do **not** enable `detection.frigate_species_authority` to pass SOTA go.
Frigate is an optional prior; Hub must meet SLOs with YOLO+classifier alone.

Hard rule: `warning` error budget state does not pass release check without override reason containing issue token (`#<id>`).

## Slow frame processing in logs (`Slow frame processing: … ms >= … ms`)

Symptom: processor log or FPS summary shows **YOLO / frame pipeline** taking longer than `processor.frame_processing_warn_ms` (default **450** ms). High-resolution video + NVDEC/NVENC still has a hard latency budget.

1. **System → Configuration audit** — check **Processor runtime (diagnostics)** for `slow_frame_processor_detect_total` and detect **p95** vs your warn threshold (driven by `data/diagnostics/processor_runtime_stats.json`).
2. **Settings → Processor → Models & scope** — reduce **`processor.binary_imgsz`** (try **640**, then **512**) so the binary pass is cheaper; re-save settings and watch logs.
3. If logs are **noisy but UX is fine**, raise **`processor.frame_processing_warn_ms`** (this does **not** speed up inference; it only reduces warning spam).
4. **Light gate / night** — if many frames are skipped before YOLO, revisit `processor.light_gate_*` and night overrides (recall vs CPU load).
5. **GPU (Orin)** — confirm the container uses NVIDIA runtime: `docker logs birdlense` for NVENC / GStreamer lines; on the host, `nvidia-smi`. If GPU is missing, you are on CPU-only.

Related: [PROCESSOR_PERFORMANCE](./processor-performance.md) (resolution × `binary_imgsz` guidance), [CONFIGURATION](./configuration.md) (`processor.*`, `detection.*`), [RELEASE_READINESS](https://github.com/Gfermoto/BirdLense-Hub/blob/main/release-readiness.md). Release gate: DEFINITION_OF_DONE (archived).

## Install or deploy verification fails on readiness

Readiness currently checks:

- database query path
- `data/` directory exists and is writable
- `app_config/` directory exists and is writable

Typical fixes:

- recreate bind-mounted folders under `app/data` and `app/app_config`
- fix ownership (`uid 1000`) or host filesystem permissions
- inspect DB path / volume mount under `DATA_DIR`

## Legacy keys in config-audit (gallery / Heimdall)

If `GET /api/ui/system/config-audit` still lists deprecated keys such as `gallery.*` or `general.heimdall_url`, they are coming from **`app/app_config/user_config.yaml`** on the hub (the UI never returns real secrets, so you cannot “copy” them out for cleanup).

The same script also drops `integrations.scales.mqtt_topic`, `mqtt_bird_present_topic`, and `mqtt_command_topic` when they are explicitly set to `""` in YAML, because that overrides topic derivation from `mqtt_topic_prefix` (shows up as warnings in the configuration audit).

On the server (adjust paths to your deploy directory):

```bash
git pull
cd app && make build && make stop && make start
```

## Деплой на удалённый Orin

```bash
# 1. Проверить deploy.local.sh
# 2. Запустить
make deploy
```

## Полная перезагрузка стека

```bash
cd app
make stop
docker system prune -f
make build && make start
```

## Бэкапы

```bash
# БД
cp app/data/db/birdlense.db app/data/db/birdlense.db.bak.$(date +%Y%m%d)

# Конфиг (автоматически)
# user_config.yaml.bak.* создаётся при изменении
```

См. [`../RUNBOOKS.md`](../RUNBOOKS.md) · [`troubleshooting.md`](troubleshooting.md).
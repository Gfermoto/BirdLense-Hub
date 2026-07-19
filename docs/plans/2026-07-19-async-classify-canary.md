# Async classify patch — Orin canary plan (2026-07-19)

Flag: `processor.async_classify_patch_enabled` (default **false**).  
Second budget: `processor.async_classify_patch_max_runtime_ms` (default 4000).

## Goal

After persist, reclassify budget/timeout leftovers and PATCH visit species
**without** `manually_corrected`, without blocking finalize critical path.

## Preconditions

- Stack healthy: `make verify`
- Hub-only taxonomy SoT (Frigate not species authority)
- Metrics scraped (Prometheus / activity_log)
- Operator can docker-restart `birdlense` quickly

## Enable (canary — one session window)

On Orin host only, in `app/app_config/user_config.yaml` (backup first):

```yaml
processor:
  async_classify_patch_enabled: true
  async_classify_patch_max_runtime_ms: 3000   # start conservative
```

Then:

```bash
# backup
cp -a app/app_config/user_config.yaml "app/app_config/user_config.yaml.bak.$(date +%Y%m%d)_async_canary"
docker compose -f app/docker-compose.orin.yml up -d --force-recreate birdlense
make verify
```

Do **not** enable via git defaults until canary green ≥24h.

## Observe (30–60 min)

| Signal | Where | Expect |
|--------|--------|--------|
| `async_classify_patch: queued` | `docker logs birdlense` | after busy multi-track sessions |
| `async_classify_patch_applied_total` | metrics | >0 if named leftovers found |
| `async_classify_patch_stub_total` | metrics | leftovers with no named fill |
| YOLO/ORT errors / GPU OOM | logs + `nvidia-smi` | none / no spike stalling live detect |
| finalize p95 | readiness funnel / session_summary | not worse than baseline |
| `recognition_stack` | session_summary | present; authority=hub |

## Abort / rollback

```bash
# restore backup
cp -a app/app_config/user_config.yaml.bak.*_async_canary app/app_config/user_config.yaml
# or set async_classify_patch_enabled: false
docker compose -f app/docker-compose.orin.yml up -d --force-recreate birdlense
make verify
```

Abort if: live detect stalls, OOM, enrich wrong species on manually-corrected rows
(should skip — verify), or finalize critical path regresses >20%.

## Success → next

1. Keep canary 24h
2. Raise `async_classify_patch_max_runtime_ms` toward 4000 if GPU headroom
3. Only then consider default-on for hub_only profile (separate PR)

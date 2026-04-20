# Operations runbooks — BirdLense Hub

[Русский](./RUNBOOKS.ru.md)

Short operator playbooks for the most common failures.

## Install succeeded, but UI does not open

1. From the repository root run `make verify`.
2. If `health` fails, inspect container state: `cd app && docker compose ps && docker compose logs --tail=100 birdlense`.
3. If Docker built successfully but the port is busy, override `BIRDLENSE_PORT` or add `docker-compose.override.yml` as shown in [LOCAL_DEV](./LOCAL_DEV.md).

## `/api/ui/health` is OK, but deploy is still not trustworthy

Use `BASE_URL=http://YOUR_HOST:8085 make verify` or `scripts/verify-stack.sh --base-url ...`.

Interpretation:

- `health` OK, `readiness` FAIL: web process is alive, but DB or writable directories are broken.
- `readiness` OK, `status` degraded: the core hub is ready, but optional integrations like processor/video/MQTT still need attention.

If settings are open or you have admin access, also check:

- `GET /api/ui/system/domain-health`
- `GET /api/ui/system/species-registry/health`

For scripted checks on a locked hub, pass `BIRDLENSE_UI_API_KEY` and run
`REQUIRE_SETTINGS_HEALTH=1 BASE_URL=... ./scripts/verify-release.sh`.

For `scripts/verify-stack.sh`, add `--check-domain-health` when you also set `BIRDLENSE_UI_API_KEY` (or `UI_API_KEY`) so domain and registry endpoints can authenticate.

GitHub Actions deploy: optional repository secret **`BIRDLENSE_UI_API_KEY`** (match server `app/.env`) turns on domain-health checks in the Verify step — see [RELEASE_READINESS](./RELEASE_READINESS.md).

Release checklist: [RELEASE_READINESS](./RELEASE_READINESS.md).

## Deploy finished, but the browser shows stale UI

1. Hard-reload the page.
2. Clear PWA / Service Worker cache in the browser.
3. Re-run `make verify` against the deployed `BASE_URL`.

## API works, but processor / detections are missing

1. Check `/api/ui/status` and System → readiness / logs.
2. Inspect processor logs:

```bash
ssh YOUR_SSH_HOST "tail -100 YOUR_REMOTE_DIR/app/data/processor.log"
```

3. Verify `PROCESSOR_SECRET` is a real value in `app/.env`, not a literal placeholder.

## Slow frame processing in logs (`Slow frame processing: … ms >= … ms`)

Symptom: processor log or FPS summary shows **YOLO / frame pipeline** taking longer than `processor.frame_processing_warn_ms` (default **450** ms). High-resolution video + VA-API still has a hard latency budget.

1. **System → Configuration audit** — check **Processor runtime (diagnostics)** for `slow_frame_processor_detect_total` and detect **p95** vs your warn threshold (driven by `data/diagnostics/processor_runtime_stats.json`).
2. **Settings → Processor → Models & scope** — reduce **`processor.binary_imgsz`** (try **640**, then **512**) so the binary pass is cheaper; re-save settings and watch logs.
3. If logs are **noisy but UX is fine**, raise **`processor.frame_processing_warn_ms`** (this does **not** speed up inference; it only reduces warning spam).
4. **Light gate / night** — if many frames are skipped before YOLO, revisit `processor.light_gate_*` and night overrides (recall vs CPU load).
5. **GPU / VA-API on the VPS** — confirm the container actually uses the expected path: `docker logs birdlense` for VA-API / FFmpeg lines; on the host, `intel_gpu_top` / `vainfo` where applicable. If GPU is missing, you are on CPU-only inference — expect slow frames at high resolution.

Related: [CONFIGURATION](./CONFIGURATION.md) (`processor.*`, `detection.*`), [RELEASE_READINESS](./RELEASE_READINESS.md). Release gate: [DEFINITION_OF_DONE](./DEFINITION_OF_DONE.md).

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
cd /root/BirdLense
python3 scripts/prune_deprecated_user_config.py --path app/app_config/user_config.yaml --dry-run
python3 scripts/prune_deprecated_user_config.py --path app/app_config/user_config.yaml
cd app && docker compose restart birdlense
```

The script writes `user_config.yaml.bak` next to the file before replacing it. See also [SECRETS_ROTATION](./SECRETS_ROTATION.md).

## MCP smoke check (Bearer token)

Use the **same** secret as on the hub: `MCP_TOKEN` in `app/.env` (or `mcp.token` in UI, not the masked `***`).

```bash
export MCP_TOKEN='your-token-from-server-env'
./scripts/verify-mcp.sh https://YOUR_HOST/
```

Details: [MCP_SETUP](./MCP_SETUP.md).

## Request-level debugging

Every API response now includes `X-Request-ID`.

Use it to correlate browser failures with server logs:

1. Reproduce the failing request in the browser or `curl`.
2. Copy the `X-Request-ID` response header.
3. Search logs for the same request id in `docker logs birdlense`.

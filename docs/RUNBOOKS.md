# Operations runbooks — BirdLense Hub

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

## Install or deploy verification fails on readiness

Readiness currently checks:

- database query path
- `data/` directory exists and is writable
- `app_config/` directory exists and is writable

Typical fixes:

- recreate bind-mounted folders under `app/data` and `app/app_config`
- fix ownership (`uid 1000`) or host filesystem permissions
- inspect DB path / volume mount under `DATA_DIR`

## Request-level debugging

Every API response now includes `X-Request-ID`.

Use it to correlate browser failures with server logs:

1. Reproduce the failing request in the browser or `curl`.
2. Copy the `X-Request-ID` response header.
3. Search logs for the same request id in `docker logs birdlense`.

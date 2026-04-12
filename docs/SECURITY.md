# BirdLense Hub Security Analysis

[Русский](./SECURITY.ru.md)

---

> Last updated: March 2026

## Summary

| Priority | Count | Actions |
|----------|-------|---------|
| Critical | 5 | Path traversal, default auth, secrets in API |
| High | 8 | Secret storage, rate limiting, Docker root |
| Medium | 9 | Session timeout, CORS, dependencies |
| Low | 6 | Documentation, migrations |

**Automated scanning:** GitHub CodeQL runs in CI (Python + TypeScript UI). See [CODEQL.md](./CODEQL.md).

---

## 1. Authentication and Authorization

| Risk | Description | Recommendation |
|------|--------------|----------------|
| ~~**Critical**~~ **Mitigated (opt-in)** | `/api/ui/*` open by default for home LAN. | Set **`BIRDLENSE_STRICT_API_AUTH=1`** with production runtime: require session (after `verify-password`), **`BIRDLENSE_UI_API_KEY`** (`X-Birdlense-Api-Key` or Bearer), or **MCP Bearer**. Bootstrap: `health`, `requires-password`, `check-access`, `verify-password`, `vapid-public`, `logout`. See [CONFIGURATION](./CONFIGURATION.md). |
| ~~**Critical**~~ **Fixed** | `PROCESSOR_SECRET` not set — Processor API was open. | In production, blocks when empty. Deploy writes to `.env`. |
| **Critical** | MCP has no authentication when `mcp.token` and `MCP_TOKEN` are empty. | Set `MCP_TOKEN` when `mcp.enabled=true`. |
| **High** | Settings password (`settings_password`) is optional. When empty — settings and system operations are unprotected. | Require password in production. |
| ~~**High**~~ **Fixed** | Settings session had no idle timeout. | `general.session_idle_minutes` (default 30; `0` disables). See [CONFIGURATION](./CONFIGURATION.md). |
| **Medium** | Endpoints `/api/ui/system/*` (logs, metrics, purge, scan) protected only by `settings_check_access()`. | Ensure mandatory `settings_password`. |

---

## 2. Secrets

| Risk | Description | Recommendation |
|------|--------------|----------------|
| ~~**Critical**~~ **Fixed** | Default `FLASK_SECRET_KEY`. | In `BIRDLENSE_ENV=production` env is required, else RuntimeError. Deploy writes to `.env`. |
| ~~**Critical**~~ **Fixed** | `GET /api/ui/settings` returned full config with secrets. | Secrets are masked (`***`), placeholder on save does not overwrite real value. |
| **High** | `user_config.yaml` stores secrets in plain text: `telegram_bot_token`, `mqtt.password`, `secrets.openweather_api_key`, `homeassistant.token`, `settings_password`, `mcp.token`. | Prefer **`BIRDLENSE_*` env overlays** (see [CONFIGURATION](./CONFIGURATION.md)) or a secret manager; avoid persisting secrets in YAML in production. |
| **High** | OpenAPI describes `telegram_bot_token`, `secrets.openweather_api_key` in Settings schema. | Add `x-sensitive: true`, do not expose in examples. |
| ~~**Medium**~~ **Mitigated** | `settings_password` / `contributor_password` historically plain text. | New saves from UI use **bcrypt**; legacy plaintext still verifies; optional **`BIRDLENSE_SETTINGS_PASSWORD`** / **`BIRDLENSE_CONTRIBUTOR_PASSWORD`** override at runtime. |
| **Low** | `.env` in `.gitignore`, deploy script does not commit it. | Keep as is. |

**Operator runbook:** [SECRETS_ROTATION.md](./SECRETS_ROTATION.md) — full inventory, rotation steps, verification, rollback, emergency note template ([issue #119](https://github.com/Gfermoto/BirdLense-Hub/issues/119)).

---

## 3. Path Traversal (nginx)

| Risk | Description | Recommendation |
|------|--------------|----------------|
| ~~**Critical**~~ **Fixed** | `location /data/` with `alias /app/data/` — request `/data/../.env` could read `/app/.env`. | Added check `if ($request_uri ~* "\.\.") { return 403; }` in all nginx configs. |
| **High** | `/data/recordings/` accessible without authentication. Path `YYYY/MM/DD/HHMMSS/video.mp4` is predictable. | Add access check via API with auth or restrict by IP. |

**Mitigations (pick one for production exposure):** (1) **IP allowlist** — more specific `location ^~ /data/recordings/` with `allow`/`deny` (see `app/nginx/examples/recordings_allowlist.conf.snippet` and [DEPLOY_SERVER.md §8](./DEPLOY_SERVER.md)); (2) **no direct nginx media** — reverse proxy only passes `/api/…` and authenticated stream routes; (3) **`auth_request`** to the Hub session endpoint — advanced, not shipped by default.

**Test:** `curl -I "http://YOUR_HOST:8085/data/../.env"` — if vulnerable, returns 200.

---

## 4. API

| Risk | Description | Recommendation |
|------|--------------|----------------|
| **High** | No rate limiting. | Add Flask-Limiter or similar. |
| **Medium** | CORS: `supports_credentials: True`; allowlist from `CORS_LOCAL_DEV_ORIGINS` (default local dev), `CORS_DEFAULT_ORIGINS`, `CORS_ORIGINS`. | Document CORS for external access; set `CORS_LOCAL_DEV_ORIGINS` empty to drop built-in local origins. |
| **Medium** | Input validation is partial. | Extend validation (schemas, sizes) for mutating endpoints. |
| ~~**Medium**~~ **Fixed** | `X-Real-IP` / `X-Forwarded-For` were trusted without a trusted proxy boundary. | Proxy headers are used only when `TRUSTED_PROXY=1`; otherwise rate limiting uses `remote_addr`. |
| ~~**Medium**~~ **Fixed** | Web Push subscription could enable `web_push.enabled` without settings access. | `POST /api/ui/push/subscribe` now requires `settings_check_access()`. |
| ~~**High**~~ **Fixed** | `webhook.url` could target loopback / private IPs and be abused as SSRF. | Only public `http`/`https` targets are allowed; private ranges are blocked. |

---

## 5. Database

| Risk | Description | Recommendation |
|------|--------------|----------------|
| **Low** | SQLAlchemy ORM, parameterized queries. | Continue using ORM. |
| **Low** | SQLite: `app/data/db/birdlense.db`, not exposed. | Keep as is. |
| **Medium** | Migrations in `app.py` — static strings. | Use Alembic. |

---

## 6. File System

| Risk | Description | Recommendation |
|------|--------------|----------------|
| **Medium** | `scan_recordings` checks `year.isdigit()`, regex for timestamp. | Additionally verify path stays inside `recordings_dir()`. |
| **Low** | `processor_routes.py`: `VIDEO_PATH_RE` strictly limits `video_path`. | Keep as is. |

---

## 7. Network

| Risk | Description | Recommendation |
|------|--------------|----------------|
| **Medium** | Port 8085 exposed. | Use reverse proxy (nginx/traefik) with TLS. |
| **Low** | Gunicorn — 127.0.0.1:8000, MCP — 127.0.0.1:8001. External access only via nginx. | Keep as is. |

---

## 8. Dependencies

| Risk | Description | Recommendation |
|------|--------------|----------------|
| **Medium** | Vulnerabilities not checked automatically. | Regularly: `pip audit`, `safety check`, `npm audit`. |
| **Low** | Versions in requirements.txt pinned. | Update based on audit results. |

---

## 8.1 Git history secret scan (maintainer hygiene)

- Command: `bash scripts/security/scan_git_history_secrets.sh`
- Tool: Gitleaks in Docker image `zricethezav/gitleaks:latest`
- Report path: `.artifacts/gitleaks-history.json`

Current baseline (Mar 2026): scan of full git history completed with **no leaks found**.

---

## 9. Docker

| Risk | Description | Recommendation |
|------|--------------|----------------|
| ~~**High**~~ **Fixed** | Container processes ran as root. | Nginx/Gunicorn/processor run as `birdlense` (**uid 1000**); entrypoint briefly runs as root to `chown` bind-mounted `./data` and `./app_config`. See [INSTALL](./INSTALL.md). |
| **Medium** | Base image `ultralytics/ultralytics` — heavy. | Consider multi-stage with minimal runtime. |
| **Low** | No `--privileged`, `--cap-add`. | Do not add. |

---

## 10. Configuration

| Risk | Description | Recommendation |
|------|--------------|----------------|
| **High** | `user_config.yaml` contains sensitive fields. | Store in env or secret manager. |
| **Low** | `deploy.sh` excludes `user_config.yaml` on sync. | Keep as is. |

---

## Quick Steps for Production

1. ~~**Set secrets**~~ ✅ Deploy via `deploy.local.sh` writes `PROCESSOR_SECRET`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV=production`.
2. **Settings password:** set `general.settings_password`.
3. ~~**Path traversal**~~ ✅ Nginx: block `\.\.`, `%2e%2e`. `image_path` in notify: `_is_safe_image_path`.
4. **Restrict access** to `/data/recordings/` (auth or IP).
5. ~~**Rate limiting**~~ ✅ `POST /api/ui/settings/verify-password`: **5** failed attempts per **60** s per client IP → **429** + `Retry-After`; success clears the counter. IP from `X-Real-IP` / `X-Forwarded-For` behind nginx — see [ACCESS_CONTROL](./ACCESS_CONTROL.md).
6. ~~**Docker:** run as non-privileged user.~~ ✅ Processes use uid 1000 (`birdlense`).
7. ~~**Mask secrets**~~ ✅ `GET /api/ui/settings` returns `***` for sensitive fields.
8. **Secret rotation:** follow [SECRETS_ROTATION.md](./SECRETS_ROTATION.md) (prod ops).

---

## Contact

To report a vulnerability, create a GitHub Security Advisory or contact the maintainers. See [Security policy](./project/security-policy.md) in the repository root.

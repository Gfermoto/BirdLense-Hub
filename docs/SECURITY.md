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
| **Critical** | API has no authentication by default. Endpoints `/api/ui/*` are accessible without checks. | Add mandatory auth for production (API key, JWT, or reverse proxy with auth). |
| ~~**Critical**~~ **Fixed** | `PROCESSOR_SECRET` not set — Processor API was open. | In production, blocks when empty. Deploy writes to `.env`. |
| **Critical** | MCP has no authentication when `mcp.token` and `MCP_TOKEN` are empty. | Set `MCP_TOKEN` when `mcp.enabled=true`. |
| **High** | Settings password (`settings_password`) is optional. When empty — settings and system operations are unprotected. | Require password in production. |
| **High** | Settings session: `session.permanent = True`, no timeout. | Add session timeout (15–30 min). |
| **Medium** | Endpoints `/api/ui/system/*` (logs, metrics, purge, scan) protected only by `settings_check_access()`. | Ensure mandatory `settings_password`. |

---

## 2. Secrets

| Risk | Description | Recommendation |
|------|--------------|----------------|
| ~~**Critical**~~ **Fixed** | Default `FLASK_SECRET_KEY`. | In `BIRDLENSE_ENV=production` env is required, else RuntimeError. Deploy writes to `.env`. |
| ~~**Critical**~~ **Fixed** | `GET /api/ui/settings` returned full config with secrets. | Secrets are masked (`***`), placeholder on save does not overwrite real value. |
| **High** | `user_config.yaml` stores secrets in plain text: `telegram_bot_token`, `mqtt.password`, `secrets.openweather_api_key`, `weather.ha_token`, `settings_password`, `mcp.token`. | Store in env or secret manager; do not write to YAML. |
| **High** | OpenAPI describes `telegram_bot_token`, `secrets.openweather_api_key` in Settings schema. | Add `x-sensitive: true`, do not expose in examples. |
| **Medium** | `settings_password` in plain text. In default_config: *"Consider hashing for production"*. | Store hash (bcrypt/argon2). |
| **Low** | `.env` in `.gitignore`, deploy script does not commit it. | Keep as is. |

**Operator runbook:** [SECRETS_ROTATION.md](./SECRETS_ROTATION.md) — full inventory, rotation steps, verification, rollback, emergency note template ([issue #119](https://github.com/Gfermoto/BirdLense-Hub/issues/119)).

---

## 3. Path Traversal (nginx)

| Risk | Description | Recommendation |
|------|--------------|----------------|
| ~~**Critical**~~ **Fixed** | `location /data/` with `alias /app/data/` — request `/data/../.env` could read `/app/.env`. | Added check `if ($request_uri ~* "\.\.") { return 403; }` in all nginx configs. |
| **High** | `/data/recordings/` accessible without authentication. Path `YYYY/MM/DD/HHMMSS/video.mp4` is predictable. | Add access check via API with auth or restrict by IP. |

**Test:** `curl -I "http://YOUR_HOST:8085/data/../.env"` — if vulnerable, returns 200.

---

## 4. API

| Risk | Description | Recommendation |
|------|--------------|----------------|
| **High** | No rate limiting. | Add Flask-Limiter or similar. |
| **Medium** | CORS: `supports_credentials: True`, origins via `CORS_ORIGINS`. When empty — localhost only. | Document CORS setup for external access. |
| **Medium** | Input validation is partial. | Extend validation (schemas, sizes) for mutating endpoints. |

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
| **High** | Container runs as root (no `USER` in Dockerfile). | Add non-privileged user and `USER`. |
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
6. **Docker:** run container as non-privileged user.
7. ~~**Mask secrets**~~ ✅ `GET /api/ui/settings` returns `***` for sensitive fields.
8. **Secret rotation:** follow [SECRETS_ROTATION.md](./SECRETS_ROTATION.md) (prod ops).

---

## Contact

To report a vulnerability, create a GitHub Security Advisory or contact the maintainers. See [Security policy](./project/security-policy.md) in the repository root.

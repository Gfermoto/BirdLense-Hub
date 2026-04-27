# Wave 4: security and production-readiness

| Area | Verdict | Notes |
|---|---|---|
| API auth | CONDITIONAL PASS | Admin/contributor guards exist; production-wide /api/ui gate is available via BIRDLENSE_STRICT_API_AUTH; must be enabled in prod. |
| CSRF | HIGH RISK | Cookie/session-auth mutation endpoints do not show explicit CSRF token enforcement; rely on SameSite/browser behavior and passwords/API keys. Add CSRF token for state-changing UI requests or require API key in strict prod. |
| CORS | PASS WITH CONFIG RISK | No default wildcard in production; CORS_ORIGINS/env can add origins. Need deploy check that CORS_ORIGINS never contains * with credentials. |
| Secrets/env | PASS WITH CONFIG RISK | FLASK_SECRET_KEY required in production; deploy generates PROCESSOR_SECRET/FLASK_SECRET_KEY. Real app/.env exists locally and is gitignored; do not commit artifacts with secret scan details. |
| HTTPS redirects | MANUAL/OPS | Application container serves HTTP behind nginx/reverse proxy; HTTPS redirect is expected at outer proxy/VPS, not enforceable from this code audit. |
| SQL injection | PASS WITH REVIEW NOTES | SQLAlchemy used; raw/admin SQL areas require continued review. No automated critical SQLi finding in this pass. |
| Error logging | PASS | Global /api/* 500 handler returns generic JSON and logs stack server-side. |
| Package metadata | UI PASS / APP N/A | UI package has engines/build/test/lint; root app is Docker-first, no Node start script expected outside UI. |
| Docker runtime | PASS WITH HARDENING TODO | Container creates non-root birdlense user; starts via root entrypoint for volume chown/nginx setup. Consider explicit security_opt/read_only/cap_drop in compose later. |
| Dependency vulnerabilities | PASS AFTER AUTOFIX | npm audit moderate postcss fixed; pip-audit clean except documented ignored py vulnerability. |

## Required production environment gates
- `BIRDLENSE_ENV=production`
- `FLASK_SECRET_KEY` non-empty
- `PROCESSOR_SECRET` non-empty
- `BIRDLENSE_STRICT_API_AUTH=1`
- `BIRDLENSE_UI_API_KEY` or UI session flow for automation
- `MCP_TOKEN` if MCP enabled
- `TRUSTED_PROXY=1` only when Gunicorn is reachable only from nginx/reverse proxy
- HTTPS/TLS and redirect at outer proxy/VPS

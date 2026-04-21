# API error shape & security checklist (UI contract)

[Русский](./API_ERRORS.ru.md)

Lightweight guide for **new** `/api/ui/*` routes: what the SPA expects and where to document exceptions.

## Common JSON shapes

| Pattern | Example | Typical HTTP | Where |
|---------|---------|----------------|--------|
| Plain error string | `{ "error": "Not found" }` | 4xx / 5xx | Many legacy handlers, feed actions |
| Success wrapper | `{ "ok": true, ... }` | 200 | Some maintenance endpoints |
| Structured validation | Problem details or `{ "errors": { "field": "..." } }` | 400 | Prefer for new forms |

**Rule of thumb for new routes:** return a **stable machine key** (`code` or `error_code`) **plus** a human string; let the client map to i18n when needed. Document the shape in [OpenAPI](./project/openapi.md) / Redoc.

## OpenAPI

Regenerate TypeScript after spec edits: `npm run codegen:openapi` in `app/ui`. CI fails on drift (`openapi-types.ts`).

## Security baseline (hub repo)

| Check | Location / action |
|-------|-------------------|
| **Bandit** + **pip-audit** | `make ci-local` / `scripts/ci-full-local.sh`; pip-audit ignore `PYSEC-2022-42969` is documented in [CI_AND_QUALITY](./CI_AND_QUALITY.md). |
| **Secrets** | Never commit real `.env`; use `app/.env.example` and deploy templates. |
| **CORS** | Production `CORS_ORIGINS` / public URL — [DEPLOY_SERVER](./DEPLOY_SERVER.md) and operator runbooks. |

Tracking: [BirdLense-Hub#331](https://github.com/Gfermoto/BirdLense-Hub/issues/331).

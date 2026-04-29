# BirdLense Hub — Agent Instructions

## Critical Requirements

- **Node.js 22** only — check `app/ui/.nvmrc`. Engine in `package.json` enforces `>=22.0.0 <23`. Do NOT guess Node versions.
- **Python 3.11** in container (Ultralytics base image), **3.12** for MkDocs docs.
- **PYTHONPATH issue**: If set in environment, may break venv imports. Unset before pip/pytest.
- **UI build BEFORE Docker**: `cd app/ui && npm run build && cd .. && docker compose build`

## Key Commands

| Command | What it does |
|---------|-------------|
| `make ci-local` | Full CI without Docker (Bandit, pip-audit, Ruff, pytest web, UI, docs). Source of truth. |
| `make ci-local-docker` | Same + Docker image build, `make test`, Playwright smoke |
| `make test-web-contract-local` | Fast OpenAPI contract check on host (no Docker) |
| `cd app && make test` | Processor unit tests (needs weights) |
| `cd app && make test-web` | Web API pytest (needs Docker image) |
| `cd app && make test-web-local` | Web API pytest on host (needs venv, no Docker) |
| `cd app && make test-processor-light` | Skip heavy YOLO tests (`SKIP_HEAVY_PROCESSOR_TESTS=1`) |
| `npm run codegen:openapi` | Generate TS types from `web/openapi.yaml` (run in `app/ui/`) |
| `npm run typecheck` | TypeScript check in UI |
| `npm run lint` | ESLint in UI |
| `npm run test` | Vitest in UI |

## Architecture

```
app/
├── web/           # Flask API (OpenAPI in openapi.yaml)
├── processor/     # YOLO detection + classification
├── ui/            # React 19 + MUI (Node 22)
├── data/          # recordings/, db/
└── app_config/   # user_config.yaml

docs/              # MkDocs site
scripts/          # ci-full-local.sh, deploy.sh, etc.
```

**Entry points**:
- API: `app/web/openapi.yaml` (authoritative contract)
- UI: `app/ui/src/App.tsx`
- Processor: `app/processor/src/`

## Testing Guidelines

- **Web contract**: Run `npm run codegen:openapi` then diff `src/generated/openapi-types.ts`
- **Heavy tests**: Processor loads YOLO — needs ≥8GB RAM, may OOM on small VPS (exit 137)
- **PYTHONPATH**: Must be unset or point to app/ subdirs for correct imports
- **E2E**: Requires live stack (`cd app && make start`), optional `E2E_SETTINGS_PASSWORD`

## Cursor Rules (exist, respect)

- `.cursor/rules/frontend-ui.mdc`
- `.cursor/rules/backend-web.mdc`
- `.cursor/rules/processor-python.mdc`
- `.cursor/rules/dev-workflow.mdc`

## Production Gates

- `BIRDLENSE_ENV=production`
- `BIRDLENSE_STRICT_API_AUTH=1`
- `FLASK_SECRET_KEY`, `PROCESSOR_SECRET` (32-char hex, NOT `${VAR}`)

## CI Source of Truth

- `.github/workflows/ci-pr.yml` (parallel jobs)
- `scripts/ci-full-local.sh` (local driver for CI jobs)

## Common Pitfalls

1. Node version mismatch → check `.nvmrc` + `package.json` engines
2. Missing UI build before Docker → `npm run build` first
3. 403 from processor → bad `PROCESSOR_SECRET` in `.env`
4. Tests hang → `make test-web` uses one-off container; ensure image exists
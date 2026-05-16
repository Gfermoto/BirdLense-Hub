# Local development — BirdLense Hub

Build and run the full stack on your machine **without** a production server. Ideal for UI/API work and running automated tests.

[Русский](../ru/local-dev.ru.md)

---

## Prerequisites

| Tool | Notes |
|------|--------|
| **Docker** + **Compose v2** | Required |
| **Node.js 22** (LTS — matches CI and UI `Dockerfile` stage) | UI build |
| **npm** | UI build (10.x с Node 22) |

Verify:

```bash
docker --version && docker compose version
node --version && npm --version
```

### Node 22 on the host (WSL / macOS / Linux)

The UI lives in **`app/ui/`** with **`.nvmrc`** → `22`. Pick one:

| Tool | Example |
|------|---------|
| **nvm** | `cd app/ui && nvm install && nvm use` |
| **fnm** | `cd app/ui && fnm use` |
| **Volta** | Uses `engines` + `volta` in `app/ui/package.json` automatically when you `cd app/ui` (Volta enabled). |

**VS Code:** open the repo from the root; for terminal tasks that build UI, `cd app/ui` first so the right Node is active.

### Python: app vs docs site

| Context | Python | Note |
|---------|--------|------|
| **BirdLense container** | **3.11** (Ultralytics base image) | Web + processor — do not assume 3.12 inside the image. |
| **MkDocs / `mkdocs build`** | **3.12** recommended (same as CI `docs` job) | Separate venv — see below. |

### MkDocs (documentation site) — local venv

From the **repository root** (not `app/`):

```bash
python3 -m venv .venv-docs
.venv-docs/bin/pip install -r requirements-docs.txt
.venv-docs/bin/python3 scripts/check-docs-version.py
.venv-docs/bin/mkdocs build --strict
```

Details: [documentation guide](./documentation.md).

### Maintainer checklist (before a release)

- [ ] From **repo root:** `make ci-local` (full parity with GitHub **CI** jobs except Docker-heavy layer — see [CI_AND_QUALITY](./ci-and-quality.md)); optional **`make ci-local-docker`** if you need processor image tests + Playwright smoke locally. **`scripts/ci-full-local.sh`** tries **nvm** / **fnm** against `app/ui/.nvmrc` if `node` on `PATH` is missing or &lt; 22 (non-interactive `make` friendly).
- [ ] `cd app && make test && make test-web` (or green **CI** on `dev` → `main`)
- [ ] `cd app && make verify`
- [ ] From repo root: `mkdocs build --strict` (or `.venv-docs` commands above)
- [ ] Optional: `cd app && make start` then `make test-e2e` (or workflow **E2E (Playwright)** → *Run workflow*)
- [ ] After deploy: smoke `curl`/UI per [TESTING](./testing.md) §2

---

## Fast path

From the repository root:

```bash
cd app
make local
```

Open **http://localhost:8085**.

`make local` runs **setup** (creates `app/.env` with `PROCESSOR_SECRET` and `FLASK_SECRET_KEY` if missing), **local-build** (UI + Docker image), then **start**.

Docker **startup order**, `PYTHONPATH`, and health vs readiness: [RUNTIME_COUPLING](../../archive/internal/docs-legacy/RUNTIME_COUPLING.md). If the stack seems stuck after `compose up`, see [TROUBLESHOOTING](../user/troubleshooting.md#single-container-startup-stuck).

Without cameras or Go2RTC, the processor idles in wait mode — **the web UI and API still work**.

Verify after start:

```bash
cd app && make verify
```

---

## Manual equivalent

```bash
cd app
make setup
cd ui && npm ci && npm run build && cd ..
docker compose build
docker compose up -d
docker compose logs -f --tail=100
```

Build the UI **before** `docker compose build` unless your image runs `npm` inside (default workflow expects prebuilt static files).

---

## Running tests

| Layer | Command |
| ------- | --------- |
| Web API | `cd app && make test-web` |
| OpenAPI / UI auth contract smoke | `make test-web-contract-local` |
| Host-only web API | `cd app && make test-web-local` |
| Processor | `cd app && make test` |
| E2E | `cd app && make start` then `make test-e2e` (optional `E2E_SETTINGS_PASSWORD`, `BASE_URL`) |

**Host-only web tests (no Docker):** `cd app && make test-web-local` — uses `app/.venv` from `web/requirements.txt`. If `pip` warns about unrelated tools (e.g. **PlatformIO**), your shell may set **`PYTHONPATH` to `~/.local/.../site-packages`** — unset it, or run **`make venv-web-reset`** to recreate a clean venv.

Focused pytest example:

```bash
docker compose run --rm -v $(pwd):/app birdlense \
  python -m pytest web/tests/test_api.py -v -k "unknowns or overview"
```

Details: [TESTING](./testing.md).

---

## Ports & lifecycle

**Busy 8085?** Add `app/docker-compose.override.yml`:

```yaml
services:
  birdlense:
    ports:
      - "8086:8080"
```

Or: `BIRDLENSE_PORT=8086 make start`

**Stop:** `cd app && make stop`

---

## Data directories

| Path | Role |
|------|------|
| `app/data/recordings/` | Video clips |
| `app/data/db/birdlense.db` | SQLite (auto-created) |
| `app/app_config/user_config.yaml` | Optional overrides |

Import existing files: **System → Scan and import** (if media is already under `data/recordings/`).

---

## Local limitations

- No live cameras until Go2RTC (or file-based CLI flows) is configured.
- No MQTT → no Frigate/BirdNET-driven triggers unless you add a broker.
- Default UI port **8085** — override with `BIRDLENSE_PORT`.

---

## Generated docs (optional)

```bash
make docs          # Python (pdoc) + UI (TypeDoc)
make docs-python   # → docs/api/
make docs-ui       # → docs/ui/
make docs-check    # interrogate on app/web (fails if below threshold)
```

Docstring coverage is configured in **`app/pyproject.toml`** (`[tool.interrogate]`): **fail-under 80%**, `tests/` excluded, plus ignores for nested functions, magic methods, `__init__`, and single-underscore helpers — so the check focuses on public module/class/function surface. The target **fails** if interrogate does not pass (no silent success).

Authoritative HTTP contract: `app/web/openapi.yaml`.

---

## CodeQL (optional)

CI runs CodeQL on push/PR; locally you can use the [VS Code CodeQL extension](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-codeql). See [CODEQL.md](../../archive/internal/docs-legacy/CODEQL.md).

---

## Common issues

**Docker build fails on npm** — build UI first: `cd app/ui && npm run build && cd .. && docker compose build`

**Container exits** — `docker compose logs birdlense`; ensure port not in use (`ss -tlnp | grep 8085`)

**Tests hang** — `make test-web` starts a one-off Docker container with the test code mounted in; it does not require a live app stack. Check that the image builds and Docker is responsive. A live stack is needed for `make verify` and E2E.

# Repository layout

Where things live in the BirdLense Hub monorepo. **Release version** is the root `VERSION` file (also mirrored in `mkdocs.yml`, `app/ui/package.json`, and `app/web/openapi.yaml` — see `scripts/check-docs-version.py`).

[Русский](./REPOSITORY_LAYOUT.ru.md)

---

## Top level

| Path | Role |
|------|------|
| **`app/`** | Runtime stack: Docker Compose, **web** (Flask API), **processor** (detection), **ui** (React/Vite). Day-to-day: `cd app && make local` / `make start` — see [LOCAL_DEV](./LOCAL_DEV.md). |
| **`docs/`** | Operator and developer documentation (this tree); **MkDocs** source. Index: [README](./README.md). |
| **`scripts/`** | Deploy (`deploy.sh`, `deploy.local.sh.example`), diagnostics, dataset helpers, GitHub project scripts, verification. |
| **`mkdocs.yml`**, **`overrides/`** | Static documentation site (GitHub Pages). Build: `make docs-site` or see [Documentation](./Documentation.md). |
| **`Makefile`** (root) | `deploy`, `docs-site`, Telegram proxy helpers, `restore-config`, etc. Application build/start is under `app/Makefile`. |
| **`VERSION`** | Current release semver for the hub (single source of truth for version checks). |
| **`examples/`** | Reference configs (e.g. Prometheus alert rules), not loaded by the app automatically. |
| **`docker/gallery-test/`** | Small **standalone** Docker sample (gallery); not the main `app/` stack. |
| **`wiki-source/`** | Seeds / automation for GitHub Wiki (see [WIKI_AUTOMATION](./WIKI_AUTOMATION.md)). |
| **`screenshots/`** | Images for docs and articles. |
| **`docs/article/`** | Drafts for external posts (e.g. Habr); not part of the running product. |
| **`datasets/`** | Optional local checkout of dataset repos (gitignored at repo root — see `.gitignore`). Use [DATASETS](./DATASETS.md) and `scripts/datasets/`. |

---

## Under `app/`

| Path | Role |
|------|------|
| **`app/web/`** | Flask app, REST API, OpenAPI (`openapi.yaml`). Entry: `app.py` → **`create_app()`** (factory); CORS + SQLite connect PRAGMAs live in `flask_extensions.py`. Handlers: `routes/` — `ui_routes.register_routes`, domain `ui_*_routes`, `ui_system_*`, `processor_routes` ([ARCHITECTURE](./ARCHITECTURE.md)). **Migrations:** `migrations/` (Alembic, Flask-Migrate). **Services:** `services/` (domain logic; routes should stay thin — see [ROADMAP](./ROADMAP.md) § tech debt). |
| **`app/processor/`** | Detection pipeline, YOLO/Ultralytics, model weights path (see repo `.gitignore` for large files). |
| **`app/ui/`** | React 19 + Vite 6 frontend; `npm run build` output is consumed by the web tier (see [LOCAL_DEV](./LOCAL_DEV.md)). |
| **`app/app_config/`** | **Shipped defaults** (`default_config` / templates). **`user_config.yaml`** is created per installation and is **not** committed (see [CONFIGURATION](./CONFIGURATION.md)). |
| **`app/data/`** | SQLite, recordings, local state — **not** copied on deploy by default; see [INSTALL](./INSTALL.md). |

---

## Hygiene (contributors)

- Do not commit **debug dumps** or one-off JSON/txt artifacts in the **repository root**. Many such patterns are already listed in **`.gitignore`**; keep temporary files under `/tmp` or a local directory outside the repo.
- **Config:** editable runtime config lives under `app/app_config/` (or paths documented in CONFIGURATION), not a duplicate empty `app_config/` at repo root.
- **Product vs docs:** runtime code is under `app/`; narrative and guides are under `docs/`.

---

## See also

- [Documentation index](./README.md) — three entry paths (run / integrate / build).
- [ARCHITECTURE](./ARCHITECTURE.md) — how components talk.
- Root [README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/README.md) — quick links for visitors.

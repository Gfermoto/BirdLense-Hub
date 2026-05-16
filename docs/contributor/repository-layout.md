# Repository layout

Where things live in the BirdLense Hub monorepo. **Release version** is the root `VERSION` file (also mirrored in `mkdocs.yml`, `app/ui/package.json`, and `app/web/openapi.yaml` — see `scripts/check-docs-version.py`).

[Русский](../../archive/internal/docs-legacy/REPOSITORY_LAYOUT.ru.md)

---

## Top level

| Path | Role |
|------|------|
| **`app/`** | Runtime stack: Docker Compose, **web** (Flask API), **processor** (detection), **ui** (React/Vite). Day-to-day: `cd app && make local` / `make start` — see [LOCAL_DEV](./local-dev.md). |
| **`docs/`** | Operator and developer documentation (this tree); **MkDocs** source. Index: [docs/index.md](../index.md). |
| **`scripts/`** | Deploy (`deploy.sh`, `deploy.local.sh.example`), diagnostics, dataset helpers, GitHub project scripts, verification. |
| **`mkdocs.yml`**, **`overrides/`** | Static documentation site (GitHub Pages). Build: `make docs-site` or see [documentation guide](./documentation.md). |
| **`Makefile`** (root) | `deploy`, **`ci-local`** / **`ci-local-docker`** (full CI mirror via `scripts/ci-full-local.sh`), `verify`, `docs-site`, Telegram proxy helpers, `restore-config`, etc. Application build/start is under `app/Makefile`. |
| **`VERSION`** | Current release semver for the hub (single source of truth for version checks). |
| **`examples/`** | Reference configs (e.g. Prometheus alert rules), not loaded by the app automatically. |
| **`wiki-source/`** | Seeds / automation for GitHub Wiki (see [WIKI_AUTOMATION](../../archive/internal/docs-legacy/WIKI_AUTOMATION.md)). |
| **`screenshots/`** | Images for docs and articles. |
| **`docs/article/`** | Drafts for external posts (e.g. Habr); not part of the running product. |
| **`datasets/`** | Local dataset artifacts (gitignored): classifier merges (e.g. **`merged_cls`**), **`BirdLense_detector_brg_*.zip`** (`pack_brg_for_gdrive.py`, default **`datasets/new/detector/`**), Roboflow zips, etc. **vs** legacy **`scripts/datasets/binary/`** — [DATASETS](./datasets.md) (**Canonical paths**). |

---

## Under `app/`

| Path | Role |
|------|------|
| **`app/web/`** | Flask app, REST API, OpenAPI (`openapi.yaml`). Entry: `app.py` → **`create_app()`** (factory); CORS + SQLite PRAGMAs in `flask_extensions.py`; DB seed/registry/cleanup in `app_startup.py`. Handlers: `routes/` — `ui_routes.register_routes`, domain `ui_*_routes`, `ui_system_*`, `processor_routes` ([ARCHITECTURE](./architecture.md)). **Migrations:** `migrations/` (Alembic, Flask-Migrate). **Services:** `services/` (domain logic; routes should stay thin — see [ROADMAP](./roadmap.md) § tech debt). |
| **`app/processor/`** | Detection pipeline, YOLO/Ultralytics, model weights path (see repo `.gitignore` for large files). **`src/`:** `main.py`, `processor_bootstrap.py`, `detection_stack.py`, `detection_strategy.py` (ABC), **`interfaces.py`** (`DetectionStrategyProtocol` for `FrameProcessor` typing/tests), `frame_processor.py`, MQTT/recording modules; **`tests/`** includes `test_detection_strategy_protocol.py`. |
| **`app/ui/`** | React 19 + Vite 6 frontend; `npm run build` output is consumed by the web tier (see [LOCAL_DEV](./local-dev.md)). |
| **`app/app_config/`** | **Shipped defaults** (`default_config` / templates). **`user_config.yaml`** is created per installation and is **not** committed (see [CONFIGURATION](../user/configuration.md)). |
| **`app/data/`** | SQLite, recordings, local state — **not** copied on deploy by default; see [INSTALL](../user/install.md). |

---

## Hygiene (contributors)

- Do not commit **debug dumps** or one-off JSON/txt artifacts in the **repository root**. Many such patterns are already listed in **`.gitignore`**; keep temporary files under `/tmp` or a local directory outside the repo.
- **Config:** editable runtime config lives under `app/app_config/` (or paths documented in CONFIGURATION), not a duplicate empty `app_config/` at repo root.
- **Product vs docs:** runtime code is under `app/`; narrative and guides are under `docs/`.

---

## See also

- [Documentation index](../index.md) — user / contributor / RU entry paths.
- [ARCHITECTURE](./architecture.md) — how components talk.
- Root [README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/README.md) — quick links for visitors.

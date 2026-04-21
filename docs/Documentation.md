# Documentation guide — BirdLense Hub

How this project structures docs for contributors and readers.

[Русский](./Documentation.ru.md)

---

## Layout

| Area | Role |
|------|------|
| Repository root | `README.md` (EN), quick start, links to `docs/` |
| `docs/` | Detailed guides, reference, troubleshooting |
| `docs/archive/` | Historical notes (optional reading) |

**Navigation:** start at [docs/README.md](./README.md).

---

## Static documentation site (MkDocs + GitHub Pages)

**Python version:** The **BirdLense application** Docker image uses **Python 3.11** (Ultralytics base). **MkDocs** for this repo is built with **Python 3.12** in CI and locally — use a **separate venv** (e.g. `.venv-docs`); do not assume the app container’s Python for doc builds.

The repository ships **[mkdocs.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml)** at the root: **MkDocs Material**, `docs_dir: docs`, `nav` aligned with [SITE_MAP.md](./SITE_MAP.md). Canonical policy files that live at the repo root (Contributing, Security policy, Changelog, OpenAPI YAML) are surfaced on the site via short pages under [docs/project/](./project/contributing.md) so internal links stay inside `docs/` and work when the site is published.

### Build locally

```bash
python3 -m venv .venv-docs
.venv-docs/bin/pip install -r requirements-docs.txt
.venv-docs/bin/mkdocs serve   # http://127.0.0.1:8000
```

Build output goes to `site/` (ignored by git).

**Full local CI (mirror of GitHub checks):** from the **repository root**, `make ci-local` runs `scripts/ci-full-local.sh` — Python security + Ruff + full `pytest web/tests/` in **`.venv-ci`**, version sync, UI (OpenAPI codegen drift, Vitest, typecheck, lint, build), Settings UI coverage script, **MkDocs** `--strict` via **`.venv-docs`**. `make ci-local-docker` adds Docker image tests and Playwright `smoke.spec.ts`. Requires **Node.js ≥ 22** for the UI phase. Details: [CI_AND_QUALITY](./CI_AND_QUALITY.md).

### OpenAPI spec maintenance {#openapi-spec-maintenance}

The UI API surface is large; **bulk path blocks** (many `/api/ui/...` entries plus the second **`servers`** URL for `/api/processor`) are generated from **`scripts/generate_openapi_remaining_paths.py`** and merged by **`scripts/merge_openapi_fragments.py`** into **`app/web/openapi.yaml`** (inserted before `components:`).

From the **repository root**:

```bash
python3 scripts/merge_openapi_fragments.py
```

Always **`git diff app/web/openapi.yaml`** before committing: the merge rewrites a big slice of the file. Hand-edited narrative in `info.description` or fine-tuned operation schemas should be preserved or re-applied if you regenerate.

**Idempotent merge:** `merge_openapi_fragments.py` removes any previously inserted bulk block (everything from the first YAML path key **`/cameras`** through the end of the `paths` section) before appending the generated fragment again — so re-running the script does not duplicate paths. **Manual path entries must live above `/cameras`** in `openapi.yaml` (the generator always emits `/cameras` first in the bulk list).

**Excluded from the published site** (see root `mkdocs.yml` `exclude_docs`): `docs/archive/**`, `docs/article/**` (publication drafts), `CONSILIUM_AUDIT.ru.md` (historical RU audit; see [archive on GitHub](https://github.com/Gfermoto/BirdLense-Hub/tree/main/docs/archive)), and `PRE_IMPLEMENTATION_UNKNOWN_TIMELINE*.md` (maintainer pre-flight checklist for specific GitHub issues—kept in the repo, not part of the operator manual), and `LEGACY_CLEANUP.md` (internal inventory notes).

### Publish (CI)

Workflow [.github/workflows/docs-pages.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docs-pages.yml):

- On push to **`main`** or **`dev`** when `docs/**`, `mkdocs.yml`, `VERSION`, `requirements-docs.txt`, or `scripts/check-docs-version.py` change (or manually via **Actions → Documentation site → Run workflow**), the site is **built** every run.
- Before build: **`python3 scripts/check-docs-version.py`** — the string from root **`VERSION`** must appear in `mkdocs.yml` (at least `extra.site_version`; the top banner is **`overrides/main.html`** → `{% block announce %}` with `config.extra.site_version`).
- Build: **`mkdocs build --strict`** (broken links / nav issues fail CI).
- **Deploy to GitHub Pages** runs only for **`main`**.

**One-time repo settings:** *Settings → Pages → Build and deployment → Source:* **GitHub Actions**. The first deploy may require approving the `github-pages` environment for the workflow.

If the live site still shows an old banner, check that **`main`** contains the updated `mkdocs.yml` and that the **Documentation site** workflow succeeded (Pages can lag by a few minutes after deploy).

---

## Content strategy (community, site, articles)

Docs are written so they can be **split into a static site** or **quoted in blog posts** without rewriting facts.

| Asset | Role |
|-------|------|
| [OVERVIEW.md](./OVERVIEW.md) | Narrative “what & why” — homepage hero, press kit, first paragraph of articles |
| [README.md](./README.md) (this folder) | Doc home + topic tables; site nav is root `mkdocs.yml` |
| [SITE_MAP.md](./SITE_MAP.md) | Ready-made section → file mapping for a doc site |
| [INSTALL](./INSTALL.md) + [SCENARIOS](./SCENARIOS.md) | Getting started & tutorials |
| [FEATURES](./FEATURES.md) | Capability / comparison page |
| [ARCHITECTURE](./ARCHITECTURE.md) | Technical deep dive |
| `app/web/openapi.yaml` | API contract; on the static site: [OpenAPI (Redoc)](./reference/openapi.md) (iframe → `reference/openapi.html`) |

**Tone:** direct, second person (“you”), no internal roadmap jargon in user-facing pages. Prefer tables and short sections over long prose.

### Reviewer checklist (before merging doc PRs)

- [ ] EN file is primary; `*.ru.md` updated when behavior or structure changes.
- [ ] Placeholders only (`YOUR_HOST`, not real IPs).
- [ ] Cross-links point to the **same language** where a pair exists (or intentionally to EN for API-only pages).
- [ ] Long how-tos (e.g. Colab): code cells still run; print strings and comments aligned with the doc language.
- [ ] [docs/README.md](./README.md) + [I18N_STATUS.md](./I18N_STATUS.md) updated when adding a new page.
- [ ] **[ROADMAP](./ROADMAP.md)** § *Current stack*: React/Vite (and any pinned UI versions) match `app/ui/package.json` / lockfile; DB/migration notes match `app/web` reality.
- [ ] [`mkdocs.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml) — both **English nav** and the **Русский** section list new pages (or an explicit decision to keep them repo-only).
- [ ] [SITE_MAP.md](./SITE_MAP.md) and [SITE_MAP.ru.md](./SITE_MAP.ru.md) match the sidebar.
- [ ] After bulk OpenAPI regeneration: `python3 scripts/merge_openapi_fragments.py` — confirm diff and run `pytest web/tests/test_openapi_contract.py` plus `python3 -c "import yaml; yaml.safe_load(open('app/web/openapi.yaml'))"`.

---

## Language policy

- **English** is the primary language for new and maintained pages (`*.md`).
- **Russian** lives in paired files (`*.ru.md`) where translated.
- At the **top** of each paired doc, link to the other language (see [INSTALL.md](./INSTALL.md)).

Docs that are still Russian-only in `*.md` are tracked in [I18N_STATUS.md](./I18N_STATUS.md); the goal is EN primary + optional RU.

---

## Security in examples

Do not commit real hosts, paths, tokens, or API keys. Use placeholders:

| Kind | Example |
|------|---------|
| Host | `YOUR_HOST`, `localhost` |
| Remote path | `YOUR_REMOTE_DIR` |
| SSH config name | `YOUR_SSH_HOST` |
| Secrets | `your-secret-token`, `your-api-key` |
| Public URL | `https://your-birdlense.example.com` |

Full table: [OPEN_SOURCE_PREP.md](./OPEN_SOURCE_PREP.md) § Placeholders.

---

## Contributing to docs

1. Prefer **instructional** tone: what to do, not project history.
2. Keep **INSTALL**, **CONFIGURATION**, **SCENARIOS**, and **TROUBLESHOOTING** aligned (cross-links).
3. After changing headings, grep for broken internal links.
4. For a new guide: add one line to [docs/README.md](./README.md) and update [I18N_STATUS.md](./I18N_STATUS.md).

Repository norms: [Contributing](./project/contributing.md).

---

## Key documents

| Topic | EN entry |
|-------|----------|
| Story & audience | [OVERVIEW.md](./OVERVIEW.md) |
| Install / deploy | [INSTALL.md](./INSTALL.md) |
| Use cases | [SCENARIOS.md](./SCENARIOS.md) |
| Config reference | [CONFIGURATION.md](./CONFIGURATION.md) |
| Glossary | [GLOSSARY.md](./GLOSSARY.md) |
| Tests | [TESTING.md](./TESTING.md) |
| Problems | [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) |
| Local dev | [LOCAL_DEV.md](./LOCAL_DEV.md) |
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| API overview | [API.md](./API.md) |
| OpenAPI YAML (canonical) | [project/openapi.md](./project/openapi.md) |
| Access control | [ACCESS_CONTROL.md](./ACCESS_CONTROL.md) |
| Site nav template | [SITE_MAP.md](./SITE_MAP.md) |
| Training (Colab) | [TRAINING.md](./TRAINING.md) |
| Datasets | [DATASETS.md](./DATASETS.md) |
| Versioning | [VERSIONING.md](./VERSIONING.md) |
| Roadmap | [ROADMAP.md](./ROADMAP.md) |
| Security analysis | [SECURITY.md](./SECURITY.md) |
| Open-source checklist | [OPEN_SOURCE_PREP.md](./OPEN_SOURCE_PREP.md) |
| Localization status | [I18N_STATUS.md](./I18N_STATUS.md) |

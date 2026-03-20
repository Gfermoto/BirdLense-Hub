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

**Large refactor:** [DOCS_REFACTOR_CONSILIUM](./DOCS_REFACTOR_CONSILIUM.md) — roles, phases, mandatory review checklist.

---

## Static documentation site (MkDocs + GitHub Pages)

The repository ships **[mkdocs.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml)** at the root: **MkDocs Material**, `docs_dir: docs`, `nav` aligned with [SITE_MAP.md](./SITE_MAP.md). Canonical policy files that live at the repo root (Contributing, Security policy, Changelog, OpenAPI YAML) are surfaced on the site via short pages under [docs/project/](./project/contributing.md) so internal links stay inside `docs/` and work when the site is published.

### Build locally

```bash
python3 -m venv .venv-docs
.venv-docs/bin/pip install -r requirements-docs.txt
.venv-docs/bin/mkdocs serve   # http://127.0.0.1:8000
```

Build output goes to `site/` (ignored by git).

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
| [README.md](./README.md) (this folder) | Information architecture — sidebar / nav for Docusaurus, MkDocs, VitePress |
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
| Access control | [ACCESS_CONTROL.md](./ACCESS_CONTROL.md) |
| Site nav template | [SITE_MAP.md](./SITE_MAP.md) |
| Training (Colab) | [TRAINING.md](./TRAINING.md) |
| Datasets | [DATASETS.md](./DATASETS.md) |
| Versioning | [VERSIONING.md](./VERSIONING.md) |
| Roadmap | [ROADMAP.md](./ROADMAP.md) |
| Security analysis | [SECURITY.md](./SECURITY.md) |
| Open-source checklist | [OPEN_SOURCE_PREP.md](./OPEN_SOURCE_PREP.md) |
| Localization status | [I18N_STATUS.md](./I18N_STATUS.md) |

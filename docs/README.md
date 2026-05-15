# BirdLense Hub — Documentation

> **Version 0.3.7** (source of truth: repo root `VERSION`) · OpenAPI: [YAML spec](./project/openapi.md) · **Interactive:** [Redoc](./reference/openapi.md) · **Published docs:** [gfermoto.github.io/BirdLense-Hub](https://gfermoto.github.io/BirdLense-Hub/)

[Русский](./README.ru.md)

Welcome. This folder is the **single source of truth** for operators, integrators, and contributors. Use it to run the stack, fix issues, extend the project, or **repurpose content** for a website, wiki, or blog (see [OVERVIEW](./OVERVIEW.md)).

---

## Start in three paths

Pick what matches you — you can read the rest as reference.

| Path | You want to… | Go to |
|------|----------------|-------|
| **Run** | Install Docker, connect cameras, go live | [QUICKSTART](./QUICKSTART.md) → [OVERVIEW](./OVERVIEW.md) → [INSTALL](./INSTALL.md) → [SCENARIOS](./SCENARIOS.md) |
| **Integrate** | Frigate, BirdNET, MQTT, HA, Telegram | [SCENARIOS](./SCENARIOS.md) → [CONFIGURATION](./CONFIGURATION.md) |
| **Build & ship** | Hacks, tests, releases | [QUICKSTART](./QUICKSTART.md) → [Repository layout](./REPOSITORY_LAYOUT.md) → [LOCAL_DEV](./LOCAL_DEV.md) → [TESTING](./TESTING.md) → [CI & quality](./CI_AND_QUALITY.md) → [Contributing](./project/contributing.md) |

---

## Product & reference

| Topic | English | Russian |
|-------|---------|---------|
| **Short description** (GitHub About, press) | [SHORT_DESCRIPTION.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SHORT_DESCRIPTION.md) | [RU](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SHORT_DESCRIPTION.ru.md) |
| **Project story** (for landing & articles) | [OVERVIEW](./OVERVIEW.md) | [RU](./OVERVIEW.ru.md) |
| **Install & deploy** | [INSTALL](./INSTALL.md) | [RU](./INSTALL.ru.md) |
| **Quickstart & verify** | [QUICKSTART](./QUICKSTART.md) | [RU](./QUICKSTART.ru.md) |
| **Recipes & workflows** | [SCENARIOS](./SCENARIOS.md) | [RU](./SCENARIOS.ru.md) |
| **Config keys & env** | [CONFIGURATION](./CONFIGURATION.md) · [Policy](./CONFIGURATION_POLICY.md) | [RU](./CONFIGURATION.ru.md) · [Политика](./CONFIGURATION_POLICY.ru.md) |
| **Terms (Hub, Frigate, merge, …)** | [GLOSSARY](./GLOSSARY.md) | [RU](./GLOSSARY.ru.md) |
| **Domain contract** (trigger/clip/visit/review/taxon) | [DOMAIN_CONTRACT](./DOMAIN_CONTRACT.md) | [RU](./DOMAIN_CONTRACT.ru.md) |
| **Feature matrix & API hints** | [FEATURES](./FEATURES.md) | [RU](./FEATURES.ru.md) |
| **System design** | [ARCHITECTURE](./ARCHITECTURE.md) | [RU](./ARCHITECTURE.ru.md) |
| **HTTP API narrative** | [API](./API.md) · [OpenAPI Redoc](./reference/openapi.md) | [RU](./API.ru.md) · [Redoc RU](./reference/openapi.ru.md) |
| **Versioning** | [VERSIONING](./VERSIONING.md) | [RU](./VERSIONING.ru.md) |
| **Server deploy checklist** | [DEPLOY_SERVER](./DEPLOY_SERVER.md) | [RU](./DEPLOY_SERVER.ru.md) |
| **Public recordings (VPS)** | [PUBLIC_RECORDINGS](./PUBLIC_RECORDINGS.md) | [RU](./PUBLIC_RECORDINGS.ru.md) |
| **PostgreSQL (hub DB)** | [POSTGRES_MIGRATION](./POSTGRES_MIGRATION.md) | [RU](./POSTGRES_MIGRATION.ru.md) |
| **Release readiness** | [RELEASE_READINESS](./RELEASE_READINESS.md) | [RU](./RELEASE_READINESS.ru.md) |
| **Definition of Done (short gate)** | [DEFINITION_OF_DONE](./DEFINITION_OF_DONE.md) | [RU](./DEFINITION_OF_DONE.ru.md) |
| **UI settings map** | [UI_SETTINGS_MAP](./UI_SETTINGS_MAP.md) | [RU](./UI_SETTINGS_MAP.ru.md) |
| **UI copy tone** | [UI_COPY_STYLE](./UI_COPY_STYLE.md) | [RU](./UI_COPY_STYLE.ru.md) |
| **UX canonical map** (roles, routes, journeys) | [UX_CANONICAL_MAP](./UX_CANONICAL_MAP.md) | [RU](./UX_CANONICAL_MAP.ru.md) |
| **Processor performance notes** | [PROCESSOR_PERFORMANCE](./PROCESSOR_PERFORMANCE.md) | [RU](./PROCESSOR_PERFORMANCE.ru.md) |
| **Config triggers inventory** | [CONFIGURATION_TRIGGERS_INVENTORY](./CONFIGURATION_TRIGGERS_INVENTORY.md) | [RU](./CONFIGURATION_TRIGGERS_INVENTORY.ru.md) |
| **API errors & security baseline** | [API_ERRORS](./API_ERRORS.md) | [RU](./API_ERRORS.ru.md) |
| **Hub epics tracker (GitHub)** | [HUB_EPICS_TRACKER](./HUB_EPICS_TRACKER.md) | [RU](./HUB_EPICS_TRACKER.ru.md) |
| **Heimdall dashboard tiles** | [HEIMDALL](./HEIMDALL.md) | [RU](./HEIMDALL.ru.md) |

---

## Security & operations

| Topic | Document |
|-------|----------|
| Access & passwords | [ACCESS_CONTROL](./ACCESS_CONTROL.md) · [RU](./ACCESS_CONTROL.ru.md) |
| Threats & hardening | [SECURITY](./SECURITY.md) · [RU](./SECURITY.ru.md) |
| Recover broken config | [RECOVERY_CONFIG](./RECOVERY_CONFIG.md) · [RU](./RECOVERY_CONFIG.ru.md) |
| When something fails | [TROUBLESHOOTING](./TROUBLESHOOTING.md) · [RU](./TROUBLESHOOTING.ru.md) |
| Operator runbooks | [RUNBOOKS](./RUNBOOKS.md) · [RU](./RUNBOOKS.ru.md) |

---

## Quality & tooling

| Topic | Document |
|-------|----------|
| **CI on PR** (Bandit, pip-audit, Ruff, pytest slices, UI build, MkDocs, Docker tests, Playwright smoke) | [TESTING](./TESTING.md) §1 · [RU](./TESTING.ru.md) |
| **Local full CI & policy** (`make ci-local`, `make ci-local-docker`, formats, audits, OpenAPI→TS) | [CI_AND_QUALITY](./CI_AND_QUALITY.md) · [RU](./CI_AND_QUALITY.ru.md) |
| **Tests, E2E, post-deploy checks** | [TESTING](./TESTING.md) · [RU](./TESTING.ru.md) |
| Automated verification log (releases / critical fixes) | [VERIFICATION](./VERIFICATION.md) · [RU](./VERIFICATION.ru.md) |
| Domain integrity checks | `GET /api/ui/system/domain-health` + [DOMAIN_CONTRACT](./DOMAIN_CONTRACT.md) |
| MCP (Model Context Protocol — automation & integrations) | [MCP_SETUP](./MCP_SETUP.md) · [RU](./MCP_SETUP.ru.md) |
| **UX tooltips & inline hints** (contributors) | [UX_TOOLTIPS](./UX_TOOLTIPS.md) · [RU](./UX_TOOLTIPS.ru.md) |

---

## ML, data & roadmap

| Topic | English | Russian |
|-------|---------|---------|
| Model training (EU/US) | [TRAINING](./TRAINING.md) | [RU](./TRAINING.ru.md) |
| ML quality loop (operators) | — | [RU only](./ML_QUALITY_LOOP.ru.md) |
| CV / ML roadmap epic (GitHub) | [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) | [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) |
| CV / ML prep contract | [CV_ML_PREP](./CV_ML_PREP.md) | [RU](./CV_ML_PREP.ru.md) |
| CV / ML roadmap phases | [CV_ML_ROADMAP_PHASES](./CV_ML_ROADMAP_PHASES.md) | [RU](./CV_ML_ROADMAP_PHASES.ru.md) |
| ML handoff (repo vs your training) | [ML_OPERATOR_HANDOFF](./ML_OPERATOR_HANDOFF.md) | [RU](./ML_OPERATOR_HANDOFF.ru.md) |
| Datasets & scripts | [DATASETS](./DATASETS.md) | [RU](./DATASETS.ru.md) |
| Detector dataset (HF, zips) | [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) | [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) |
| Detector weights (HF, YOLO + OpenVINO) | [weights-20260429T125011Z-3-001.zip](https://huggingface.co/gfermoto/BirdLense_Detector/blob/main/weights-20260429T125011Z-3-001.zip) | [weights-20260429T125011Z-3-001.zip](https://huggingface.co/gfermoto/BirdLense_Detector/blob/main/weights-20260429T125011Z-3-001.zip) |
| Detector training (Colab) | [ML_DETECTOR_COLAB](./ML_DETECTOR_COLAB.md) | [RU](./ML_DETECTOR_COLAB.ru.md) |
| Video decode baseline (#373) | [CV_ML_DECODE](./CV_ML_DECODE.md) | [RU](./CV_ML_DECODE.ru.md) |
| Active learning (#369) | [ACTIVE_LEARNING](./ACTIVE_LEARNING.md) | [RU](./ACTIVE_LEARNING.ru.md) |
| Re-ID roadmap (#374) | [REID](./REID_ROADMAP.md) | [RU](./REID_ROADMAP.ru.md) |
| Federated learning (#375) | [FEDERATED_LEARNING](./FEDERATED_LEARNING.md) | [RU](./FEDERATED_LEARNING.ru.md) |
| Versioning & releases | [VERSIONING](./VERSIONING.md) | [RU](./VERSIONING.ru.md) |
| Direction / backlog | [ROADMAP](./ROADMAP.md) | [RU](./ROADMAP.ru.md) |

---

## Project meta

The static site sidebar comes from root `mkdocs.yml`. For a **line-up with filenames** (same order as **Meta** and **Repository (canonical files)**), use [SITE_MAP](./SITE_MAP.md) · [RU](./SITE_MAP.ru.md).

### Meta (MkDocs `nav` → Meta)

| Topic | Document |
|-------|----------|
| **Hub epics (GitHub tracker)** | [HUB_EPICS_TRACKER](./HUB_EPICS_TRACKER.md) · [RU](./HUB_EPICS_TRACKER.ru.md) |
| **Repository layout** (onboarding) | [REPOSITORY_LAYOUT](./REPOSITORY_LAYOUT.md) · [RU](./REPOSITORY_LAYOUT.ru.md) |
| **Verification log** (releases) | [VERIFICATION](./VERIFICATION.md) · [RU](./VERIFICATION.ru.md) |
| How docs are written (placeholders, i18n, site reuse) | [Documentation](./Documentation.md) · [RU](./Documentation.ru.md) |
| **Site map** (generator; keep `nav` aligned) | [SITE_MAP](./SITE_MAP.md) · [RU](./SITE_MAP.ru.md) |
| Translation status | [I18N_STATUS](./I18N_STATUS.md) · [RU](./I18N_STATUS.ru.md) |
| **Secrets rotation (production ops)** | [SECRETS_ROTATION](./SECRETS_ROTATION.md) · [RU](./SECRETS_ROTATION.ru.md) |
| Security analysis (technical) | [SECURITY](./SECURITY.md) · [RU](./SECURITY.ru.md) |
| Open-source release checklist | [OPEN_SOURCE_PREP](./OPEN_SOURCE_PREP.md) · [RU](./OPEN_SOURCE_PREP.ru.md) |
| Governance & external review | [GOVERNANCE](./GOVERNANCE.md) · [RU](./GOVERNANCE.ru.md) |
| **GitHub CLI setup** (personal repo) | [GITHUB_SETUP_GH](./GITHUB_SETUP_GH.md) · [RU](./GITHUB_SETUP_GH.ru.md) |
| **Wiki + CI reports** (Summary / Artifact / optional Wiki push) | [WIKI_AUTOMATION](./WIKI_AUTOMATION.md) · [RU](./WIKI_AUTOMATION.ru.md) |

### Related process (not extra sidebar rows)

| Topic | Document |
|-------|----------|
| **Issues, board & roadmap** | [ROADMAP](./ROADMAP.md) (*Triage*) · [RU](./ROADMAP.ru.md); root [CONTRIBUTING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md) |

### Repository (canonical files — `docs/project/` stubs)

| Topic | Document |
|-------|----------|
| Contributing | [project/contributing.md](./project/contributing.md) → root **CONTRIBUTING** on GitHub |
| Security policy | [project/security-policy.md](./project/security-policy.md) → root **SECURITY** |
| Code of Conduct | [project/code-of-conduct.md](./project/code-of-conduct.md) → root **CODE_OF_CONDUCT** |
| Changelog | [project/changelog.md](./project/changelog.md) → root **CHANGELOG** |
| OpenAPI (YAML) | [project/openapi.md](./project/openapi.md) → `app/web/openapi.yaml` |
| Root README | [project/root-readme.md](./project/root-readme.md) → root **README** |

### Publishing & archive

| Topic | Document |
|-------|----------|
| **MkDocs site** (build & GitHub Pages) | [Documentation](./Documentation.md) (*Static documentation site*) |
| Historical notes | [archive/README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/docs/archive/README.md) (in repo; excluded from MkDocs build) |

---

## Quick commands (from repo)

| Goal | Command |
|------|---------|
| Local stack | `cd app && make local` → http://localhost:8085 |
| Shared smoke contract | `make verify` (or `BASE_URL=http://YOUR_HOST:8085 make verify`) |
| Web tests | `cd app && make test-web` |
| Telegram proxy autorotate | `make proxy-rotation-install` (status: `make proxy-rotation-status`) |
| Regenerate bulk OpenAPI path block | `python3 scripts/merge_openapi_fragments.py` (from repo root; review diff) — [details](./Documentation.md#openapi-spec-maintenance) |
| Full doc index above | This page |
| Preview static doc site | `pip install -r requirements-docs.txt && mkdocs serve` ([details](./Documentation.md)) |

For server deploy patterns, see [INSTALL](./INSTALL.md).

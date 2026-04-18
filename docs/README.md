# BirdLense Hub — Documentation

> **Version 0.3.5** (source of truth: repo root `VERSION`) · OpenAPI: [YAML spec](./project/openapi.md) · **Interactive:** [Redoc](./reference/openapi.md) · **Published docs:** [gfermoto.github.io/BirdLense-Hub](https://gfermoto.github.io/BirdLense-Hub/)

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
| **Quickstart & verify** | [QUICKSTART](./QUICKSTART.md) | — |
| **Recipes & workflows** | [SCENARIOS](./SCENARIOS.md) | [RU](./SCENARIOS.ru.md) |
| **Config keys & env** | [CONFIGURATION](./CONFIGURATION.md) | [RU](./CONFIGURATION.ru.md) |
| **Terms (Hub, Frigate, merge, …)** | [GLOSSARY](./GLOSSARY.md) | [RU](./GLOSSARY.ru.md) |
| **Domain contract** (trigger/clip/visit/review/taxon) | [DOMAIN_CONTRACT](./DOMAIN_CONTRACT.md) | [RU](./DOMAIN_CONTRACT.ru.md) |
| **Feature matrix & API hints** | [FEATURES](./FEATURES.md) | [RU](./FEATURES.ru.md) |
| **System design** | [ARCHITECTURE](./ARCHITECTURE.md) | [RU](./ARCHITECTURE.ru.md) |
| **HTTP API narrative** | [API](./API.md) · [OpenAPI Redoc](./reference/openapi.md) | [RU](./API.ru.md) · [Redoc RU](./reference/openapi.ru.md) |
| **Versioning** | [VERSIONING](./VERSIONING.md) | [RU](./VERSIONING.ru.md) |
| **Server deploy checklist** | [DEPLOY_SERVER](./DEPLOY_SERVER.md) | [RU](./DEPLOY_SERVER.ru.md) |
| **Release readiness** | [RELEASE_READINESS](./RELEASE_READINESS.md) | [RU](./RELEASE_READINESS.ru.md) |
| **Heimdall dashboard tiles** | [HEIMDALL](./HEIMDALL.md) | [RU](./HEIMDALL.ru.md) |

---

## Security & operations

| Topic | Document |
|-------|----------|
| Access & passwords | [ACCESS_CONTROL](./ACCESS_CONTROL.md) · [RU](./ACCESS_CONTROL.ru.md) |
| Threats & hardening | [SECURITY](./SECURITY.md) |
| Recover broken config | [RECOVERY_CONFIG](./RECOVERY_CONFIG.md) · [RU](./RECOVERY_CONFIG.ru.md) |
| When something fails | [TROUBLESHOOTING](./TROUBLESHOOTING.md) · [RU](./TROUBLESHOOTING.ru.md) |
| Operator runbooks | [RUNBOOKS](./RUNBOOKS.md) · [RU](./RUNBOOKS.ru.md) |

---

## Quality & tooling

| Topic | Document |
|-------|----------|
| **CI jobs** (Bandit, pip-audit, Ruff, pytest slices, UI build, MkDocs, Docker tests, Playwright smoke) | [TESTING](./TESTING.md) (section 1) · [RU](./TESTING.ru.md) |
| **One-shot local CI** (`make ci-local`, `make ci-local-docker` from repo root) | [CI_AND_QUALITY](./CI_AND_QUALITY.md) · [RU](./CI_AND_QUALITY.ru.md) |
| **CI policy** (Ruff format, pip-audit ignores, npm audit, OpenAPI→TS roadmap) | [CI_AND_QUALITY](./CI_AND_QUALITY.md) · [RU](./CI_AND_QUALITY.ru.md) |
| Unit, API, E2E, post-deploy checks | [TESTING](./TESTING.md) · [RU](./TESTING.ru.md) |
| Automated verification log (releases / critical fixes) | [VERIFICATION](./VERIFICATION.md) · [RU](./VERIFICATION.ru.md) |
| Domain integrity checks | `GET /api/ui/system/domain-health` + [DOMAIN_CONTRACT](./DOMAIN_CONTRACT.md) |
| MCP (Model Context Protocol — automation & integrations) | [MCP_SETUP](./MCP_SETUP.md) · [RU](./MCP_SETUP.ru.md) |

---

## ML, data & roadmap

| Topic | English | Russian |
|-------|---------|---------|
| Model training (EU/US) | [TRAINING](./TRAINING.md) | [RU](./TRAINING.ru.md) |
| Datasets & scripts | [DATASETS](./DATASETS.md) | [RU](./DATASETS.ru.md) |
| Versioning & releases | [VERSIONING](./VERSIONING.md) | [RU](./VERSIONING.ru.md) |
| Direction / backlog | [ROADMAP](./ROADMAP.md) | [RU](./ROADMAP.ru.md) |

---

## Project meta

| Topic | Document |
|-------|----------|
| **Repository layout** (onboarding) | [REPOSITORY_LAYOUT](./REPOSITORY_LAYOUT.md) · [RU](./REPOSITORY_LAYOUT.ru.md) |
| How docs are written (placeholders, i18n, site reuse) | [Documentation](./Documentation.md) · [RU](./Documentation.ru.md) |
| Security analysis (technical) | [SECURITY](./SECURITY.md) · [RU](./SECURITY.ru.md) |
| **Secrets rotation (production ops)** | [SECRETS_ROTATION](./SECRETS_ROTATION.md) · [RU](./SECRETS_ROTATION.ru.md) |
| Open-source release checklist | [OPEN_SOURCE_PREP](./OPEN_SOURCE_PREP.md) · [RU](./OPEN_SOURCE_PREP.ru.md) |
| Governance & external review | [GOVERNANCE](./GOVERNANCE.md) · [RU](./GOVERNANCE.ru.md) |
| **Issues, board & roadmap process** | [ROADMAP](./ROADMAP.md) (*Triage*) · [RU](./ROADMAP.ru.md); root [CONTRIBUTING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md) |
| **GitHub CLI setup** (personal repo) | [GITHUB_SETUP_GH](./GITHUB_SETUP_GH.md) · [RU](./GITHUB_SETUP_GH.ru.md) |
| **Wiki + CI reports** (Summary / Artifact / optional Wiki push) | [WIKI_AUTOMATION](./WIKI_AUTOMATION.md) · [RU](./WIKI_AUTOMATION.ru.md) |
| Translation status | [I18N_STATUS](./I18N_STATUS.md) |
| **Site sections ↔ files** (keep in sync with `mkdocs.yml`) | [SITE_MAP](./SITE_MAP.md) · [RU](./SITE_MAP.ru.md) |
| **MkDocs site (build & GitHub Pages)** | [Documentation](./Documentation.md) (*Static documentation site*) |
| Historical notes | [archive/README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/docs/archive/README.md) (in repo; excluded from MkDocs build) |

---

## Quick commands (from repo)

| Goal | Command |
|------|---------|
| Local stack | `cd app && make local` → http://localhost:8085 |
| Shared smoke contract | `make verify` (or `BASE_URL=http://YOUR_HOST:8085 make verify`) |
| Web tests | `cd app && make test-web` |
| Telegram proxy autorotate | `make proxy-rotation-install` (status: `make proxy-rotation-status`) |
| Full doc index above | This page |
| Preview static doc site | `pip install -r requirements-docs.txt && mkdocs serve` ([details](./Documentation.md)) |

For server deploy patterns, see [INSTALL](./INSTALL.md).

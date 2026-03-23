# BirdLense Hub — Documentation

> **Version 0.2.6** · OpenAPI: [YAML spec](./project/openapi.md) · **Interactive:** [Redoc](./reference/openapi.md) · **Published docs:** [gfermoto.github.io/BirdLense-Hub](https://gfermoto.github.io/BirdLense-Hub/)

[Русский](./README.ru.md)

Welcome. This folder is the **single source of truth** for operators, integrators, and contributors. Use it to run the stack, fix issues, extend the project, or **repurpose content** for a website, wiki, or blog (see [OVERVIEW](./OVERVIEW.md)).

---

## Start in three paths

Pick what matches you — you can read the rest as reference.

| Path | You want to… | Go to |
|------|----------------|-------|
| **Run** | Install Docker, connect cameras, go live | [OVERVIEW](./OVERVIEW.md) (context) → [INSTALL](./INSTALL.md) → [SCENARIOS](./SCENARIOS.md) |
| **Integrate** | Frigate, BirdNET, MQTT, HA, Telegram | [SCENARIOS](./SCENARIOS.md) → [CONFIGURATION](./CONFIGURATION.md) |
| **Build & ship** | Hacks, tests, releases | [LOCAL_DEV](./LOCAL_DEV.md) → [TESTING](./TESTING.md) → [Contributing](./project/contributing.md) |

---

## Product & reference

| Topic | English | Russian |
|-------|---------|---------|
| **Short description** (GitHub About, press) | [SHORT_DESCRIPTION.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SHORT_DESCRIPTION.md) | [RU](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SHORT_DESCRIPTION.ru.md) |
| **Project story** (for landing & articles) | [OVERVIEW](./OVERVIEW.md) | [RU](./OVERVIEW.ru.md) |
| **Install & deploy** | [INSTALL](./INSTALL.md) | [RU](./INSTALL.ru.md) |
| **Recipes & workflows** | [SCENARIOS](./SCENARIOS.md) | [RU](./SCENARIOS.ru.md) |
| **Config keys & env** | [CONFIGURATION](./CONFIGURATION.md) | [RU](./CONFIGURATION.ru.md) |
| **Terms (Hub, Frigate, merge, …)** | [GLOSSARY](./GLOSSARY.md) | [RU](./GLOSSARY.ru.md) |
| **Feature matrix & API hints** | [FEATURES](./FEATURES.md) | [RU](./FEATURES.ru.md) |
| **System design** | [ARCHITECTURE](./ARCHITECTURE.md) | [RU](./ARCHITECTURE.ru.md) |
| **HTTP API narrative** | [API](./API.md) · [OpenAPI Redoc](./reference/openapi.md) | [RU](./API.ru.md) · [Redoc RU](./reference/openapi.ru.md) |
| **Versioning** | [VERSIONING](./VERSIONING.md) | — |

---

## Security & operations

| Topic | Document |
|-------|----------|
| Access & passwords | [ACCESS_CONTROL](./ACCESS_CONTROL.md) · [RU](./ACCESS_CONTROL.ru.md) |
| Threats & hardening | [SECURITY](./SECURITY.md) |
| Recover broken config | [RECOVERY_CONFIG](./RECOVERY_CONFIG.md) · [RU](./RECOVERY_CONFIG.ru.md) |
| When something fails | [TROUBLESHOOTING](./TROUBLESHOOTING.md) · [RU](./TROUBLESHOOTING.ru.md) |

---

## Quality & tooling

| Topic | Document |
|-------|----------|
| Unit, API, E2E, post-deploy checks | [TESTING](./TESTING.md) · [RU](./TESTING.ru.md) |
| MCP (AI tools) | [MCP_SETUP](./MCP_SETUP.md) · [RU](./MCP_SETUP.ru.md) |

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
| How docs are written (placeholders, i18n, site reuse) | [Documentation](./Documentation.md) · [RU](./Documentation.ru.md) |
| Security analysis (technical) | [SECURITY](./SECURITY.md) · [RU](./SECURITY.ru.md) |
| Open-source release checklist | [OPEN_SOURCE_PREP](./OPEN_SOURCE_PREP.md) · [RU](./OPEN_SOURCE_PREP.ru.md) |
| Governance & external review | [GOVERNANCE](./GOVERNANCE.md) · [RU](./GOVERNANCE.ru.md) |
| **GitHub CLI setup** (personal repo) | [GITHUB_SETUP_GH](./GITHUB_SETUP_GH.md) · [RU](./GITHUB_SETUP_GH.ru.md) |
| **Wiki + CI reports** (Summary / Artifact / optional Wiki push) | [WIKI_AUTOMATION](./WIKI_AUTOMATION.md) · [RU](./WIKI_AUTOMATION.ru.md) |
| Translation status | [I18N_STATUS](./I18N_STATUS.md) |
| **Site sections ↔ files** (keep in sync with `mkdocs.yml`) | [SITE_MAP](./SITE_MAP.md) · [RU](./SITE_MAP.ru.md) |
| **MkDocs site (build & GitHub Pages)** | [Documentation](./Documentation.md) § *Static documentation site* |
| Historical notes | [archive/README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/docs/archive/README.md) (in repo; excluded from MkDocs build) |

---

## Quick commands (from repo)

| Goal | Command |
|------|---------|
| Local stack | `cd app && make local` → http://localhost:8085 |
| Web tests | `cd app && make test-web` |
| Full doc index above | You are here ✓ |
| Preview static doc site | `pip install -r requirements-docs.txt && mkdocs serve` ([details](./Documentation.md)) |

For server deploy patterns, see [INSTALL](./INSTALL.md).

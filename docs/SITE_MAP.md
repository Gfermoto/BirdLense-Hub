# Documentation site map (suggested)

Section → file map for humans and for keeping [`mkdocs.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml) `nav` aligned. The built site is **MkDocs Material** at repo root.

[Русский](./SITE_MAP.ru.md)

---

## Top navigation

| Label | Source file | Notes |
|-------|-------------|--------|
| Overview | [OVERVIEW.md](./OVERVIEW.md) | MkDocs first item |
| Documentation index | [README.md](./README.md) | Topic tables / entry paths |
| GitHub | external | Repository URL |

---

## Sidebar — “Use the hub”

| Page | Source |
|------|--------|
| Quickstart | [QUICKSTART.md](./QUICKSTART.md) |
| Install | [INSTALL.md](./INSTALL.md) |
| Server deploy checklist | [DEPLOY_SERVER.md](./DEPLOY_SERVER.md) · [RU](./DEPLOY_SERVER.ru.md) |
| Scenarios | [SCENARIOS.md](./SCENARIOS.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Features | [FEATURES.md](./FEATURES.md) |
| Domain contract | [DOMAIN_CONTRACT.md](./DOMAIN_CONTRACT.md) · [RU](./DOMAIN_CONTRACT.ru.md) |
| Release readiness | [RELEASE_READINESS.md](./RELEASE_READINESS.md) · [RU](./RELEASE_READINESS.ru.md) |
| Definition of Done (short gate) | [DEFINITION_OF_DONE.md](./DEFINITION_OF_DONE.md) · [RU](./DEFINITION_OF_DONE.ru.md) |
| Troubleshooting | [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) |
| Runbooks | [RUNBOOKS.md](./RUNBOOKS.md) · [RU](./RUNBOOKS.ru.md) |
| Recover config | [RECOVERY_CONFIG.md](./RECOVERY_CONFIG.md) |
| Glossary | [GLOSSARY.md](./GLOSSARY.md) |
| Heimdall tiles | [HEIMDALL.md](./HEIMDALL.md) · [RU](./HEIMDALL.ru.md) |

---

## Sidebar — “Develop & integrate”

| Page | Source |
|------|--------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| HTTP API | [API.md](./API.md) + OpenAPI import |
| OpenAPI (Redoc) | [reference/openapi.md](./reference/openapi.md) · [RU](./reference/openapi.ru.md) |
| Access control | [ACCESS_CONTROL.md](./ACCESS_CONTROL.md) |
| MCP | [MCP_SETUP.md](./MCP_SETUP.md) |
| Local dev | [LOCAL_DEV.md](./LOCAL_DEV.md) |
| CodeQL (CI) | [CODEQL.md](./CODEQL.md) |
| Testing | [TESTING.md](./TESTING.md) |
| CI & quality policy | [CI_AND_QUALITY.md](./CI_AND_QUALITY.md) · [RU](./CI_AND_QUALITY.ru.md) |
| Accessibility | [A11Y.md](./A11Y.md) · [RU](./A11Y.ru.md) |
| UX: Tooltips & inline hints | [UX_TOOLTIPS.md](./UX_TOOLTIPS.md) |
| Review mode & video corrections | [UX_UNKNOWN_VIDEO_CORRECTION.md](./UX_UNKNOWN_VIDEO_CORRECTION.md) |
| Settings: composable triggers (phase 2 draft) | [SETTINGS_TRIGGERS_PHASE2.md](./SETTINGS_TRIGGERS_PHASE2.md) |

---

## Sidebar — “ML & project”

| Page | Source |
|------|--------|
| Training | [TRAINING.md](./TRAINING.md) |
| ML quality loop (RU) | [ML_QUALITY_LOOP.ru.md](./ML_QUALITY_LOOP.ru.md) |
| Datasets | [DATASETS.md](./DATASETS.md) |
| Versioning | [VERSIONING.md](./VERSIONING.md) |
| Roadmap | [ROADMAP.md](./ROADMAP.md) |

---

## Meta (footer or “Project”)

| Page | Source |
|------|--------|
| Contributing | [project/contributing.md](./project/contributing.md) → root `CONTRIBUTING.md` on GitHub |
| Security policy | [project/security-policy.md](./project/security-policy.md) → root `SECURITY.md` |
| Code of Conduct | [project/code-of-conduct.md](./project/code-of-conduct.md) → root `CODE_OF_CONDUCT.md` |
| Changelog | [project/changelog.md](./project/changelog.md) → root `CHANGELOG.md` |
| OpenAPI YAML | [project/openapi.md](./project/openapi.md) → `app/web/openapi.yaml` |
| Root README | [project/root-readme.md](./project/root-readme.md) → root `README.md` |
| Repository layout | [REPOSITORY_LAYOUT.md](./REPOSITORY_LAYOUT.md) · [RU](./REPOSITORY_LAYOUT.ru.md) |
| Verification log (releases) | [VERIFICATION.md](./VERIFICATION.md) · [RU](./VERIFICATION.ru.md) |
| Pre-implementation checklist (repo only; not in MkDocs) | [EN on GitHub](https://github.com/Gfermoto/BirdLense-Hub/blob/main/docs/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.md) · [RU on GitHub](https://github.com/Gfermoto/BirdLense-Hub/blob/main/docs/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md) |
| Doc conventions | [Documentation.md](./Documentation.md) |
| Security analysis (deep dive) | [SECURITY.md](./SECURITY.md) · [RU](./SECURITY.ru.md) |
| Secrets rotation (ops) | [SECRETS_ROTATION.md](./SECRETS_ROTATION.md) · [RU](./SECRETS_ROTATION.ru.md) |
| Open-source prep (maintainers) | [OPEN_SOURCE_PREP.md](./OPEN_SOURCE_PREP.md) · [RU](./OPEN_SOURCE_PREP.ru.md) |
| i18n status | [I18N_STATUS.md](./I18N_STATUS.md) |
| Governance & observer | [GOVERNANCE.md](./GOVERNANCE.md) · [RU](./GOVERNANCE.ru.md) |
| Issues, board & roadmap | [ROADMAP.md](./ROADMAP.md) (Triage) · [RU](./ROADMAP.ru.md); repo root CONTRIBUTING.md |
| GitHub via `gh` CLI | [GITHUB_SETUP_GH.md](./GITHUB_SETUP_GH.md) · [RU](./GITHUB_SETUP_GH.ru.md) |
| Wiki & CI reports | [WIKI_AUTOMATION.md](./WIKI_AUTOMATION.md) · [RU](./WIKI_AUTOMATION.ru.md) |
| OpenAPI bulk path regeneration | [Documentation.md](./Documentation.md#openapi-spec-maintenance) (scripts `merge_openapi_fragments.py` / `generate_openapi_remaining_paths.py`) |

**Implemented generator:** [mkdocs.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/mkdocs.yml) at repo root (MkDocs Material); Russian pages are a section in the same `nav`.

---

## Russian

Mirror each published page as `*.ru.md` or use a `/ru/` locale folder; keep the same structure. See [I18N_STATUS.md](./I18N_STATUS.md).

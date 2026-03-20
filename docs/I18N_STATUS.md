# Documentation — Bilingual Status

English = main (`.md`). Russian = secondary (`.ru.md`).

## Workflow

1. **Structure & rewrite** — information architecture, audience paths, tables over rambling text (technical writer).
2. **EN primary** — ship polished English in `DOC.md` first (basis for site & community).
3. **RU** — mirror in `DOC.ru.md` where needed (translator / maintainer).

“Translate only” is not the default: pages should stay **usable as site sections** and **article source**.

## Archive cleanup (done)

Removed from `archive/`: ROLLBACK_LOST_FEATURES, SYSTEM_UI_AND_FRIGATE_REFERENCE, COLLABORATIVE_LABELING, UX_IMPROVEMENTS, FRIGATE_EVENT_LOSS_AUDIT (content folded into TROUBLESHOOTING). Shortened: REACT_19_MIGRATION.

## Pattern

- `DOC.md` — English (primary)
- `DOC.ru.md` — Russian

Each paired doc links to the other at the top: `[Русский](./DOC.ru.md)` / `[English](./DOC.md)`.

## Status

| Document | EN | RU |
|----------|:--:|:--:|
| **Root** | | |
| README | ✅ | ✅ |
| CONTRIBUTING | ✅ | ✅ |
| CODE_OF_CONDUCT | ✅ | ✅ |
| SECURITY | ✅ | ✅ |
| **docs/** | | |
| README (hub) | ✅ | ✅ |
| OVERVIEW (story / landing source) | ✅ | ✅ |
| INSTALL | ✅ | ✅ |
| Documentation (meta guide) | ✅ | ✅ |
| SCENARIOS | ✅ | ✅ |
| CONFIGURATION | ✅ | ✅ |
| GLOSSARY | ✅ | ✅ |
| FEATURES | ✅ | ✅ |
| TESTING | ✅ | ✅ |
| TROUBLESHOOTING | ✅ | ✅ |
| LOCAL_DEV | ✅ | ✅ |
| ARCHITECTURE | ✅ | ✅ |
| API | ✅ | ✅ |
| MCP_SETUP | ✅ | ✅ |
| ACCESS_CONTROL | ✅ | ✅ |
| RECOVERY_CONFIG | ✅ | ✅ |
| SITE_MAP (static site nav) | ✅ | ✅ |
| TRAINING | ✅ | ✅ |
| DATASETS | ✅ | ✅ |
| ROADMAP | ✅ | ✅ |
| VERSIONING | ✅ | ✅ |
| SECURITY (analysis in docs/) | ✅ | ✅ |
| OPEN_SOURCE_PREP | ✅ | ✅ |

## Adding or refreshing a doc

1. Write or rewrite **English** in `DOC.md` (instructional, placeholders, cross-links).
2. If Russian is required: create/update `DOC.ru.md` (same structure).
3. Register in [docs/README.md](./README.md) (and [README.ru.md](./README.ru.md)).
4. Update this table.

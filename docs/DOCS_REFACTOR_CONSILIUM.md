# Documentation refactor — consilium & review

[Русский](./DOCS_REFACTOR_CONSILIUM.ru.md)

Formal process to **refactor docs in a controlled way** and **close with a review gate**. Roles can be one person checking each lens in order.

---

## Roles (the “consilium”)

| Role | Focus |
|------|--------|
| **Librarian** | `docs/` structure, duplicates, [SITE_MAP](./SITE_MAP.md), `mkdocs.yml` **nav**, `archive/` |
| **Operator** | [INSTALL](./INSTALL.md), [SCENARIOS](./SCENARIOS.md), [CONFIGURATION](./CONFIGURATION.md) match real deploy |
| **Integrator** | [API](./API.md), OpenAPI, examples, no secrets / real hosts |
| **New reader** | “Run” path from [docs/README](./README.md) without insider jargon |
| **i18n** | EN/RU pairs, [I18N_STATUS](./I18N_STATUS.md) |

---

## Phases

1. **Inventory** — list targets (files or sections); note conflicts with SITE_MAP/nav.
2. **Principles** — single source of truth, remove duplication, placeholders (`YOUR_HOST`), bilingual when user-facing.
3. **Execute** — small PRs (e.g. one area per PR).
4. **Review** — use the checklist below; record outcome (pass / changes requested).

---

## Review checklist (mandatory after each batch)

- [ ] `mkdocs build --strict` passes locally or in CI.
- [ ] No live secrets, tokens, or private IPs (see [SECURITY](./SECURITY.md)).
- [ ] Internal `docs/` links valid; off-site links intentional (blob URLs OK for strict).
- [ ] User-visible behavior change → [CHANGELOG](./project/changelog.md) (repo root file).
- [ ] If version/banner touched → `VERSION` + `mkdocs.yml` `extra.site_version` aligned ([VERSIONING](./VERSIONING.md)).

---

## Minutes template (issue or discussion)

```markdown
## Docs consilium — YYYY-MM-DD
**Scope:** (files / theme)
**Participants:** (names or "solo, all roles")
**Decisions:** (bullet list)
**Review:** checklist pass / follow-ups: …
```

Conventions: [Documentation](./Documentation.md) · Governance: [GOVERNANCE](./GOVERNANCE.md)

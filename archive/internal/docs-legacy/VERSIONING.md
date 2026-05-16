# Versioning — BirdLense Hub

[Русский](./VERSIONING.ru.md)

---

## Scheme

We follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

| Part | When to bump |
|------|----------------|
| **MAJOR** | Breaking API or configuration changes |
| **MINOR** | New functionality, backward compatible |
| **PATCH** | Bug fixes, small safe improvements |

Examples:

- `0.1.0` → `0.1.1` — bugfix
- `0.1.1` → `0.2.0` — new feature (e.g. new motion trigger type)
- `1.0.0` → `2.0.0` — breaking change (e.g. config format)

---

## Where the version lives

| File | Purpose |
|------|---------|
| `VERSION` | Single source of truth (repo root) |
| `app/ui/package.json` | UI package version |
| `app/web/openapi.yaml` | API version in OpenAPI |

Bump **the same version string** everywhere below (**[#120](https://github.com/Gfermoto/BirdLense-Hub/issues/120)** checklist).

1. Root **`VERSION`**
2. **`app/ui/package.json`** → `version`
3. **`app/web/openapi.yaml`** → `info.version`
4. **`mkdocs.yml`** → `extra.site_version` (and **`overrides/main.html`** banner if needed)
5. **`CHANGELOG.md`**

Verify from the repo root:

```bash
python3 scripts/check-docs-version.py
```

This checks `VERSION` against `mkdocs.yml`, `package.json`, and `openapi.yaml`. In CI the same script runs in the **`openapi-contract`** job and again in the **`docs`** job before MkDocs (see [TESTING](./TESTING.md) §1). The site banner comes from **`overrides/main.html`** (`announce` block), not `theme.announcement` in YAML.

---

## Releases and tags

1. **Before release:** bump `VERSION`, `package.json`, `openapi.yaml`, and edit **`CHANGELOG.md`** at the repository root (see [Changelog](./project/changelog.md) for the canonical location). Close/update **Issues** and the **Roadmap** project board (see [ROADMAP](./ROADMAP.md) § *Reporting* and root [CONTRIBUTING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md)).
2. **Commit:** `git add -A && git commit -m "Release v0.1.0"`
3. **Tag:** `git tag -a v0.1.0 -m "Release v0.1.0"`
4. **Push:** `git push && git push origin v0.1.0`
5. **GitHub Release:** create from tag; paste notes from CHANGELOG

### GitHub Actions after a release

- **Docker:** [docker-publish.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docker-publish.yml) — `main` + **published** Release → `latest` + semver tag.
- **Docs site:** [docs-pages.yml](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docs-pages.yml) — deploy Pages только с ветки **`main`** (push по путям или `workflow_dispatch`). После merge релиза этого достаточно; деплой с тега не используется (ограничения окружения `github-pages`).

Wiki (optional): [WIKI_AUTOMATION](./WIKI_AUTOMATION.md).

---

## CHANGELOG

Format: [Keep a Changelog](https://keepachangelog.com/).

Sections: **Added**, **Changed**, **Deprecated**, **Removed**, **Fixed**, **Security**.

---

## Upgrades

- **Minor / patch (`0.x.y`):** usually `make deploy` or `make pull`; user config and data are preserved.
- **Major:** read release notes — migrations may be required.

---

## See also

[Changelog](./project/changelog.md) · [INSTALL](./INSTALL.md)

# GitHub ecosystem — how the pieces fit together

[Русский](./GITHUB_ECOSYSTEM.ru.md)

BirdLense Hub uses several GitHub features at once. This page explains **what is canonical**, what is **optional**, and how **releases** tie to **Docker** and **Pages**.

---

## Single source of truth

| Need | Canonical place | Not a substitute for |
|------|-----------------|----------------------|
| Install, API, architecture, config | **`docs/`** in the repo → published as **GitHub Pages** | Wiki alone |
| Public README / short “About” text | Root **`README.md`**, **`SHORT_DESCRIPTION.md`** | — |
| Roadmap wording | **`docs/ROADMAP.md`** / **`docs/ROADMAP.ru.md`** | Board columns without repo text |
| Version number | Root **`VERSION`**, plus `app/ui/package.json`, `app/web/openapi.yaml`, `mkdocs.yml` → `extra.site_version` | Git tag alone (tag must match after bump) |

---

## GitHub Pages (documentation site)

- **URL:** configured in repo **Settings → Pages** (e.g. `https://gfermoto.github.io/BirdLense-Hub/`).
- **Built by:** [`.github/workflows/docs-pages.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docs-pages.yml) (MkDocs Material).
- **Deploy rule:** the site deploys when there is a push to **`main`** that touches docs (or related paths), on **`workflow_dispatch`**, or when a **GitHub Release is published** — so a release updates Pages even if only root files (e.g. `VERSION`) changed.
- **Stars/forks/version chip** in the header: Material loads GitHub API data; the displayed doc version is aligned with **`VERSION`** via `overrides/main.html` (see [VERSIONING](./VERSIONING.md)).

---

## Docker image (GHCR)

- **Workflow:** [`.github/workflows/docker-publish.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/docker-publish.yml).
- **Triggers:** push to **`main`**, and **`release: published`**.
- **Tags:** `ghcr.io/…/birdlense-hub:latest` is updated on **main** and on **published releases**; a semver tag (e.g. `0.2.2`) is added when you **publish** a Release (not for draft releases).
- If a package did not appear: check **Actions** for failed runs, and confirm the Release is **Published** (not draft). Pre-releases still fire `release: published` in GitHub Actions.

---

## Wiki

- **Separate Git repo** from the main code (`*.wiki.git`). Does **not** run MkDocs.
- **Optional automation:** [WIKI_AUTOMATION](./WIKI_AUTOMATION.md) — CI writes a report to the job Summary, Artifact, and optionally pushes to Wiki if **`WIKI_PUSH_TOKEN`** is set.
- Use Wiki for short operator notes or links; **do not** treat it as the primary manual.

---

## Discussions vs Issues

| Area | Use for |
|------|---------|
| **Discussions** | Ideas, Q&A, show-and-tell, long threads |
| **Issues** | Actionable bugs, concrete tasks, regressions |

Link Discussions from README; keep **labels** and templates consistent ([Contributing](./project/contributing.md)).

---

## Roadmap and GitHub Projects

- **In-repo roadmap:** `docs/ROADMAP.md` (and `.ru.md`) — narrative and shipped checklist.
- **GitHub Projects (board):** optional visual layer; cards are usually **Issues** (or draft items). The board does **not** replace the Markdown roadmap: import or create issues from real backlog, and avoid duplicating already-shipped work (see ROADMAP + [FEATURES](./FEATURES.md)).

---

## Release checklist (maintainer)

1. Merge work into **`main`**.
2. Bump **`VERSION`**, **`app/ui/package.json`**, **`app/web/openapi.yaml`**, **`mkdocs.yml`** → `extra.site_version`, **`CHANGELOG.md`**.
3. Commit, tag **`vX.Y.Z`**, push branch + tag.
4. GitHub → **Releases → Draft a new release** → choose tag → **Publish release** (not draft).
5. Verify **Actions**: Docker workflow green; docs workflow green; **Packages** shows new tags; **Pages** shows new version after cache refresh.

See [VERSIONING](./VERSIONING.md) for details.

---

## See also

[GITHUB_SETUP_GH](./GITHUB_SETUP_GH.md) · [WIKI_AUTOMATION](./WIKI_AUTOMATION.md) · [VERSIONING](./VERSIONING.md) · [Contributing](./project/contributing.md)

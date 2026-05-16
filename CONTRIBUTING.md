# Contributing to BirdLense Hub

Thank you for your interest in contributing to BirdLense Hub.

**Issues & board:** [docs/contributor/roadmap.md](docs/contributor/roadmap.md) (triage + reporting) and § *Issues & Project board* below.

### Maintainer / contributor workflow (end to end)

When you own a change, carry it through the full cycle unless you agreed otherwise (e.g. draft only, no push):

1. **Code** — match existing style; run relevant tests / linters locally (`app/`, e.g. `make test-web`; CI covers more).
2. **Docs & changelog** — update `docs/*` when operators or integrators need new facts; user-visible changes → [CHANGELOG.md](CHANGELOG.md).
3. **Git** — meaningful commits; **push** to the agreed branch (usually `dev`) unless the task was local-only.
4. **Release path** — feature work merges to **`dev`** first; promotion **`dev` → `main`** is a separate maintainer PR after green CI. Link PRs in Issues and close them when done; update the **BirdLense Hub — Roadmap** board (**Done**) where applicable (see scripts under `scripts/github-project-*.sh` and [docs/contributor/roadmap.md](docs/contributor/roadmap.md)).
5. **Deploy** — when the running hub must pick up your code: from repo root **`make deploy`** (see [docs/user/install.md](docs/user/install.md) § *Deploy to server*).
6. **Verify** — after deploy or CI changes, confirm health / logs or workflow success as appropriate.

## How to contribute

### Branching (two steps to production)

| Step | Branch flow | Who |
|------|-------------|-----|
| **1** | `feature/*` (from **`dev`**) → **Pull Request into `dev`** | Contributors |
| **2** | **`dev`** → **Pull Request into `main`** | Maintainers (release) |

Do **not** open feature PRs **directly** to `main`. Integrate on `dev` first; only then promote to `main`.

After your PR into `dev` is merged, GitHub **deletes the feature branch** automatically so branches do not pile up. Long-lived **`main`** and **`dev`** stay: they are **protected from deletion**.

1. **Clone** [BirdLense-Hub](https://github.com/Gfermoto/BirdLense-Hub) (or **fork** it to your account if you prefer) and create a branch from **`dev`**.
2. **Make changes** — follow existing code style and conventions.
3. **Test** — in `app/`: `make test` and `make test-web` (Docker), or ensure the PR is green in CI: **`python-security`**, **`openapi-contract`**, **`ui-build`**, **`docs`**, **`docker-tests`** (see [docs/contributor/testing.md](docs/contributor/testing.md) §1). **CodeQL** runs separately ([archive/internal/docs-legacy/CODEQL.md](archive/internal/docs-legacy/CODEQL.md)); not required by default.
4. **Open a Pull Request** with base branch **`dev`**.

**Second pair of eyes:** use a human reviewer for merges to protected branches. See [GOVERNANCE.md](GOVERNANCE.md) (how to add an observer on GitHub; only a real GitHub account can accept a collaborator invite—use a bot or GitHub App for automation).

## Development setup

```bash
git clone https://github.com/YOUR_USER/BirdLense-Hub.git
cd BirdLense-Hub/app
make build
make start
```

See [docs/contributor/local-dev.md](docs/contributor/local-dev.md) for details.

## Documentation

- **Repository layout:** [docs/contributor/repository-layout.md](docs/contributor/repository-layout.md) — where `app/`, `docs/`, and `scripts/` fit together.
- **Index:** [docs/index.md](docs/index.md) — how guides are grouped (user / contributor / RU).
- **Narrative for readers & press:** [docs/user/overview.md](docs/user/overview.md).
- **Conventions:** [docs/contributor/documentation.md](docs/contributor/documentation.md) (placeholders, bilingual files, MkDocs). **Terms:** [docs/user/glossary.md](docs/user/glossary.md).
- User-visible behavior change → update the relevant guide and [CHANGELOG.md](CHANGELOG.md).

## Code style

- **Python:** Follow PEP 8. Use type hints where practical.
- **TypeScript/React:** ESLint, Prettier (project config).
- **Docs:** Markdown, short sections and tables; placeholders (`YOUR_HOST`, `your-token`) instead of real values.

## Issues & Project board (accountability)

**All substantive work** must be reflected in **GitHub Issues** and, when the item is on it, on the **BirdLense Hub — Roadmap** project — including work **outside** the [Roadmap consilium](docs/contributor/roadmap.md) table (CI-only, docs, chores). Comment with outcomes + PR links, **close** issues when done, set board **Status** to **Done** (or `bash scripts/github-project-mark-done.sh <n>` with PAT `repo` + `project`). **Deferred ideas** without a current implementation scope may be recorded only in [roadmap](docs/contributor/roadmap.md) until a new issue is opened.

## Pull request guidelines

- Keep PRs focused — one feature or fix per PR.
- Add tests for new API endpoints or processor logic.
- Update documentation if behavior changes.
- Ensure **`make test`** and **`make test-web`** pass in `app/` (Docker), or the PR is green in CI (all jobs in [docs/contributor/testing.md](docs/contributor/testing.md) §1).
- For PRs that materially change **UI placement** or add a new surface (`area:web`): in the PR description, briefly confirm the **UX-context gate** (after [#114](https://github.com/Gfermoto/BirdLense-Hub/issues/114)): which page owns the user intent, whether data/API flow reuses existing patterns, and what would feel wrong to an operator.

### Maintainer checklist (before release)

See [docs/contributor/local-dev.md](docs/contributor/local-dev.md) § *Maintainer checklist* — from repo root **`make ci-local`** (or **`make ci-local-docker`** for image + Playwright smoke), `make test` / `make test-web` in `app/`, `mkdocs build --strict`, optional E2E, post-deploy smoke.

## Reporting issues

- Use GitHub Issues; when closing work, update the board as in § *Issues & Project board* above.
- For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## Questions

Use **[GitHub Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions)** for Q&A and ideas, or open an **Issue** for bugs and concrete work.

## Good first issues

Look for issues labelled **`good first issue`** — small, scoped tasks for newcomers. Maintainers: when filing such an issue, describe expected files, acceptance criteria, and link to relevant docs (`docs/contributor/local-dev.md`, `docs/contributor/testing.md`).

## Community

- **Discussions:** https://github.com/Gfermoto/BirdLense-Hub/discussions  
- **Security:** follow [SECURITY.md](SECURITY.md) — do not report vulnerabilities in public threads.

## GitHub Projects (maintainers)

**Issues**, **Discussions**, and **Projects** are enabled on the repo. Labels `area:*`, `priority:*`, and `triage` support triage; milestones **v0.2.3** and **Backlog (no milestone)** are available.

To create the Kanban project **BirdLense Hub — Roadmap** and link this repository, `gh` must reach the **Projects** API. OAuth + `gh auth refresh -s project` often loops through device login — **use a classic PAT** instead:

1. [New classic token](https://github.com/settings/tokens/new) → enable **repo** + **project**.
2. `cp scripts/env.project.example scripts/.env.project` and set `export GH_TOKEN="ghp_…"` (file is gitignored via `.env.*`), **or** run `export GH_TOKEN=ghp_…` for one session.
3. `bash scripts/github-bootstrap-project.sh`

New projects start **empty**. To add all **open issues and PRs** to the board:

```bash
bash scripts/github-project-import-open-items.sh
```

Roadmap backlog issues **#46–#48, #50–#57** (see [docs/contributor/roadmap.md](docs/contributor/roadmap.md); **#49** skipped — x86-only):

```bash
bash scripts/github-project-add-backlog-consilium.sh
```

After closing an issue that is already on the board, mark **Status** and **Поток** as **Done** (same `GH_TOKEN` / `.env.project`):

```bash
bash scripts/github-project-mark-done.sh 46
bash scripts/github-project-mark-done.sh 46 57
```

GitHub **sub-issue** hierarchy (board column, parent on the issue page): use `scripts/github-issue-link-subissues.sh` (full tech-debt tree example: `bash scripts/github-issue-link-subissues.sh 220 198 201 221 222 223 224 225`).

On **WSL**, `gh project view … --web` often fails (`xdg-open: Permission denied`); open the printed **https://github.com/users/…/projects/N** link in your Windows browser instead.

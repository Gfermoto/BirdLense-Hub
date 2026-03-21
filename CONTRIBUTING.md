# Contributing to BirdLense Hub

Thank you for your interest in contributing to BirdLense Hub.

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
3. **Test** — in `app/`: `make test` and `make test-web` (Docker), or ensure the PR is green in CI (**`ui-build`**, **`docs`**, **`docker-tests`**).
4. **Open a Pull Request** with base branch **`dev`**.

**Second pair of eyes:** maintainers should use a human reviewer for merges to protected branches. See [docs/GOVERNANCE.md](docs/GOVERNANCE.md) (how to add an observer on GitHub and why AI assistants cannot accept repo invites).

## Development setup

```bash
git clone https://github.com/YOUR_USER/BirdLense-Hub.git
cd BirdLense-Hub/app
make build
make start
```

See [docs/LOCAL_DEV.md](docs/LOCAL_DEV.md) for details.

## Documentation

- **Index:** [docs/README.md](docs/README.md) — how guides are grouped (run / integrate / build).
- **Narrative for readers & press:** [docs/OVERVIEW.md](docs/OVERVIEW.md).
- **Conventions:** [docs/Documentation.md](docs/Documentation.md) (placeholders, bilingual files, reusing docs for a static site). **Terms:** [docs/GLOSSARY.md](docs/GLOSSARY.md).
- User-visible behavior change → update the relevant guide and [CHANGELOG.md](CHANGELOG.md).

## Code style

- **Python:** Follow PEP 8. Use type hints where practical.
- **TypeScript/React:** ESLint, Prettier (project config).
- **Docs:** Markdown, short sections and tables; placeholders (`YOUR_HOST`, `your-token`) instead of real values.

## Pull request guidelines

- Keep PRs focused — one feature or fix per PR.
- Add tests for new API endpoints or processor logic.
- Update documentation if behavior changes.
- Ensure **`make test`** and **`make test-web`** pass in `app/` (Docker), or the PR is green in CI (**`ui-build`**, **`docs`**, **`docker-tests`**).

### Maintainer checklist (before release)

See [docs/LOCAL_DEV.md](docs/LOCAL_DEV.md) § *Maintainer checklist* — `make test` / `make test-web`, `mkdocs build --strict`, optional E2E, post-deploy smoke.

## Reporting issues

- Use GitHub Issues.
- For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## Questions

Use **[GitHub Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions)** for Q&A and ideas, or open an **Issue** for bugs and concrete work.

## Good first issues

Look for issues labelled **`good first issue`** — small, scoped tasks for newcomers. Maintainers: when filing such an issue, describe expected files, acceptance criteria, and link to relevant docs (`docs/LOCAL_DEV.md`, `docs/TESTING.md`).

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

Roadmap backlog issues **#46–#48, #50–#57** (see [docs/ROADMAP.md](docs/ROADMAP.md); **#49** skipped — x86-only):

```bash
bash scripts/github-project-add-backlog-consilium.sh
```

On **WSL**, `gh project view … --web` often fails (`xdg-open: Permission denied`); open the printed **https://github.com/users/…/projects/N** link in your Windows browser instead.

# Contributing to BirdLense Hub

Thank you for your interest in contributing to BirdLense Hub.

## How to contribute

1. **Fork** the repository and create a branch from `dev`.
2. **Make changes** — follow existing code style and conventions.
3. **Test** — run `make test-web` in `app/` before submitting.
4. **Submit a Pull Request** to the `dev` branch.

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
- Ensure `make test-web` passes.

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

To create the Kanban project **BirdLense Hub — Roadmap** and link this repository, GitHub CLI needs **Projects** scopes. If `gh auth refresh -s project -s read:project` does nothing, do a full login (or use a **classic** PAT with the `project` scope as `GH_TOKEN` — see script header):

```bash
gh auth logout -h github.com
gh auth login -h github.com -w -s repo -s read:org -s gist -s project -s read:project
bash scripts/github-bootstrap-project.sh
```

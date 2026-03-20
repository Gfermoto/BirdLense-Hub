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

Open a Discussion or Issue on GitHub.

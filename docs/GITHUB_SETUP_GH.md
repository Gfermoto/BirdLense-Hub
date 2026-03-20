# GitHub setup via `gh` CLI (personal repo)

Full Russian walkthrough: **[GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md)** (for `Gfermoto/BirdLense-Hub`).

**Do not paste PATs into chat.** Use `gh auth login` locally, then:

```bash
./scripts/github-repo-bootstrap.sh
```

Branch protection payload: `scripts/github-branch-protection-main.json`.

Wiki + CI reports: [WIKI_AUTOMATION.md](./WIKI_AUTOMATION.md).

Set default repo for `gh` (avoids wrong target on `pr merge`):

```bash
gh repo set-default Gfermoto/BirdLense-Hub
```

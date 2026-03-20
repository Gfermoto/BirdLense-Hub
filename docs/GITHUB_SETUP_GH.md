# GitHub setup via `gh` CLI (personal repo)

Full Russian walkthrough: **[GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md)** (for `Gfermoto/BirdLense-Hub`).

**Do not paste PATs into chat.** Use `gh auth login` locally, then:

```bash
./scripts/github-repo-bootstrap.sh
```

Branch protection: use [`scripts/github-branch-protection-main.json`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/github-branch-protection-main.json) for **both** `main` and `dev` (`allow_deletions: false`). Turn off **Automatically delete head branches** so merging `dev` → `main` does not delete `dev`. Ruleset **Protect** + required checks **`ui-build`** / **`docs`** — see the Russian guide.

Wiki + CI reports: [WIKI_AUTOMATION.md](./WIKI_AUTOMATION.md).

Set default repo for `gh` (avoids wrong target on `pr merge`):

```bash
gh repo set-default Gfermoto/BirdLense-Hub
```

# GitHub setup via `gh` CLI (personal repo)

Full Russian walkthrough: **[GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md)** (for `Gfermoto/BirdLense-Hub`).

**Do not paste PATs into chat.** Use `gh auth login` locally, then:

```bash
./scripts/github-repo-bootstrap.sh
```

Branch protection: [`scripts/github-branch-protection-main.json`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/github-branch-protection-main.json) for **both** `main` and `dev` (`allow_deletions: false`). **Workflow:** feature PR → **`dev`**, then **`dev` → `main`**. Turn **on** **Automatically delete head branches** so merged feature branches are removed; protected `main`/`dev` are not deleted. Rulesets + **`ui-build`** / **`docs`** / **`docker-tests`** — see [GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md) §4.

Wiki + CI reports: [WIKI_AUTOMATION.md](./WIKI_AUTOMATION.md).

Set default repo for `gh` (avoids wrong target on `pr merge`):

```bash
gh repo set-default Gfermoto/BirdLense-Hub
```

**Projects / Kanban scripts:** if `gh auth refresh -s project` loops forever, use a **classic PAT** (`repo` + `project`) as `GH_TOKEN` or in `scripts/.env.project` — see [GITHUB_SETUP_GH.ru.md](./GITHUB_SETUP_GH.ru.md) §7a and `scripts/env.project.example`.

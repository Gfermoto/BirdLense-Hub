# GitHub Issues & Project — reporting (accountability)

[Русский](./PROJECT_REPORTING.ru.md)

---

**Rule:** every meaningful piece of work must be **visible in GitHub** — in **Issues** and, when the item is on it, on the **Project** board (**BirdLense Hub — Roadmap**). This applies to **all** work, not only rows from the [Roadmap consilium](./ROADMAP.md).

## Why

- Traceability: what shipped, when, and in which PR.
- The board is the single place to see status for you and collaborators.

## When you finish (or partially ship) work

1. **Issue already exists**  
   - Comment: short summary, link to PR(s) / commit / release tag if relevant.  
   - **Close** the issue when the definition of done is met.  
   - If the issue is on the Project: set **Status** (and **Поток** if used) to **Done** — manually in the UI or via  
     `bash scripts/github-project-mark-done.sh <number> [more numbers…]`  
     (requires a **classic PAT** with `repo` + `project` in `scripts/.env.project`; see [GITHUB_SETUP_GH.md](./GITHUB_SETUP_GH.md)).

2. **No issue yet**  
   - Open an **Issue** (labels `area:*`, `priority:*` as appropriate), or start from a **Discussion** if the scope is unclear, then open an Issue.  
   - Add the card to the **Roadmap** project if it is ongoing/planned work.

3. **Partial delivery** (e.g. phase A+B done, C later)  
   - Comment what is done and what remains; leave the issue **open** until the remaining scope is closed (or split a follow-up issue and link it).

4. **Work outside the consilium table** (CI, docs-only, chore)  
   - Still use an Issue (or one umbrella “chore” issue per sprint if you prefer) so the board and history stay honest.

## Automation & CLI access

- Mark issues Done on the board: **`scripts/github-project-mark-done.sh`**.  
- If `gh project list` fails with missing scope:  
  `gh auth refresh -s read:project`  
  (and project **write** scopes if you edit fields from the CLI).

## Related

- [CONTRIBUTING.md](../CONTRIBUTING.md) — branching and PRs.  
- [AGENTS.md](../AGENTS.md) — agent checklist including reporting.  
- [Roadmap](./ROADMAP.md) — backlog source; reporting is **broader** than this table.

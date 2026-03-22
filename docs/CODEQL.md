# CodeQL (static analysis in CI)

[Русский](./CODEQL.ru.md)

---

GitHub **CodeQL** runs in workflow **`.github/workflows/codeql.yml`** (repository root) on **push/PR** to `main` and `dev`, plus a **weekly** schedule.

## What is analyzed

| Language | Scope (see `.github/codeql/`) |
|----------|-------------------------------|
| **JavaScript / TypeScript** | `app/ui/src` |
| **Python** | `app/web`, `app/processor` (excluding `app/processor/models` and `**/tests/**`) |

## Where to see results

On **GitHub.com**: **Security** → **Code scanning** (alerts and history).  
Forks and private repos need **GitHub Advanced Security** for full UI; the workflow still runs and uploads SARIF when permissions allow.

## Local development (optional)

1. Install the [CodeQL extension for VS Code](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-codeql) (or use the CodeQL CLI).
2. Clone the [CodeQL repo](https://github.com/github/codeql) or use the extension’s bundle to run queries against a local database created from this repository.

CI does **not** need to be green in branch protection unless you add **CodeQL** as a required check in the repository ruleset.

## Related

- [SECURITY.md](./SECURITY.md) — threat model and manual review topics  
- [TESTING.md](./TESTING.md) — runtime tests (pytest, Docker)

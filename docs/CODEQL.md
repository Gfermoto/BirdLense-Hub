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

### Cursor / VS Code

The repo recommends the [CodeQL extension](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-codeql) via `.vscode/extensions.json`. After a local run, use **CodeQL: View SARIF** or open a database from `.tools/codeql-dbs/`.

### CLI

Run **`scripts/codeql-local.sh`** (requires `gh`, `unzip`, Node **22+**, Python 3.12+). It downloads the CodeQL bundle under `.tools/` (gitignored), installs query packs under `~/.codeql/packages`, builds databases, and writes SARIF to `.tools/codeql-results/`.

### Sample review (security-extended)

Latest local run: **4** Python + **1** JavaScript finding — see the table in [CODEQL.ru.md](./CODEQL.ru.md) (Russian section “Пример результата ревью”) for triage notes (ReDoS on species regex, path-injection guarded by `_is_safe_image_path`, SW `postMessage` origin).

CI does **not** need to be green in branch protection unless you add **CodeQL** as a required check in the repository ruleset.

## Related

- [SECURITY.md](./SECURITY.md) — threat model and manual review topics  
- [TESTING.md](./TESTING.md) — runtime tests (pytest, Docker)

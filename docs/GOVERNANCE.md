# Governance & external observer

How to avoid a **single-person bottleneck** and ensure important changes get a second pair of eyes.

[Русский](./GOVERNANCE.ru.md)

---

## Secrets and automation on GitHub

**Collaborator invites** are accepted only by a **real GitHub user**. Scripts and headless tools do not “join” the repo as people—use a **dedicated bot account** or **GitHub App** with least privilege for automation.

**Do not paste** into public forums, shared logs, or untrusted channels:

- PATs with `repo`, `workflow`, or `admin`
- Deploy keys with **write** to production
- GitHub Actions secret values

---

## Human external observer

An **observer** is a trusted person who reviews PRs, releases, security-sensitive changes, and docs.

### Grant access

1. Repo → **Settings** → **Collaborators** / **Manage access**.
2. **Add people**.
3. Role:
   - **Read** — view only (may be enough for commentary depending on your workflow).
   - **Triage** — labels/milestones on issues.
   - **Write** — typical if they must **approve** PRs under branch protection.

See: [Repository roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/repository-roles-for-an-organization).

### Require review on `main`

1. **Settings** → **Rules** → **Rulesets** (or **Branches** → branch protection).
2. For `main`: require PRs, **required approvals** ≥ 1 (often 1–2), optionally **Code owners**.

Then every merge to `main` goes through a PR and **human approval**.

### CODEOWNERS

Edit [.github/CODEOWNERS](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/CODEOWNERS) with real GitHub usernames and optional path-specific owners.

---

## Observer quick checklist

- No secrets in diff; aligns with **SECURITY.md**.
- User-visible impact reflected in CHANGELOG / docs.
- CI green; release tags/artifacts OK.
- License compatibility for new deps/assets.

PR template: [.github/PULL_REQUEST_TEMPLATE.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/PULL_REQUEST_TEMPLATE.md).

---

## GitHub setup via `gh` (personal account)

See [GITHUB_SETUP_GH.md](./GITHUB_SETUP_GH.md) and `scripts/github-repo-bootstrap.sh` — no tokens in chat.

---

## Automated signals (not a substitute for humans)

- Dependabot + timely alert triage.
- Dependency review workflow on PRs.
- CodeQL where available.
- Periodic [OpenSSF Scorecard](https://github.com/ossf/scorecard) runs.

---

## Summary

| Role | Responsibility |
|------|------------------|
| **Maintainer** | Implement, open PRs, release after review |
| **Observer (collaborator)** | Approve PRs, security/docs feedback |
| **Bot / GitHub App** | Automation with scoped tokens—not a substitute for design review |

Trust is enforced by **process**: PR + human approval.

# Governance & external observer

How to avoid a **single-person bottleneck** and ensure important changes get a second pair of eyes (including when using an AI coding assistant in the IDE).

[Русский](./GOVERNANCE.ru.md)

---

## AI and GitHub access

A Cursor assistant **is not a GitHub account** and **cannot accept a collaborator invite**. Work happens against your **local clone**.

**Do not share** with assistants or public chats:

- PATs with `repo`, `workflow`, or `admin`
- Deploy keys with **write** to production
- GitHub Actions secret values

Use a **dedicated bot account** or **GitHub App** with least privilege.

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

Then merges to `main` (including AI-suggested patches) go through a PR and **human approval**.

### CODEOWNERS

Edit [.github/CODEOWNERS](../.github/CODEOWNERS) with real GitHub usernames and optional path-specific owners.

---

## Observer quick checklist

- No secrets in diff; aligns with **SECURITY.md**.
- User-visible impact reflected in CHANGELOG / docs.
- CI green; release tags/artifacts OK.
- License compatibility for new deps/assets.

PR template: [.github/PULL_REQUEST_TEMPLATE.md](../.github/PULL_REQUEST_TEMPLATE.md).

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
| **IDE AI** | Suggests local patches; **no** GitHub tokens |

Trust is enforced by **process**: PR + human approval, not by giving the AI repo admin.

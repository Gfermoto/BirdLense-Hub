# Wiki & CI reports

GitHub **Wiki does not execute scripts** — it is a separate Git repo of Markdown. Scripts run in **Actions**; output is visible in the **job Summary**, **Artifacts**, and optionally pushed to Wiki as **Latest-CI-Report**.

[Русский](./WIKI_AUTOMATION.ru.md)

## Enable Wiki

**Settings → General → Features → Wikis**, or:

```bash
gh api "repos/OWNER/REPO" -X PATCH -f has_wiki=true
```

## Optional: push to Wiki (`WIKI_PUSH_TOKEN`)

The default `GITHUB_TOKEN` cannot push to the wiki remote. Create a **classic PAT** with **`repo`** scope, add repository secret **`WIKI_PUSH_TOKEN`**, then run workflow **Wiki report**.

## Files

- `scripts/generate-wiki-report.sh` — builds the report
- `scripts/push-wiki-report.sh` — pushes to `*.wiki.git` (CI + secret)
- `wiki-source/Home.md` — static wiki home copied on each push
- `.github/workflows/wiki-report.yml`

# Wiki & CI reports

GitHub **Wiki does not execute scripts** — it is a separate Git repo of Markdown. Scripts run in **Actions**; output is visible in the **job Summary**, **Artifacts**, and optionally pushed to Wiki as **Latest-CI-Report**.

[Русский](./WIKI_AUTOMATION.ru.md)

## Enable Wiki

**Settings → General → Features → Wikis**, or:

```bash
gh api "repos/OWNER/REPO" -X PATCH -f has_wiki=true
```

You must also open the **Wiki** tab once and **Create the first page** (any title/body → Save). Until then, `https://github.com/OWNER/REPO.wiki.git` may return **Repository not found**.

## `Repository not found` on push

Usually: Wikis disabled, no first wiki page yet, wrong token type (prefer **classic PAT** with **`repo`**; fine-grained often fails for `*.wiki.git`), or token from an account without repo access.

## Optional: push to Wiki (`WIKI_PUSH_TOKEN`)

The default `GITHUB_TOKEN` cannot push to the wiki remote. Create a **classic PAT** with **`repo`** scope, add repository secret **`WIKI_PUSH_TOKEN`**, then run workflow **Wiki report**.

## Run manually

Direct page (shows **Run workflow** on the right):

`https://github.com/Gfermoto/BirdLense-Hub/actions/workflows/wiki-report.yml`

Or CLI:

```bash
gh workflow run "Wiki report" --repo Gfermoto/BirdLense-Hub --ref main
```

If the workflow is missing, confirm the file exists on the default branch and Actions are not disabled in repo **Settings → Actions → General**.

## Files

- `scripts/generate-wiki-report.sh` — builds the report
- `scripts/push-wiki-report.sh` — pushes to `*.wiki.git` (CI + secret)
- `wiki-source/Home.md` — static wiki home copied on each push
- `.github/workflows/wiki-report.yml`

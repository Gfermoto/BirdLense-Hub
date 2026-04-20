# Definition of Done (release gate) — BirdLense Hub

[Русский](./DEFINITION_OF_DONE.ru.md)

One-page gate before you tag a release, merge a stabilization branch, or tell others the hub is “production ready”. For the **full** checklist (domain health, registry, CI secrets), see [RELEASE_READINESS](./RELEASE_READINESS.md).

---

## Must pass (automated)

1. From the **repository root**: `make ci-local` — green end-to-end (Python security + Ruff + `pytest web/tests/`, OpenAPI codegen drift, UI Vitest + typecheck + lint + `vite build`, Settings UI coverage script, MkDocs `--strict`).  
   - Optional stricter path: `make ci-local-docker` (adds Docker image tests + Playwright smoke; needs Docker, weights fetch, Node **≥ 22**).
2. Deploy or staging URL: `BASE_URL=https://your-hub/ make verify` (or `scripts/verify-stack.sh --base-url …`) — **`verify-stack: PASS`** (health, readiness, status as appropriate).

## Five-minute manual smoke (operator)

Do this on the **same** build you are releasing (staging or production):

| # | Check | Pass? |
|---|--------|--------|
| 1 | Open **Library** — recent clips load; no permanent spinner. | ☐ |
| 2 | Open **System** — readiness shows **ready** (or only expected optional gaps you accept). | ☐ |
| 3 | Open **Settings → Processor** (admin) — save a trivial safe change and confirm success (or cancel without error). | ☐ |
| 4 | Live or test stream — **one** motion/recording cycle completes without processor crash loop. | ☐ |
| 5 | If Frigate/MQTT matters — one event path still works (or consciously skipped with a note in the release notes). | ☐ |

## Document the release

- [ ] `CHANGELOG.md` entry (user-visible changes, migrations, config keys).
- [ ] If behaviour or ops changed, one line in [RUNBOOKS](./RUNBOOKS.md) or [DEPLOY_SERVER](./DEPLOY_SERVER.md) when operators must act.

---

**Not in this short gate:** product roadmap items, ML quality benchmarks, monetization — track those separately in Issues / Projects.

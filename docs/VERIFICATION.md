# Quality verification (operators & maintainers)

Short log of automated checks. Full cycle: [CONTRIBUTING.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md), [TESTING.md](./TESTING.md).

## 2026-03-29 — critical UI fix

| Check | Result |
|-------|--------|
| Prev/next recording on `/videos/:id` | Fixed `ReferenceError` (undefined `listReturnState`); see [CHANGELOG.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) [Unreleased] |
| `make test-web` (Docker, `app/`) | 100 passed |
| `npm run build` (`app/ui`) | OK |

**Manual smoke on hub:** open a clip from Timeline → prev/next → back returns to list; direct URL (no `state`) → stepping still works; browser back follows history.

**Not run here:** weekly Playwright E2E, full `make docs` unless MkDocs changed.

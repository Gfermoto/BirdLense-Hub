# Pre-implementation: catalog, Unknowns, and Timeline

[Русский](./PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md)

This checklist is meant to **run before UI/API changes** to reduce regression risk and align the data model. It supports **[#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131)** (Migration as the path to species; remove **Catalog** from the nav) and **[#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139)** (review mode on the recordings page instead of a separate **Unknowns** nav item).

---

## 1. Product and API (agree before building the screen)

- **Review mode semantics**: document whether the UI shows detections from `GET /api/ui/unknowns` and/or visits from `GET /api/ui/timeline` (different entities). Capture this in #139 or a short ADR so the approach does not change mid-sprint.
- **API strategy**: decide whether `GET /api/ui/timeline` gains query parameters (e.g. low-confidence / review-only) or `unknowns` stays separate while Timeline only switches source/filter. Caching, the current `limit`, and the max one-day window for unknowns depend on this.
- **OpenAPI**: `app/web/openapi.yaml` documents `/timeline`; **`/api/ui/unknowns` is not in the spec** — add it before or with the frontend work; rely on CI (`openapi-contract`) as the contract gate.

---

## 2. Link and navigation inventory

- **Menu and routes**: `app/ui/src/components/Navigation.tsx`, `app/ui/src/App.tsx` — full list of entry points to **Catalog** (`/species`) and **Unknowns** (`/unknowns`).
- **Deep links in code**: e.g. Migration → `/species/:id`, directory tree, “back to species” actions.
- **Bookmarks and legacy URLs**: after release, expect redirect `/unknowns` → Timeline with query (see #139) — plan updates to user-facing docs (`docs/FEATURES*.md`, `docs/ARCHITECTURE*.md`, `docs/API*.md`, and `docs/UX_UNKNOWN_VIDEO_CORRECTION.md` if needed).
- **Tests**: `app/e2e/tests/smoke.spec.ts` hits `/unknowns` — define expected behavior after redirect.

---

## 3. Test baseline (regression)

- **Backend**: `app/web/tests/test_api.py` — extend edge-case coverage for unknowns if needed; add cases for new timeline query params when introduced.
- **E2E**: minimal `/timeline` flow (load, pick a day) and a “`/unknowns` redirect opens the correct mode” flow — diff before/after without relying only on manual QA.
- **React Query**: table of expected `invalidateQueries` after merging flows (today `unknowns`, `timeline`, `species` are tied together — see `DetectedSpecies` and the Unknowns page) to avoid stale lists.

---

## 4. i18n and page help

- Audit `nav.*`, `unknowns.*`, `timeline.*` keys: what merges, single label for the mode (“review” / low confidence).
- **Page help**: `unknownsHelpConfig` vs Timeline help — one flow or two scenarios in one component.

---

## 5. Accessibility and stable URLs

- Document query semantics (e.g. `?review=1`), `aria-pressed` for the mode control, live region on filter change — in one place (#139 or a short ADR) so implementation matches the plan.

---

## Suggested order

1. Align data/API in #139 (+ ADR if needed).
2. Extend OpenAPI and API tests as required.
3. Extend e2e/smoke baseline.
4. Ship doc and link updates in the same release as redirect and new UX (or a docs-only PR right after the feature merge).

After this checklist, implementation work on #131 and #139 can start.

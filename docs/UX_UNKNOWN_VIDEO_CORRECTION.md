# UX: Unknowns ↔ correction inside video (#81)

[Русский кратко](#russian-summary): цель и фазы — ниже на EN для единого источника.

**Issue:** [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81)

## Problem (operator view)

Manual species correction works well when one choice applies to **many** detections. But **Unknowns** and **per-video** correction feel like **two disconnected** flows: fixing a row on `/unknowns` vs opening the same detection via **View video** and correcting there.

## Current behavior (technical)

- Both paths call the same API: **`PATCH /api/ui/detections/:id`** with `species_id` (and related dataset/crop logic on the server).
- **Unknowns** lists low-confidence rows; **Video details → Detected species** groups by species/track and can merge or correct.
- After correction or merge from video, **`DetectedSpecies`** invalidates **`['unknowns']`** (and related queries) so the Unknowns page refetches — required because the app uses a **5-minute** React Query `staleTime` by default.

## UX principles (target)

1. **One mental model:** “I am correcting **this detection** (id `X`); the list and the video page are two entry points.”
2. **Visible linkage:** From Unknowns, **View video** already deep-links to context; optional: toast or hint “Same as Settings → video page”.
3. **No regression:** Bulk merge in video and multi-select flows stay as-is.

## Phased plan

| Phase | Scope |
|-------|--------|
| **A — Docs & microcopy** | Page help + i18n: clarify that Unknowns and video use the **same** correction API; encourage View video for visual check. |
| **B — Navigation** | From Unknowns after correct: optional “Stay on list” vs “Open video” — **implemented:** success snackbar includes **Open video** (default: stay on list; 10s auto-hide when action shown). |
| **C — Unified history** | **Implemented:** corrections write shared activity entries with `source` (`unknowns`/`video`) and Unknowns shows recent unified correction history. |

## Acceptance (from issue)

- [x] UX spec documented (this file + issue link).
- [x] Implementation or phased plan recorded in issue comments / PR.
- [x] No regression for bulk / multi-detection flows.

---

## Русский {#russian-summary}

**Цель:** одна понятная история для оператора: исправление вида в «Неизвестных» и на странице видео — это **одно и то же действие** над детекцией (общий API), разные точки входа.

**Фазы:** (A) тексты и справка, (B) опциональная навигация после исправления, (C) единая история правок между Unknowns/Video.

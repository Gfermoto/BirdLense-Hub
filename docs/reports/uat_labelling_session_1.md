# UAT Labelling Session 1 (prod)

Date: 2026-05-18  
Environment: `https://birdlense.eyera.info/labelling` (production)  
Operator mode: hotkeys-first ("Биолог")

## Stage 0 prerequisite (P0) verification

- Before fix: queue contained broken/empty-first cases; UI could land on non-annotatable entry.
- After fix deploys (`7818f572`, `e68bd965`): first visible case loads media stream and overlay.
- Verified on prod with browser snapshot:
  - media stream opened (`/api/ui/videos/1763/stream`);
  - bbox/label overlay rendered on frame (case #188 screenshot state);
  - no white screen; action panel responsive.

## UAT run (10 cases)

- Reviewed cases in single-pass flow: **10**
- Actions:
  - Confirm: **9**
  - Reject: **1**
- Hotkeys tested in prod:
  - `Enter` / `Space` (confirm) — OK
  - `Backspace` (reject) — OK
  - `1` (quick species shortcut) — handler active, no UI crash
- Throughput:
  - Target: 3-5 sec/case
  - Observed: **~3.2 sec/case average** (hotkey-driven run)

## UX checks

- Bounding boxes: visible on annotatable entries, overlay stays aligned with media.
- Russian localization: language switcher available; persisted UI language can remain EN per browser/session preference.
- Action duplication with other pages: no duplicate "ML-cycle" actions in this screen during run; flow remains labelling-centric.

## Non-blocking polish notes

- Language default depends on persisted client setting; add explicit "RU by default on first visit" fallback.
- If overlay confidence text is long, label can cover object on small screens; consider compact label mode.

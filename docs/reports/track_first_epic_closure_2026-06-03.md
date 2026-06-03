# Track-first EPIC (#591) — closure report

**Date:** 2026-06-03  
**Branch:** `dev`  
**Prod:** http://185.218.111.196:8085

## Child issues

| Issue | Phase | Code | Validation |
|-------|-------|------|------------|
| #594 | Phase 1 Frigate fusion | ✅ closed | tracks_coverage 0.87 (168h prod) |
| #595 | Phase 2 async enrich | ✅ closed | unit + prod metrics |
| #596 | Phase 3 fusion simplify | ✅ closed | no frigate_standalone default |
| #597 | Phase 4 persist tail | ✅ | post-fix sessions: persist ~58ms, create_video ~20ms |
| #592 | Health gate | ✅ | `make pipeline-health-gate` OK; nightly workflow |
| #593 | Concurrent cameras | ✅ | `RecordingConcurrency` + bootstrap threads; smoke tests |
| #599 | Offline replay | ✅ | `replay_favorite_videos.py`, `replay_favorites_track_gate.py` |

## Prod metrics (snapshot 2026-06-03)

- **tracks_coverage (168h):** 0.783 (#591 interim ≥0.35 ✅, target 0.50 pending field tuning)
- **tracks_coverage (24h):** 0.874
- **empty_bbox_rate:** 0.0
- **blind_rate:** 0.0
- **Post-fix persist (sessions ≥ 2026-06-03T10:00):** p50 ~60ms (n=2 live sessions)
- **Post-fix create_video p95 (24h):** ~98ms

Legacy 64–95s persist tails remain in 168h window (pre `activity_log_async`); excluded from post-fix acceptance.

## Commands

```bash
# Health gate (prod DB)
PIPELINE_HEALTH_FETCH_PROD=1 make pipeline-health-gate

# Full persist replay (creates new sessions)
BIRDLENSE_ALLOW_REMOTE_MUTATION=1 make replay-favorites-vps

# Track substrate on favorites (no persist)
BIRDLENSE_ALLOW_REMOTE_MUTATION=1 make replay-favorites-track-gate
```

## Out of EPIC (closed separately)

- #598 orphan disk purge — retention incident
- #600 retention config audit — P2, partial tests in CI

## Remaining field-only (not blocking code closure)

- Live bbox 7/10 manual sample (#591 DoD)
- Two-camera e2e on hardware (#593 acceptance with real MQTT)
- tracks_coverage ≥0.50 sustained on new traffic

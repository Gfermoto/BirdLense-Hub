# Live Hub-only species golden pack (RC6 residual)

JSON cases in `../species_golden_cases.json` validate **contract derivation**
(`RecognitionOutcome`). This directory is the home for **labeled Hub-only mp4**
clips that must pass with MQTT/Frigate off.

## Contract (when clips land)

| Field | Meaning |
|-------|---------|
| `clip` | relative path under this dir |
| `camera_id` | optional |
| `expected_kind` | `named_accept` \| `presence` \| `review` |
| `expected_species` | required for `named_accept` |
| `mqtt` | must be `off` / empty |

Gate: `make validate-species-live-hub-only`  
Strict empty fail: `REQUIRE_CLIPS=1 make validate-species-live-hub-only`  
Runtime regen (Orin):  
`SPECIES_LIVE_RUN=1 SPECIES_LIVE_DOCKER=birdlense make validate-species-live-hub-only`

## Harvest + curate (Orin)

```bash
# Candidates only:
python3 scripts/harvest_species_live_clips.py \
  --db app/data/db/birdlense.db --recordings-root app \
  --limit 6 --copy-full

# Keep only offline named_accept PASS:
python3 scripts/curate_species_live_pack.py \
  --db app/data/db/birdlense.db --recordings-root app \
  --limit 6 --docker birdlense --copy-full
```

`clips/*.mp4` are gitignored. Prefer `--copy-full` (short cuts → Unknown).

## Status

Runtime gate wired (2026-07-19). Empty `clips: []` in git skips unless
`REQUIRE_CLIPS=1`. Orin: full-clip harvest + classify-first regen —
**Common Wood Pigeon named_accept PASS** (`SPECIES_LIVE_DOCKER=birdlense`).
Prefer `--copy-full` for named; short ffmpeg cuts often yield Unknown.

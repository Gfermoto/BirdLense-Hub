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

## Harvest (Orin)

```bash
python3 scripts/harvest_species_live_clips.py \
  --db app/data/db/birdlense.db \
  --recordings-root app \
  --limit 4 --clip-seconds 6 \
  --docker-ffmpeg birdlense
```

`clips/*.mp4` are gitignored. Commit only `manifest.json` when you want a
tracked empty/partial index — or keep harvest local for Orin eval.

## Status

Runtime gate wired (2026-07-19). Empty `clips: []` in git skips unless
`REQUIRE_CLIPS=1`. Orin: full-clip harvest + classify-first regen —
**Common Wood Pigeon named_accept PASS** (`SPECIES_LIVE_DOCKER=birdlense`).
Prefer `--copy-full` for named; short ffmpeg cuts often yield Unknown.

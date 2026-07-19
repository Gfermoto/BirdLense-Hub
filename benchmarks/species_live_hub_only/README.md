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
Strict (fail if empty): `REQUIRE_CLIPS=1 make validate-species-live-hub-only`

## Status

Manifest scaffold (2026-07-19). `clips: []` — no labeled mp4 checked in yet.

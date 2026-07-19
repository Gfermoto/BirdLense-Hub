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

Gate entry (planned): `make validate-species-live-hub-only` — fails closed if
the pack is empty in CI strict mode; local Orin may skip until clips exist.

## Status

Scaffold only (2026-07-19). No labeled mp4 checked in yet.

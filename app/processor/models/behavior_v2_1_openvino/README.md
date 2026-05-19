# Behavior v2.1 OpenVINO (Canary)

Trained on VPS 2026-05-19: Hub relaxed extract + synthetic WetlandBirds supplement.

- `video_model_kind`: `video_v2_1`
- Manifest: `behavior_dataset_v2.1_merged.json` (64 tracklets, flying=8 prod+synthetic)
- Train report: holdout Macro-F1 1.0 (n=8; flying recall on holdout was 0 — experimental)

Config patch: `scripts/user-config-behavior-canary-v2_1.partial.yaml`

# Behavior v2 OpenVINO (prod-retrained)

Trained on Hub prod crops (`behavior_prod_v2` manifest), classes: `feeding`, `flying`.

- `behavior_video_model.xml` / `.bin` — IR FP16, input `[1, 192]`
- `behavior_video_export.json` — coef/intercept + labels

Regenerate: `docs/ml/BEHAVIOR_MODEL.md`.

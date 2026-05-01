# Fusion A/B Eval 2026-04-30

Источник: `scripts/prod/ab_fusion_eval.py`, окно `2026-04-29 00:00:00` → `2026-04-30 00:00:00`, `limit=6`.

## Профили

- **Profile A (baseline-like)**:
  - `detection.frigate_standalone_when_no_accepted_species=true`
  - `detection.frigate_standalone_min_score=0.48`
  - `detection.use_learned_fusion=true`
- **Profile B (YOLO-first tuned)**:
  - `detection.frigate_standalone_when_no_accepted_species=false`
  - `detection.frigate_standalone_min_score=0.52`
  - `detection.use_learned_fusion=false`

## Итоговые метрики A/B

- Profile A:
  - `total_rows=5`
  - `primary_provider`: `frigate=4 (0.8)`, `yolo=1 (0.2)`
  - `decision_kind`: `frigate_standalone=4`, `accepted_species=1`
- Profile B:
  - `total_rows=5`
  - `primary_provider`: `frigate=2 (0.4)`, `yolo=3 (0.6)`
  - `decision_kind`: `frigate_standalone=2`, `accepted_species=1`, `accepted_generic=2`

## Пер-видео изменения (ключевые)

- `video_id=686`: A → `frigate`, B → `yolo`
- `video_id=685`: A → `frigate`, B → `yolo`
- `video_id=687`: A/B обе `yolo`
- `video_id=688/689`: A/B обе `frigate` (raw tracks = 0)

Один ролик (`video_id=690`) пропущен по `track_regeneration_timeout`.

## Gate decision

`Profile B` проходит gate по ключевому KPI провайдера (`yolo` доля растет с `0.2` до `0.6`, +40 п.п. на оценочном срезе), при этом fallback от Frigate сохраняется для `raw_tracks=0`.

Решение: **фиксировать YOLO-first tuned профиль** и продолжать сбор live-метрик 24–48ч.

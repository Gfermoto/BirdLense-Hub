# Fusion Baseline 2026-04-30

Источник: production `birdlense.db`, окно `decision_trace` (последние 398 записей), срез снят `2026-04-30T12:02:05Z`.

## KPI snapshot

- `persisted_tracks_total`: `393`
- `rejected_tracks_total`: `81`
- `persisted primary_provider`:
  - `frigate`: `300` (`76.3%`)
  - `yolo`: `93` (`23.7%`)
- `rejected primary_provider`:
  - `yolo`: `81` (`100%`)
- `fallback_used_ratio`: `0.906`

## Decision kind distribution

- `frigate_standalone`: `258`
- `accepted_generic`: `59`
- `review_only_generic`: `45`
- `accepted_species`: `31`

## Top decision reasons

- `frigate_standalone`: `150`
- `absorbed_generic_into_frigate_species`: `102`
- `downgraded_to_generic_due_to_strong_conflict`: `44`
- `fallback_bird`: `36`
- `accepted_species`: `31`

## Top arbitration reasons

- `none`: `241`
- `absorbed_generic_into_frigate_species`: `102`
- `downgraded_to_generic_due_to_strong_conflict`: `44`

## Threshold paths

- `frigate_standalone_min_score`: `300`
- `classifier_threshold_then_detector_store_floor`: `55`
- `classifier_threshold`: `31`

## Provider mix in video_species (48h)

- `frigate`: `147`
- `arbitration`: `32`
- `yolo`: `2`

## Throughput

- `24h`: `videos=37`, `video_species=55`
- `48h`: `videos=108`, `video_species=154`

## Conclusion

Текущий прод перекошен в сторону `frigate_standalone`, а визуальная ветка `yolo` преимущественно отбрасывается или теряется на этапе fusion/arbitration. Это baseline для A/B после внедрения YOLO-first тюнинга.

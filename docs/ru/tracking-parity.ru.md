# Единая политика трекинга Live vs Regen (SOTA-11)

## Цель

Один и тот же ролик не должен давать разные `track_id`, длительности треков и отсечение коротких визитов в зависимости от того, обрабатывается он **в live-потоке** или **офлайн-перегенерацией** (`track_regen`).

## Источник правды

Модуль `app/processor/src/tracking_policy.py`:

- `build_unified_tracking_policy()` — пороги DecisionMaker, IoU fallback, geometry mode, regional scope, binary-only.
- `UnifiedTrackingPolicy.resolve_tracker_path()` — FPS-профили + адаптивный `track_buffer` (SOTA-10).
- `TrackingService` (`tracking_service.py`) — общий цикл decode → YOLO → ByteTrack для regen.

## Включение

В `default_config.yaml`:

```yaml
processor:
  track_regen_match_live_pipeline: true
```

При `true` regen использует:

- `processor.min_track_duration` (не `track_regen_min_track_duration`);
- live geometry (`inference_lores_*`, не `track_regen_lores_*`);
- `processor.regional_species` (не global-only);
- `iou_id_fallback_live_*` и путь `_track_maybe_retry` (как live);
- полный two_stage (не `track_regen_binary_only`).

## Legacy-режим

`track_regen_match_live_pipeline: false` — прежние отдельные ключи `track_regen_*` для экспериментов и быстрого binary-only overlay.

## Проверка

- Юнит-тесты: `app/processor/tests/test_tracking_policy_parity.py`
- Бенчмарк SOTA-09: метрика `tracking_unified_with_live` в отчёте regen
- Паритет на golden-клипах: `scripts/benchmark_sota.py` + `benchmarks/golden_baseline.json`

## Связанные документы

- [tracking-low-fps.ru.md](tracking-low-fps.ru.md) — адаптивный трекер при низком FPS
- [benchmark-golden-clips.ru.md](benchmark-golden-clips.ru.md) — регрессия 1816/1819

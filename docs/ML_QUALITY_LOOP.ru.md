# ML quality loop

Минимальный рабочий цикл для качества детекции/распознавания теперь такой:

1. Снять baseline по живому хабу:

```bash
cd /home/gfer/BirdLense
python scripts/report-detection-quality-baseline.py --days 14
```

Что смотреть:
- `trace_summary.low_light_clip_rate`
- `trace_summary.frigate_rescue_clip_rate`
- `trace_summary.yolo_silent_clip_rate`
- `correction_proxies.species_change_actions`
- `detection_slices.object_scale`

2. Подготовить dataset export с чистыми примерами:

- prefer `only_manually_corrected=true`
- prefer `ready_for_train=true`
- prefer `strict_quality=true`

3. Оценить готовность к review/calibration/retrain:

```bash
cd /home/gfer/BirdLense
python scripts/report-review-retrain-cycle.py \
  --days 14 \
  --dataset-info /path/to/dataset_info.json \
  --fusion-eval-report /path/to/fusion_eval_report.csv
```

Критерии перед retrain:
- есть `dataset_ready_for_train=true`
- `dataset_strict_quality_ok=true`
- есть свежий `fusion_eval_report`
- есть runtime snapshot процессора
- есть ручные corrections / review signal

4. После retrain сравнить:

- baseline до/после
- `generic Bird` rate
- `frigate_standalone` / `yolo_silent_clip_rate`
- runtime latency (`processor_runtime_stats.json`)

## Runtime observability

Процессор теперь пишет snapshot:

`data/diagnostics/processor_runtime_stats.json`

Там есть:
- `counters` — дропы MQTT, ошибки finalize/API, slow frames
- `gauges` — глубина MQTT queue, последний runtime profile, light metrics
- `latency_ms` — p50/p95/max для detect/API/session duration

В web diagnostics доступно:

- `GET /api/ui/system/diagnostics/processor-runtime`

## Night profile

Night / low-light profile настраивается в:

`app/app_config/default_config.yaml`

Блок:

- `processor.adaptive_profiles.enabled`
- `processor.adaptive_profiles.night.*`

Смысл: не выключать light gate целиком, а мягко ослаблять пороги для сложных сцен.

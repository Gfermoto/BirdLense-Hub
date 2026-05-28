# Калибровка классификатора (#507 / SOTA-16)

## Симптомы

- Уверенный YOLO + неверный Birder (мышь → синица, rodent → tit)
- Много правок в Unknowns / карточке видео

## Отчёт по правкам оператора

```bash
cd /home/gfer/BirdLense
python scripts/classifier_confusion_report.py --db app/data/db/birdlense.db
python scripts/classifier_confusion_report.py --db app/data/db/birdlense.db --json > /tmp/confusion.json
```

Источник: `activity_log` тип `species_correction` + `video_species.confidence`.

## Пороги (глобально, без per-camera)

| Ключ | Назначение | Старт (default_config) |
|------|------------|-------------------------|
| `processor.min_confidence_binary` | пол для всех меток детектора | 0.12 |
| `processor.min_confidence_binary_bird` | пол для label Bird перед классификатором | 0.12 |
| `processor.min_confidence_binary_rodent` | rodent/squirrel gate | 0.12 |
| `processor.bird_skip_classifier_max_area_frac` | не гонять Birder на огромный «Bird» bbox | 0 → выкл.; попробуйте **0.012–0.02** на широком угле |

Настройка в UI: **Станция → Настройки → Processor → Confidence**.

## Процедура после смены весов Birder/YOLO

1. Прогнать отчёт confusion на prod DB (read-only или копия)
2. Сравнить `recommended_processor_yaml` из JSON с текущим `user_config`
3. Поднять `min_confidence_binary_bird` на **+0.03…0.05**, если top pair rodent→bird
4. Включить `bird_skip_classifier_max_area_frac: 0.015` при «гигантской птице» на весь кадр
5. Smoke: 2–3 эталонных ролика + regen, метрика `yolo_frames_with_tracks`

## Val-set sweep (офлайн)

Полный temperature scaling — отдельный прогон на `datasets/` (не в hot path хаба). Скрипт отчёта даёт **операторский** срез; для val используйте export corrections + notebook/Ultralytics val по классам Birder.

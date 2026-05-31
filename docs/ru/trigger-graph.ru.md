# Граф триггеров и FP/FN по источникам (SOTA-07)

Модуль: `app/processor/src/trigger_graph.py`. Данные пишутся в `recording_session_summary` → `session_runtime_metrics.payload_json.trigger_graph`.

## Узлы: trigger vs support

### Trigger-слой (источники старта записи)

| Узел | Роль |
|------|------|
| **frigate** | MQTT Frigate (движение / standalone species) |
| **opencv** | Локальный motion (MOG2 / ROI) |
| **scale** | MQTT весов / motion по кормушке |

### Support/Fusion-слой (не trigger-источники)

| Узел | Роль |
|------|------|
| **yolo** | Бинарный детектор + треки (визуальная опора) |
| **birdnet** | MQTT BirdNET в окне записи (аудио-prior/поддержка) |

Важно: arbitration — результат fusion/decision шага, а не самостоятельный trigger/source.

## Рёбра (типы)

- `initiated_recording` — кто запустил сессию (`recording_context.triggered_by`).
- `extended_session` — Frigate-only продление без YOLO.
- `species_persisted` — вид сохранён после fusion (`decision_reason`).
- `candidate_rejected` — отклонённый кандидат (quality / floor).
- `mqtt_in_window` — события MQTT в окне записи.

## FP / FN (операторские определения)

| Метрика | Смысл | Типичный источник |
|---------|--------|-------------------|
| `fp_empty_recording` | Запись есть, кадров много, **post_fusion_persisted = 0** | Инициатор (opencv/frigate) |
| `fp_rejected_noise` | Отклонённые weak/phantom/static кандидаты | YOLO / quality |
| `fn_detector_silent` | Frigate-only при **yolo_raw = 0** или `yolo_blind_confirmed` | YOLO |
| `fn_no_persisted_species` | Много кадров YOLO без треков и без видов | YOLO |

Пороги кадров зашиты в коде (например `frames_seen >= 30` для пустой записи) — при необходимости вынести в `detection.trigger_graph_*` в конфиге.

## API и UI

- `GET /api/ui/analytics/trigger-graph?hours=24&camera_id=BirdBox`
- System → карточка **«Граф триггеров»**

## Проверка

```bash
cd app/processor && PYTHONPATH=src python3 -m pytest tests/test_trigger_graph.py -q
python3 scripts/chaos_load_generator.py --cameras 2 --sessions-per-camera 5
```

После chaos в UI появятся агрегаты (если chaos дописывает `trigger_graph` — перезапуск с новым процессором на реальных записях предпочтительнее).

## Связанные документы

- `docs/ru/yolo-blind-runbook.ru.md` — слепой YOLO (FN на узле yolo).
- `docs/ru/detection-geometry.ru.md` — геометрия боксов.

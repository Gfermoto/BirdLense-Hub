# ADR: контракт «подсказки классификатору» (внешние метаданные)

[English](../strategy/adr-classifier-hints-only.md) · [#634](https://github.com/Gfermoto/BirdLense-Hub/issues/634) · [#635](https://github.com/Gfermoto/BirdLense-Hub/issues/635)

**Статус:** принят  
**Дата:** 2026-06-10

---

## Суть

Frigate MQTT, BirdNET, eBird regional top и multicam metadata — **только подсказки** для классификатора и скоринга (bias порогов, priors в fusion, boost между камерами).

**Не должны:**

- блокировать старт записи на main stream;
- требовать detect-first anchor на lores (кроме явного legacy `recording_gate_mode: detect_first`);
- быть primary-драйвером persist в fusion (primary — YOLO + ByteTrack).

**По умолчанию (#635):** `processor.recording_gate_mode: motion_immediate` — триггер → FFmpeg на main, YOLO внутри сессии.

**Железо Wave 1:** Intel CPU + iGPU, OpenVINO `intel:gpu`. Без Coral/CUDA в контрактах процессора.

---

## Миграция — пути для понижения роли

| Путь | Модуль | Сейчас | Цель |
|------|--------|--------|------|
| `build_frigate_assisted_detect_first_anchor` | `detect_first.py` | Frigate bbox как lores anchor | Только при `detect_first` + assist enabled |
| `detect_first_frigate_assist_*` | config | Включает assist | Legacy opt-in |
| `requires_detect_first_before_record` | `detection_scheduler.py` | Gate до main FFmpeg | Выкл. при `motion_immediate` |
| `frigate_salvage_*` | `linear_pipeline.py`, finalize | Salvage без YOLO | Opt-in (`frigate_site`) |
| `_frigate_standalone_prepared_rows` | `detection_fusion.py` | Synthetic rows | Hint/review, не default persist |
| BirdNET / eBird / multicam boost | fusion, session | Priors и bias | **Оставить** как hints |
| `trigger_graph` `detect_first_ok` | `trigger_graph.py` | Гейт узлов | Диагностика, не gate записи |

**Не ломать:** dual-stream, geometry remap, `single_rtsp_read: false`, OpenVINO Intel GPU.

---

## Откат

```yaml
processor:
  recording_gate_mode: detect_first
  detect_first_enabled: true
```

---

## Проверка

- ADR EN + RU
- Тест BirdBox: trigger + lores hits=0 → запись стартует
- `make test-processor-light`

# Linear pipeline — fusion safeguards (#622)

[English](../contributor/linear-fusion-safeguards.md) · [Architecture](../contributor/architecture.md)

## Профили

| Профиль | По умолчанию | Frigate/BirdNET | Frigate salvage |
|---------|--------------|-----------------|-----------------|
| **Standalone-first** | `pipeline_mode: linear` | Подсказки в fusion, без synthetic persist | Выкл. |
| **Frigate-site** | Тот же linear | Frigate триггерит запись; hint вида | Opt-in: `tuning_role: frigate_site` |

YOLO + ByteTrack — **primary** persist в обоих профилях.

## `linear_skip_*` (`linear_pipeline.py`)

| Helper | Skip когда | В linear всё ещё работает |
|--------|------------|---------------------------|
| `linear_skip_legacy_fusion_safeguards` | linear/simple | detect-first restore, weak salvage, bbox contract, track_first |
| `linear_skip_frigate_salvage_paths` | linear без opt-in salvage | Salvage при global/role opt-in |

Подробная матрица — в [English](../contributor/linear-fusion-safeguards.md).

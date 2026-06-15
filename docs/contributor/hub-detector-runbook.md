# Hub detector runbook (короткий)

Чеклист против «круга» YOLO blind: Frigate видит, Hub молчит, агент правит пороги, на следующем деплое снова слепой.

## Перед правкой порогов

**Не чините только thresholds.** Сначала по порядку:

1. **Stream parity** — Hub `detect_stream` = тот же кадр, что Frigate detect. RTSP Dahua/Hik: **`subtype=0`**, не `subtype=1`.
2. **Lores / imgsz** — `processor.openvino_native_lores_imgsz: false` для Trapper @704²; `true` ломает square IR.
3. **Blind funnel** — в логах `recording_session_summary`: `yolo_frames_with_raw_boxes`, `yolo_frames_with_tracks`.
4. **Пороги** — только после 1–3; смотреть **merged** config (`default_config` + `user_config`), не только UI.

## Деплой и конфиги

| Артефакт | При `make deploy` |
|----------|-------------------|
| `app/app_config/default_config.yaml` | **синхронизируется** с репо |
| `app/app_config/user_config.yaml` | **не перезаписывается** (exclude + rsync filter `P`) |
| `app/data/`, `datasets/` | не трогаем |

Агентам: **не править prod `user_config` без бэкапа** `.bak.YYYYMMDD_<reason>`. Долгоживущие фиксы — в **`default_config.yaml`** репозитория + PR.

Пост-деплой (warn-only): `make verify-prod-detector-smoke` или `./scripts/verify-prod-detector-smoke.sh`.

## Метрики воронки (Frigate vs Hub)

После сессии в логах / UI funnel:

| Метрика | Frigate-only слепота | Где смотреть |
|---------|----------------------|--------------|
| `yolo_frames_with_raw_boxes` | 0 при живых Frigate-триггерах | `docker logs birdlense \| grep recording_session_summary` |
| `yolo_frames_with_tracks` | 0 при raw > 0 | то же |
| `post_fusion_persisted` / `db_persist_success` | 0 при tracks > 0 | fusion / persist слой |

Дополнительно: `yolo_blind_suspected` / `yolo_blind_confirmed`, `detection_acceptance_gap`.

## Канонические ключи (repo defaults)

| Ключ | Значение | Зачем |
|------|----------|-------|
| `processor.openvino_native_lores_imgsz` | `false` | 704×704 IR + native lores → пустой track |
| `processor.species_confidence_overrides.Bird` | `≤ 0.1` (default `0.08`) | высокий Bird gate режет слабые YOLO conf |
| `processor.min_confidence_binary` | `0.12` (default) | не поднимать в user без причины |
| `detection.frigate_standalone_when_no_yolo` | `false` | Frigate prior-only |
| `video.cameras[].detect_stream_name` | = Frigate detect | parity потоков |

CI/локально: `app/processor/tests/test_threshold_resolution.py` + `scripts/verify_merged_detector_config.py`.

## Связанные документы

- [yolo-blind-runbook.ru](../ru/yolo-blind-runbook.ru.md) — полная диагностика
- [morning-bird-checklist](../runbooks/morning-bird-checklist.md) — утренний 5‑мин чек
- [deploy.mdc](../../.cursor/rules/deploy.mdc) — VPS/LAN, политика агентов

# Migration Final Report — NABirds + OpenVINO (2026-05-20)

## Статус

| Критерий | Результат |
|----------|-----------|
| Parity Gate | **PASS** 7/7 (IoU ≥ 0.95, conf ≤ 5%) |
| Прод backend | `openvino` + `intel:gpu` |
| Персистентность IR | volume + rsync + `make sync-models` |
| Полный `make deploy` без ручного `docker cp` | **да** (после коммита весов в репо) |

**Вердикт:** переход необратим в коде и пайплайне; грызуны бинарником не детектируются.

---

## До / После

| | BRG + torch/OV BRG | NABirds + OpenVINO (финал) |
|--|-------------------|----------------------------|
| Веса | `best.pt`, `best_openvino_model` | `best_NABirds.pt`, `best_NABirds_openvino_model` |
| Рассвет 014828 | 0 YOLO boxes | детекция есть (PT/OV) |
| Latency (warm, 1 кадр) | torch CPU ~12 s | **OV GPU ~142 ms** |
| `yolo_raw_boxes_total` (до миграции) | 0 при BRG | мониторить после OV |

---

## Персистентность (P0)

1. **`app/docker-compose.yml`:** volume  
   `./processor/models/detection/weights` → `/app/processor/models/detection/weights`
2. **`scripts/sync_detector_weights.sh`** + **`make sync-models`** — проверка `best.xml` / `best.bin` / `best_NABirds.pt`
3. **`scripts/public/deploy.sh`:** шаг 1.1 после rsync; rsync `P` для `best_NABirds_openvino_model/`
4. **Git:** `best_NABirds_openvino_model/{best.xml,best.bin,metadata.yaml}` в репозитории (~21 MB)

После `force-recreate` IR остаётся на хосте в примонтированном каталоге.

---

## Code as Config

- `default_config.yaml`: `inference_backend: openvino`, `openvino_binary_enabled: true`, NABirds paths
- `app/.env.example`: `BIRDLENSE_INFERENCE_BACKEND=openvino`, `BIRDLENSE_OPENVINO_BINARY_ENABLED=1`, `intel:gpu`

`user_config.yaml` на сервере **не** перезаписывается деплоем — операторские override сохраняются.

---

## Операции

```bash
make sync-models          # локально перед коммитом/деплоем
make export-nabirds-openvino   # пересборка IR
make validate-nabirds-ov-parity
make deploy
```

Логи после деплоя:

```
detector_backend=openvino
ultralytics_device_label=intel:gpu
binary_path=.../best_NABirds_openvino_model
```

Smoke: `session_runtime_metrics.yolo_raw_boxes_total > 0` на сессии с птицами.

---

## Добавление классов в будущем

1. Обучить/получить новый `.pt` (Ultralytics detect).
2. `make export-nabirds-openvino` (или свой скрипт с тем же суффиксом `*_openvino_model`).
3. `make validate-nabirds-ov-parity` на golden manifest.
4. Обновить `processor.models.binary` / `binary_openvino`, `binary_predict_class_allowlist`, `detector_scope`.
5. `make sync-models` → commit → `make deploy`.

Без успешного parity **не** включать `openvino_binary_enabled: true`.

---

См. `docs/reports/nabirds_migration_20260520.md`, `docs/ml/MODEL_EXPORT_GUIDE.md`.

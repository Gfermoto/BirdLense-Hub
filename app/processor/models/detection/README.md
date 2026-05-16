# Detection weights (`detection/weights/`)

**Рабочий дефолт Hub:** модель **BRG** — три класса **Bird / Rodent / Background**. В Git закоммичены **`weights/best.pt`**, резерв **`weights/last.pt`** и каталог **`weights/best_openvino_model/`** (OpenVINO IR); пути в рантайме задаются в `processor.models.binary` / `processor.models.binary_openvino` (см. `default_config.yaml`). При сборке образа они попадают через `COPY app/processor`, на площадку — через `make deploy` / rsync.

**OV vs torch scores:** при `processor.inference_backend: openvino` в `default_config.yaml` заданы **`processor.openvino_binary_track_ultralytics_conf`** (нижняя страховка для `YOLO.track(conf=…)`) и **`processor.openvino_binary_bird_score_scale`** (множитель только для сравнения с порогом Bird; сырая `conf` в данных не умножается). Подстройте при росте ложных птиц или наоборот пропусках. На Intel iGPU задайте **`processor.inference_device: intel:gpu`** (или `BIRDLENSE_INFERENCE_DEVICE`) — см. `app/app_config/user_config.openvino-intel.example.yaml`.

**Перед заменой весов:** `make snapshot-detector-weights` (или `TAG=mytag make …`) кладёт копию в `weights/snapshots/<tag>/` (каталог в `.gitignore`). Сравнение PT↔IR на mp4: `scripts/compare_detector_bboxes.py` (в образе Hub: `/app/scripts/compare_detector_bboxes.py` после `make deploy`).

**Дополнительно в образе:** Ultralytics COCO **[`yolo11n.pt`](https://github.com/ultralytics/assets)** и экспорт **`yolo11n_openvino_model/`** (сборочный шаг в `Dockerfile`). Это не продуктовый дефолт конфига; при явном указании пути на `yolo11n.pt` можно использовать **`processor.binary_predict_class_allowlist: [14]`**, чтобы в пайплайн попадал только класс **bird** — грызуны так не покрываются.

`scripts/fetch-processor-weights.sh` может стянуть BRG zip из форка и положить `best.pt` (см. ниже).

## BRG 3-class (архив форка)

Пакеты и описание: **[AleksandrRogachev94/BirdLense](https://github.com/AleksandrRogachev94/BirdLense/tree/main/app/processor)** (`nabirds_yolo11n_binary.zip`). Для ручной подстановки: `processor.models.binary` → **`best.pt`**, `binary_openvino` → свой IR и при необходимости уберите или обнулите `binary_predict_class_allowlist`.

## EU classifier (отдельно)

**`classification/weights/best.pt`** — [HF `gfermoto/birdlense-birds-eu`](https://huggingface.co/gfermoto/birdlense-birds-eu) (pin в Dockerfile / fetch-скрипте).

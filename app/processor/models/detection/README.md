# Binary detector weights (`detection/weights/`)

По умолчанию образ Hub тянет **Ultralytics COCO [`yolo11n.pt`](https://github.com/ultralytics/assets)** и экспортирует **`yolo11n_openvino_model/`** (OpenVINO, `imgsz=640`).
В конфиге **`processor.binary_predict_class_allowlist: [14]`** — в пайплайн попадает только класс **14 (bird)**; грызуны через COCO не покрыты (нужна своя голова или BRG-детектор).

## BRG 3-class Bird / Rodent / Background (архив форка)

Пакеты и описание см. **[AleksandrRogachev94/BirdLense](https://github.com/AleksandrRogachev94/BirdLense/tree/main/app/processor)** (`nabirds_yolo11n_binary.zip`).
Для возврата к ним задайте `processor.models.binary` → распакованный **`best.pt`**, `binary_openvino` → свой IR и **уберите или обнулите `binary_predict_class_allowlist`**.
`scripts/fetch-processor-weights.sh` по-прежнему может стянуть zip и положить `best.pt`.

## EU classifier (отдельно)

**`classification/weights/best.pt`** — [HF `gfermoto/birdlense-birds-eu`](https://huggingface.co/gfermoto/birdlense-birds-eu) (pin в Dockerfile / fetch-скрипте).

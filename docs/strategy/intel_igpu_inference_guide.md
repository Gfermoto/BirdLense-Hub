# Intel iGPU + OpenVINO — BirdLense Hub

Операторский гайд для **Intel CPU + iGPU** (`renderD*`, VA-API, OpenVINO GPU plugin). Без Coral, без CUDA.

Связанные задачи: [#636](https://github.com/Gfermoto/BirdLense-Hub/issues/636) (native lores geometry), [#644](https://github.com/Gfermoto/BirdLense-Hub/issues/644) (perf audit).

---

## 1. Что делает Hub

| Стадия | Backend | Устройство | Примечание |
|--------|---------|------------|------------|
| Бинарный YOLO (Trapper) | Ultralytics → OpenVINO IR | `intel:gpu` | `track()` / `predict()`, batch=1 на live-кадр |
| Birder EU classifier | OpenVINO Runtime | `intel:gpu` | Отдельный compile; async worker снимает с hot path |
| Behavior logistic | OpenVINO | auto → GPU, CPU fallback | На finalize |
| FFmpeg decode/encode | VA-API (опц.) | iGPU | Отдельно от OV infer; `video.encoding: intel` |

Пути резолвятся в `inference/selector.py`, `inference_bootstrap.py`, `frame_geometry.resolve_binary_track_imgsz()`.

---

## 2. Железо и Docker (обязательно для iGPU)

На хосте: `/dev/dri/renderD*` и `card*`. Деплой генерирует `app/docker-compose.override.yml` через `scripts/docker-compose-intel-override-gen.sh`:

- Проброс DRI-устройств
- `group_add: video`, `render`
- `LIBVA_DRIVER_NAME=iHD`
- `cap_add: SYS_ADMIN`, `PERFMON`

Проверка на VPS:

```bash
ls -la /dev/dri/
cat app/docker-compose.override.yml
docker compose exec birdlense python3 -c "import openvino as ov; print(ov.Core().available_devices)"
```

Ожидаемые устройства: `CPU`, `GPU` (или `GPU.0`). Ultralytics принимает `device=intel:gpu`.

---

## 3. Продакшен `user_config.yaml` (рекомендация)

Минимальный фрагмент для VPS с Trapper 704×576 lores (см. `user_config.trapper-production.example.yaml`, `patch_prod_trapper_user_config.py`):

```yaml
processor:
  inference_backend: openvino
  inference_device: intel:gpu
  openvino_binary_enabled: true
  openvino_native_lores_imgsz: true          # #636 / 2ff464057 — [576,704], не квадрат 704²
  inference_lores_wh: [704, 576]
  binary_imgsz: 704
  models:
    binary: models/detection/weights/trapper_ai_v02_2024.pt
    binary_openvino: models/detection/weights/trapper_ai_v02_2024_openvino_model
    classifier_openvino: models/classification/weights/convnext_v2_tiny_eu-common256px_openvino_model
  classifier_inference_backend: openvino
  classifier_inference_device: intel:gpu
  classifier_async_enabled: true
  openvino:
    profile: latency      # live detect — минимальная задержка кадра
    num_requests: 0       # 0 = auto (фактически 1 infer request на live)
    model_cache_enabled: true
  openvino_min_confidence_binary_bird: 0.12
  openvino_binary_track_ultralytics_conf: 0.12
  track_spatial_split_enabled: true         # #636 — split треков при прыжке центра
  track_spatial_split_max_center_jump_norm: 0.18
  track_spatial_split_min_segment_frames: 2
```

Эквивалент через `app/.env` / `app/env/profiles/intel.env`:

```bash
BIRDLENSE_INFERENCE_BACKEND=openvino
BIRDLENSE_INFERENCE_DEVICE=intel:gpu
BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE=intel:gpu
BIRDLENSE_BINARY_OPENVINO_PATH=models/detection/weights/trapper_ai_v02_2024_openvino_model
# Опционально:
BIRDLENSE_OPENVINO_PROFILE=latency
BIRDLENSE_OPENVINO_NUM_REQUESTS=1
```

`.env` перекрывает пустые YAML-ключи; для продакшена задавайте **и YAML, и .env** согласованно.

---

## 4. Native lores imgsz (#636, commit `2ff464057`)

**Проблема:** OpenVINO IR Trapper экспортирован с `imgsz=704` (квадратный letterbox внутри YOLO). На detect substream 704×576 принудительный квадрат даёт смещение bbox.

**Фикс в коде:** `frame_geometry.resolve_binary_track_imgsz()` при `processor.openvino_native_lores_imgsz: true` и совпадении кадра с `inference_lores_wh` передаёт в `track(imgsz=…)` **`[H, W]` = [576, 704]**, не `704`.

| Ключ | Live (7 FPS detect) | Offline benchmark |
|------|---------------------|-------------------|
| `openvino_native_lores_imgsz` | `true` | `true` |
| `inference_lores_wh` | `[704, 576]` | то же |
| `binary_imgsz` | `704` (fallback / square export) | то же |

Тесты: `test_detect_first_birdbox_lores.py`, `test_yolo_geometry.py`.

---

## 5. Async, batch, streams, память

### Live pipeline (кормушка, ~7 FPS)

- **Batch:** неявно **1** — один кадр на `binary_model.track()`.
- **OpenVINO profile:** `latency` — правильный выбор для интерактивного detect+track.
- **num_requests:** `0` (auto) или `1` — не поднимать на live без бенчмарка; throughput+4 streams увеличивают VRAM iGPU и задержку кадра.
- **Classifier:** `classifier_async_enabled: true` — Birder на iGPU в фоне; детектор не ждёт species infer.
- **Finalize:** `finalize_async_enabled: true`, `finalize_queue_maxsize: 2` — W1 очередь (#644).

### Throughput (только offline / `scripts/ml_openvino_async_profile.py`)

```bash
python3 scripts/ml_openvino_async_profile.py \
  --videos-root app/data/recordings \
  --profile throughput_intel_gpu
```

Профиль `throughput` + `num_requests: 4` имеет смысл для пакетного прогона MP4, **не** для live RTSP.

### Память iGPU

- Два compiled model (binary OV + Birder OV) на GPU — следить за OOM при одновременной нагрузке.
- `processor.openvino.model_cache_enabled: true` — кэш IR на диске, быстрее рестарт.
- При нехватке памяти: classifier на `intel:cpu`, binary на `intel:gpu` (разнести устройства).

### Gap (аудит #644)

Ключи `processor.openvino.profile` / `num_requests` резолвятся в `processor_runtime_profile.resolve_openvino_tuning()` и `inference/selector.py`, но **не пробрасываются** в Ultralytics `YOLO.track()` напрямую — эффект сейчас через env `BIRDLENSE_OPENVINO_*` и внешние скрипты. Для live достаточно `device=intel:gpu` + native lores.

---

## 6. OpenVINO-пороги (OV ≠ torch scores)

| Ключ | Назначение |
|------|------------|
| `openvino_min_confidence_binary_bird` | Замена `min_confidence_binary_bird` только при `inference_backend=openvino` |
| `openvino_binary_track_ultralytics_conf` | Потолок `conf` в `track()` без второго инференса |
| `openvino_binary_bird_score_scale` | Масштаб Bird conf перед сравнением с порогом |

На проде (2026-06): `0.12` / `0.12` — согласовано с `auto_unstick` и detect-first.

---

## 7. Верификация продакшена

### Конфиг (SSH)

```bash
grep -E 'inference_backend|inference_device|binary_openvino|openvino_native|inference_lores_wh' \
  app/app_config/user_config.yaml
ls processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/
```

### Логи после `make start`

```bash
docker compose logs birdlense 2>&1 | grep -iE \
  'Inference startup|ultralytics_device|openvino|intel:gpu|inference_backend_effective'
```

Ожидаемо:

```
Inference startup: detector_backend=openvino … ultralytics_device_label=intel:gpu …
```

Метрики: `inference_backend_effective=openvino` в `processor_runtime_stats.json` / heartbeat.

### Smoke в контейнере

```bash
docker compose exec birdlense python3 -c "
from ultralytics import YOLO
m = YOLO('processor/models/detection/weights/trapper_ai_v02_2024_openvino_model', task='detect')
r = m.predict('https://ultralytics.com/images/bus.jpg', device='intel:gpu', imgsz=[576,704], verbose=False)
print('boxes', len(r[0].boxes))
"
```

---

## 8. Аудит VPS 185.218.111.196 (2026-06-10)

| Проверка | Статус |
|----------|--------|
| `/dev/dri/renderD128` | OK |
| `docker-compose.override.yml` (iHD, group_add) | OK |
| `user_config`: `inference_backend=openvino`, `inference_device=intel:gpu` | OK |
| `binary_openvino` → `trapper_ai_v02_2024_openvino_model` | OK (xml+bin на диске) |
| `inference_lores_wh: [704, 576]` | OK |
| `openvino.profile: latency`, `num_requests: 0` | OK |
| `openvino_native_lores_imgsz` в user_config | наследуется из `default_config` после деплоя |
| Контейнер `birdlense` running | **DOWN** на момент аудита — логи `intel:gpu` не сняты |
| `video.record_with_vaapi` | `false` на проде — decode/encode на CPU; OV infer на GPU отдельно |

---

## 9. Top 5 actionable (только Intel)

1. **`intel:gpu` + native lores** — `openvino_native_lores_imgsz: true`, `inference_lores_wh: [704,576]`; не форсировать square 704² на OV track (#636).
2. **Latency, batch=1** — `openvino.profile: latency`, `num_requests: 0|1` на live; throughput+streams только для offline `ml_openvino_async_profile.py`.
3. **Docker DRI override** — убедиться что деплой перегенерирует override; без `renderD*` OV падает на CPU молча через `resolve_openvino_device_policy(auto)`.
4. **Async classifier на iGPU** — `classifier_inference_backend: openvino`, `classifier_async_enabled: true`; binary и Birder параллельно без блокировки detect loop.
5. **OV-пороги вместо torch defaults** — `openvino_min_confidence_binary_bird` + `openvino_binary_track_ultralytics_conf` (0.12 на VPS); иначе «слепой» YOLO при заниженном `track(conf)`.

### Следующие шаги (не блокеры)

- Поднять контейнер и подтвердить `ultralytics_device_label=intel:gpu` в логах.
- После деплоя `2ff464057+`: явно прописать `track_spatial_split_*` в prod `user_config` (сейчас из default).
- Рассмотреть `video.capture_backend: ffmpeg_vaapi` при `encoding: intel` для разгрузки CPU decode (отдельно от OV).
- Wire `resolve_openvino_tuning()` → Ultralytics OV compile hints (сейчас dead config для binary).

---

## 10. Ссылки

- `app/app_config/user_config.openvino-intel.example.yaml`
- `app/env/profiles/intel.env`
- `docs/ml/MODEL_EXPORT_GUIDE.md` — экспорт IR
- `scripts/ml_openvino_async_profile.py` — offline throughput sweep
- [Ultralytics OpenVINO](https://docs.ultralytics.com/integrations/openvino/) — `device=intel:gpu`

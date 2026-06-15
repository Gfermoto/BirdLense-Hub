# Stream Probe (SOTA-02 / #493)

BirdLense определяет **реальное** разрешение и FPS detect-потока (Go2RTC/RTSP или файл) и использует их в пайплайне вместо захардкоженных значений в коде.

## Как работает

1. **При старте процессора** (`processor_bootstrap`): для CLI-файла или `video.file_path` вызывается `probe_processor_startup()`; `main_size` — probe, иначе fallback из `video.video_width` × `video.video_height`.
2. **При подключении Go2RTC** (`Go2RTCStreamSource._connect`): `probe_stream_url()` на detect/capture RTSP; **per camera** probe record URL при создании источника и в `refresh_record_stream_geometry`.
3. **Файловые источники** (`VideoFileSource`, плейлист): `probe_video_file()` при открытии ролика.
4. **Track regen**: probe mp4 перед YOLO.

Приоритет **FPS**: `StreamCapabilities` → атрибуты источника → `video.detect_fps` (>0) → `processor.detection_quality_assumed_fps` из YAML.

Приоритет **letterbox (detect WxH)**: `detect_use_native_resolution` → `inference_lores_wh` → `inference_lores_px` → probe кадра / stream capabilities (не global record resolution).

`processor.binary_imgsz` — размер **экспорта модели** YOLO/OpenVINO, не размер потока.

## WxH vs H×W (контракт геометрии)

| Поле / API | Порядок | Пример Full HD | Модуль |
|------------|---------|----------------|--------|
| `video_width` × `video_height`, `main_size`, `inference_lores_wh` | **ширина×высота (W×H)** | `1920`, `1080` | config, ffprobe |
| `*_shape_hw` в detection metadata, `frame.shape` | **высота×ширина (H×W)** | `[1080, 1920]` | OpenCV, persist |
| Нормализованный bbox `xyxy` | доли от **W** и **H** кадра хранения | playback = main MP4 | `detection_strategy` |

Парсеры: `app/shared/frame_shape.py`. ADR: [adr-frame-geometry-contract.md](../strategy/adr-frame-geometry-contract.md).

## Бэкенды probe

| Режим | Переменная | Поведение |
|-------|------------|-----------|
| auto (по умолчанию) | `BIRDLENSE_STREAM_PROBE=auto` | ffprobe, при неудаче — OpenCV + измерение FPS по кадрам |
| ffprobe | `BIRDLENSE_STREAM_PROBE=ffprobe` | только ffprobe, затем OpenCV |
| opencv | `BIRDLENSE_STREAM_PROBE=opencv` | только OpenCV |

Требуется `ffprobe` в PATH (образ Docker обычно уже содержит ffmpeg).

## Метрики

Gauges (processor runtime stats):

- `stream_probe_width`, `stream_probe_height`, `stream_probe_fps`
- `stream_probe_source` — `ffprobe`, `opencv`, `measured`
- `geometry_metadata_invalid_total` — metadata `playback_shape_hw` не совпал с `main_size`/MP4 ffprobe

## Конфиг

- `video.detect_fps: 0` — авто (из probe).
- `video.video_width` / `video_height`: **0 или не задано** — авто из probe record/main RTSP (per camera). Fallback, если probe недоступен.
- `video.force_recording_resolution: true` — legacy: явные width/height **перекрывают** probe (офлайн file-replay).
- Detect letterbox — см. `processor.inference_lores_wh` (не привязан к record resolution).

См. также: [config-schema.ru.md](config-schema.ru.md), `app/processor/src/stream_probe.py`.

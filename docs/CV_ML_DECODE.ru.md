# Декод видео и resize — замеры (#373)

[English](./CV_ML_DECODE.md)

**Прод:** в поставляемом `default_config.yaml` у `video` по умолчанию **`encoding: cpu`**. Intel VA-API (кодек/декод) включится только при **`video.encoding: intel`**, пробросе `/dev/dri` в контейнер и поддержке стеком — до тех пор на большинстве хабов RTSP идёт через **CPU**, если явно не включать GPU.

Фаза 1 [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) — **только замеры**, без обязательного hwaccel в продукте, пока нет выигрыша на вашей матрице.

**Проверка окружения:** `python3 scripts/check_video_decode_environment.py` — перечисляет устройства `/dev/dri` и при наличии запускает `vainfo`.

## Захват для детектора vs запись FFmpeg (GPU)

- **`video.encoding: intel`** относится к **записи** (`start_recording`): отдельный FFmpeg тянет RTSP с VA-API и кодирует в файл через `h264_vaapi`, если устройство и драйверы работают.
- **Живой инференс** (`capture()` → кадры для motion/детектора) — **второе** подключение к потоку. По умолчанию `video.capture_backend: auto`: при `video.encoding: cpu` остаётся OpenCV/CPU, при `video.encoding: intel` и успешном VA-API preflight пробуется FFmpeg VA-API rawvideo capture. Если VA-API недоступен — fallback на OpenCV.

## Скрипт

```bash
pip install opencv-python
python3 scripts/benchmark_video_decode_resize.py --video путь/к/клипу.mp4 --frames 300 --width 640 --height 640
python3 scripts/benchmark_video_decode_resize.py --video путь/к/клипу.mp4 --backend ffmpeg_vaapi --frames 300
```

JSON в stdout: ``video_decode_resize_benchmark@v1`` (`backend`, `fps`, `ms_per_frame`, `resize`).

Таблицу результатов заполняйте вручную в [CV_ML_DECODE.md](./CV_ML_DECODE.md) (англ.) или здесь — и фиксируйте платформу (bare Intel / Docker / WSL2).

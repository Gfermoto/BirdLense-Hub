# Video decode & resize — baseline (#373)

[Русский](./CV_ML_DECODE.ru.md)

**Production note:** In shipped `default_config.yaml`, `video.encoding` defaults to **`cpu`**. Intel VA-API encoding/decoding is used only when you set **`video.encoding: intel`**, pass `/dev/dri` into the container, and the stack supports it — so most hubs decode/encode RTSP on **CPU** unless you explicitly enable GPU helpers. This is independent of the benchmark script below.

Phase 1 of [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) is **measurement only** (no mandatory hwaccel in the product path until a win is shown).

**Preflight:** `python3 scripts/check_video_decode_environment.py` — lists `/dev/dri` nodes and runs `vainfo` when available.

## Inference capture vs FFmpeg recording (GPU)

- **`video.encoding: intel`** applies to the **recording** path (`start_recording`): a separate FFmpeg process pulls RTSP with `-hwaccel vaapi` and encodes with `h264_vaapi` when `/dev/dri` and drivers work.
- **Live inference** (`capture()` → frames for motion/detection) is a **second** RTSP client. It defaults to `video.capture_backend: auto`: CPU/OpenCV when `video.encoding: cpu`, and FFmpeg VA-API rawvideo capture when `video.encoding: intel` and the VA-API preflight passes. If VA-API is unavailable, it falls back to OpenCV.

## Script

```bash
pip install opencv-python  # or use the same env as the processor
python3 scripts/benchmark_video_decode_resize.py --video path/to/clip.mp4 --frames 300 --width 640 --height 640
python3 scripts/benchmark_video_decode_resize.py --video path/to/clip.mp4 --backend ffmpeg_vaapi --frames 300
```

Output JSON uses `schema: video_decode_resize_benchmark@v1` and now includes
`cpu_process_pct`, `host`, `platform`, and absolute `video` path in addition to
`backend`, `fps`, `ms_per_frame`, `frames`, `elapsed_sec`, `resize`.

## Result table (fill locally)

| Date | Host | Platform | Backend | Frames | FPS | ms/frame | CPU% (process) | `/dev/dri` | Notes |
|------|------|----------|---------|--------|-----|----------|----------------|------------|-------|
| _fill from script JSON_ |  |  | opencv |  |  |  |  | n/a | baseline |
| _fill from script JSON_ |  |  | ffmpeg_vaapi |  |  |  |  | yes/no | VA-API path |

## Support matrix (WSL2/headless)

| Environment | `opencv` backend | `ffmpeg_vaapi` backend | Notes |
|-------------|------------------|------------------------|-------|
| Bare-metal Linux + Intel iGPU + `/dev/dri/renderD*` | Supported | Supported | Preferred validation target for VA-API |
| Headless Linux server without `/dev/dri` | Supported | Unsupported | CPU decode only |
| WSL2 (typical setup) | Supported | Usually unsupported | Treat VA-API as experimental unless preflight confirms |

Always record the actual decode path used (`opencv` fallback vs `ffmpeg_vaapi`)
for each row in the table above.

Phase 2 (optional GStreamer/ffmpeg hwaccel) starts only if Phase 1 shows a clear win on your matrix (see issue text).

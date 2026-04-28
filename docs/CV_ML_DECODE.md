# Video decode & resize — baseline (#373)

[Русский](./CV_ML_DECODE.ru.md)

Phase 1 of [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) is **measurement only** (no mandatory hwaccel in the product path until a win is shown).

## Script

```bash
pip install opencv-python  # or use the same env as the processor
python3 scripts/benchmark_video_decode_resize.py --video path/to/clip.mp4 --frames 300 --width 640 --height 640
```

Output JSON uses `schema: video_decode_resize_benchmark@v1` (`fps`, `ms_per_frame`, `resize`).

## Result table (fill locally)

| Date | Host | OS | Docker | `/dev/dri` | OpenCV build | Clip | Resolution | FPS | ms/frame | Notes |
|------|------|----|--------|------------|--------------|------|------------|-----|----------|-------|
| | bare Intel | | | | | 1080p sample | | | | |

**Unsupported / caution:** WSL2 video backends differ from bare Linux; headless servers may lack VA-API render nodes — document “decode path used” (CPU vs attempted hwaccel).

Phase 2 (optional GStreamer/ffmpeg hwaccel) starts only if Phase 1 shows a clear win on your matrix (see issue text).

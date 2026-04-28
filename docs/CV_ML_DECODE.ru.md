# Декод видео и resize — замеры (#373)

[English](./CV_ML_DECODE.md)

Фаза 1 [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) — **только замеры**, без обязательного hwaccel в продукте, пока нет выигрыша на вашей матрице.

## Скрипт

```bash
pip install opencv-python
python3 scripts/benchmark_video_decode_resize.py --video путь/к/клипу.mp4 --frames 300 --width 640 --height 640
```

JSON в stdout: ``video_decode_resize_benchmark@v1``.

Таблицу результатов заполняйте вручную в [CV_ML_DECODE.md](./CV_ML_DECODE.md) (англ.) или здесь — и фиксируйте платформу (bare Intel / Docker / WSL2).

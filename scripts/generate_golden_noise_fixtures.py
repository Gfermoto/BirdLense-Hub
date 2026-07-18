#!/usr/bin/env python3
"""Generate small synthetic noise_fp golden MP4 fixtures (OpenCV, no ffmpeg)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "benchmarks" / "fixtures"

SPECS: list[tuple[str, tuple[int, int, int], int, int, bool]] = [
    ("empty_day", (42, 42, 42), 704, 576, False),
    ("empty_night", (8, 8, 8), 704, 576, False),
    ("feeder_static_noise", (30, 35, 28), 704, 576, True),
    ("forest_far_empty", (50, 55, 45), 960, 540, False),
    ("birdbox_close_empty", (40, 40, 40), 704, 576, False),
    ("low_light_empty", (5, 5, 5), 704, 576, False),
    ("dual_cam_empty_a", (35, 35, 35), 704, 576, False),
    ("dual_cam_empty_b", (38, 40, 36), 960, 540, False),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, color, w, h, noisy in SPECS:
        path = OUT / f"clip_{name}.mp4"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 7.0, (w, h))
        if not writer.isOpened():
            print(f"FAIL open writer {path}")
            return 1
        rng = np.random.default_rng(abs(hash(name)) % (2**32))
        for _ in range(21):
            frame = np.full((h, w, 3), color, dtype=np.uint8)
            if noisy:
                frame = np.clip(
                    frame.astype(np.int16) + rng.integers(-3, 4, size=frame.shape),
                    0,
                    255,
                ).astype(np.uint8)
            writer.write(frame)
        writer.release()
        print(f"OK {path.name} ({path.stat().st_size} bytes)")
    # Legacy alias for 1816 noise clip.
    alias = OUT / "clip_1816.mp4"
    src = OUT / "clip_empty_day.mp4"
    alias.write_bytes(src.read_bytes())
    print(f"OK {alias.name} (alias empty_day)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

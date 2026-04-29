#!/usr/bin/env python3
"""Одноразовый добор background/val (если train уже заполнен)."""
from pathlib import Path

from bootstrap_detector_yolo import _collect_no_bird_background, _ensure_layout

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    _ensure_layout(root)
    # Меньше, чем дефолт 600/450: иначе FiftyOne долго качает весь prefetch вала COCO
    # до первой записи в binary/background/val.
    # pool крупный: в val COCO много кадров с bird; при малом бюджете набирается < target.
    _collect_no_bird_background(
        root,
        coco_split="validation",
        pool=20000,
        target=22,
        out_tag="val",
        scan_chunk=60,
    )
    print("OK: background/val")

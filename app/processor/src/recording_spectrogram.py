"""Spectrogram helpers for finalized recordings."""

from __future__ import annotations

import logging
import os
from typing import Any

from spectrogram import generate_spectrogram


def maybe_generate_recording_spectrogram(
    config: Any,
    *,
    mqtt_events: list[dict],
    video_output: str,
    output_path_physical: str,
    output_path_logical: str,
    generate_func=None,
) -> str | None:
    has_birdnet_event = any(event.get("source") == "birdnet" for event in mqtt_events)
    spectrogram_always = bool(config.get("processor.generate_spectrogram_always"))
    if not (spectrogram_always or has_birdnet_event):
        return None

    px_per_sec = config.get("processor.spectrogram_px_per_sec") or 200
    spectrogram_filename = f"spectrogram_{px_per_sec}.jpg"
    spectrogram_output = os.path.join(output_path_physical, spectrogram_filename)
    generate = generate_spectrogram if generate_func is None else generate_func
    if generate(video_output, spectrogram_output, px_per_sec):
        return f"{output_path_logical}/{spectrogram_filename}"
    logging.warning("Spectrogram generation failed (BirdNET event present)")
    return None

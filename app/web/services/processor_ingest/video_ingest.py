"""Подготовка JSON для приёма видео от процессора (без записи в БД)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from recording_layout_paths import stat_recording_layout_file

from services.processor_ingest.gateway import log_ingest_activity, processor_detection_payload


@dataclass(frozen=True)
class PreparedProcessorVideo:
    """Нормализованные поля для создания ``Video`` и ``process_detections``.

    ``processor_version`` остаётся в исходном ``data`` (как в маршруте до #344).
    """

    start_time: datetime
    end_time: datetime
    video_path: str
    spectrogram_path: str | None
    species_list: list[dict]


def prepare_processor_video(
    data: dict,
    *,
    min_confidence: float,
) -> tuple[Literal[True], PreparedProcessorVideo] | tuple[Literal[False], dict, int]:
    """Проверить тело ``/api/processor/videos`` и пути файлов.

    При ошибке доступа к файлу (не invalid format) пишет ``ingest_gate`` в activity log.
    """
    if not data:
        return False, {"error": "JSON body required"}, 400
    try:
        start_time = datetime.fromisoformat(data.get("start_time"))
        end_time = datetime.fromisoformat(data.get("end_time"))
    except (ValueError, TypeError):
        return False, {"error": "Invalid datetime format"}, 400

    species_list = data.get("species", []) or []
    if not species_list:
        return False, {"error": "Missing species"}, 400
    species_list = [processor_detection_payload(s) for s in species_list if isinstance(s, dict)]
    species_list = [s for s in species_list if s.get("species_name") or s.get("species")]
    if not species_list:
        return False, {"error": "Missing species"}, 400
    species_list = [s for s in species_list if float(s.get("confidence") or 0) >= min_confidence]
    if not species_list:
        return False, {"error": "All species below min_confidence_to_store threshold"}, 400

    video_path = (data.get("video_path") or "").strip()
    ok_file, resolved_full, reason = stat_recording_layout_file(video_path, kind="video")
    if not ok_file:
        if reason == "video_path_invalid":
            return False, {"error": "Invalid video_path format"}, 400
        log_ingest_activity(
            "ingest_gate",
            {
                "reason": reason or "video_file_missing",
                "video_path": video_path,
                "resolved_path": resolved_full,
            },
        )
        return (
            False,
            {
                "error": "Video file is missing or unreadable on hub storage",
                "reason": reason or "video_file_missing",
                "video_path": video_path,
            },
            400,
        )

    spec_path = (data.get("spectrogram_path") or "").strip()
    spectrogram_path = data.get("spectrogram_path")
    if spec_path:
        ok_spec, _, _ = stat_recording_layout_file(spec_path, kind="spectrogram")
        if not ok_spec:
            spectrogram_path = ""

    prepared = PreparedProcessorVideo(
        start_time=start_time,
        end_time=end_time,
        video_path=video_path,
        spectrogram_path=spectrogram_path,
        species_list=species_list,
    )
    return True, prepared

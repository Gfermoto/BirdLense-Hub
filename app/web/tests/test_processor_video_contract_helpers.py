"""Unit tests for processor ingest bbox/track contract pruning."""

from routes.processor_routes import _enforce_video_bbox_track_contract


def test_enforce_video_bbox_track_contract_drops_invalid_yolo_rows():
    rows, stats = _enforce_video_bbox_track_contract(
        [
            {
                "species_name": "Invalid",
                "source": "video",
                "detection_provider": "yolo",
                "frames": [],
            }
        ]
    )
    assert rows == []
    assert int(stats["dropped_missing_frames"]) == 1


def test_enforce_video_bbox_track_contract_prunes_bad_frames_and_keeps_row():
    rows, stats = _enforce_video_bbox_track_contract(
        [
            {
                "species_name": "Mixed",
                "source": "video",
                "detection_provider": "yolo",
                "frames": [
                    {"t": 0.1, "bbox": [0.2, 0.2, 0.2, 0.4]},
                    {"t": 0.2, "bbox": [0.1, 0.1, 0.3, 0.3]},
                ],
            }
        ]
    )
    assert len(rows) == 1
    assert len(rows[0]["frames"]) == 1
    assert int(stats["pruned_invalid_bbox_frames"]) == 1

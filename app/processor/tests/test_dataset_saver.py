import json
import os
import sys

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

import dataset_saver as ds  # noqa: E402


def test_save_dataset_crops_falls_back_to_video_frames(monkeypatch, tmp_path):
    writes = []

    class _FakeCv2:
        @staticmethod
        def imwrite(path, image):
            writes.append((path, image.shape))
            return True

    monkeypatch.setattr(ds, "cv2", _FakeCv2(), raising=False)
    monkeypatch.setattr(
        ds,
        "_extract_local_detection_crop",
        lambda *args, **kwargs: np.zeros((8, 9, 3), dtype=np.uint8),
        raising=False,
    )

    saved = ds.save_dataset_crops(
        [
            {
                "species_name": "Bird",
                "confidence": 0.9,
                "track_id": -1,
                "start_time": 0.0,
                "end_time": 20.0,
                "frames": [{"t": 10.0, "bbox": [0.1, 0.2, 0.4, 0.5]}],
            }
        ],
        video_id=17,
        data_dir=str(tmp_path),
        min_confidence=0.5,
        video_output_path="/tmp/clip.mp4",
    )

    assert saved == 1
    assert len(writes) == 1
    assert writes[0][0].endswith("17_-1_0.jpg")
    assert writes[0][1] == (8, 9, 3)


def test_build_detection_crop_request_prefers_best_frame():
    from shared.detection_crop_contract import build_detection_crop_request

    img = np.zeros((4, 4, 3), dtype=np.uint8)

    req = build_detection_crop_request(
        best_frame=img,
        frames=json.dumps([{"t": 5.0, "bbox": [0.1, 0.2, 0.4, 0.5]}]),
        start_time=0.0,
        end_time=10.0,
    )

    assert req["source_kind"] == "best_frame"
    assert req["best_frame"] is img
    assert req["bbox"] == [0.1, 0.2, 0.4, 0.5]


def test_build_detection_crop_request_uses_midpoint_bbox_when_no_best_frame():
    from shared.detection_crop_contract import build_detection_crop_request

    req = build_detection_crop_request(
        best_frame=None,
        frames=json.dumps(
            [
                {"t": 1.0, "bbox": [0.0, 0.0, 0.1, 0.1]},
                {"t": 5.0, "bbox": [0.2, 0.2, 0.5, 0.6]},
            ]
        ),
        start_time=0.0,
        end_time=10.0,
    )

    assert req["source_kind"] == "video_frames_bbox"
    assert req["offset_sec"] == 5.0
    assert req["bbox"] == [0.2, 0.2, 0.5, 0.6]

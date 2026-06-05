"""video.cameras: required detect_stream_name for Go2RTC live."""

from app_config.app_config import validate_merged_config_semantics
from app_config.cameras import cameras_for_processor, get_valid_cameras, validate_go2rtc_detect_streams


def test_get_valid_cameras_without_detect_stream_still_lists_camera():
    """Missing detect_stream_name is caught by validate_go2rtc_detect_streams, not get_valid_cameras."""
    rows = get_valid_cameras(
        [{"id": "a", "stream_name": "main_a", "name": "A"}],
    )
    assert len(rows) == 1
    assert "detect_stream_name" not in rows[0]
    issues = validate_go2rtc_detect_streams(rows, video_source="go2rtc")
    assert any("detect_stream_name required" in i for i in issues)


def test_get_valid_cameras_strips_detect_stream_name():
    """Whitespace around detect_stream_name is stripped."""
    rows = get_valid_cameras(
        [
            {
                "id": "b",
                "stream_name": "main_b",
                "detect_stream_name": "  det_b  ",
                "name": "B",
            },
        ],
    )
    assert len(rows) == 1
    assert rows[0]["detect_stream_name"] == "det_b"
    assert validate_go2rtc_detect_streams(rows, video_source="go2rtc") == []


def test_validate_rejects_detect_same_as_main():
    rows = get_valid_cameras(
        [{"id": "x", "stream_name": "Forest", "detect_stream_name": "Forest", "name": "X"}],
    )
    issues = validate_go2rtc_detect_streams(rows, video_source="go2rtc")
    assert any("must differ" in i for i in issues)


def test_validate_skipped_for_file_source():
    rows = get_valid_cameras([{"id": "a", "stream_name": "main_a"}])
    assert validate_go2rtc_detect_streams(rows, video_source="file") == []


def test_semantics_validation_requires_detect_on_go2rtc():
    merged = {
        "video": {
            "source": "go2rtc",
            "cameras": [{"id": "Forest", "stream_name": "Forest", "name": "Forest"}],
        },
    }
    issues = validate_merged_config_semantics(merged)
    assert any("detect_stream_name required" in i for i in issues)


def test_cameras_for_processor_includes_detect_when_set():
    """Processor dict carries detect_stream_name for media_runtime."""
    valid = get_valid_cameras(
        [
            {
                "id": "x",
                "stream_name": "rec_x",
                "detect_stream_name": "det_x",
                "name": "X",
            },
        ],
    )
    proc = cameras_for_processor(valid)
    assert proc == [
        {
            "id": "rec_x",
            "stream_name": "rec_x",
            "detect_stream_name": "det_x",
            "camera_slot": "camera_1",
        },
    ]


def test_cameras_for_processor_omits_detect_when_absent():
    """Processor dict has no detect key if unset."""
    valid = get_valid_cameras([{"id": "y", "stream_name": "only_y"}])
    proc = cameras_for_processor(valid)
    assert proc == [{"id": "only_y", "stream_name": "only_y", "camera_slot": "camera_1"}]


def test_cameras_preserve_opencv_masks():
    """Per-camera OpenCV masks survive valid/processor filtering."""
    raw = [
        {
            "id": "BirdBox",
            "stream_name": "bird",
            "detect_stream_name": "bird_det",
            "opencv_masks": ["0,0,1,0,1,0.1,0,0.1"],
        },
    ]
    valid = get_valid_cameras(raw)
    proc = cameras_for_processor(valid)
    assert valid[0]["opencv_masks"] == ["0,0,1,0,1,0.1,0,0.1"]
    assert proc[0]["opencv_masks"] == ["0,0,1,0,1,0.1,0,0.1"]


def test_get_valid_cameras_from_slot_config_with_profile_binding():
    valid = get_valid_cameras(
        video_config={
            "camera_profiles": {
                "closeup": {
                    "detect_stream_name": "feeder_detect",
                    "opencv_masks": ["0,0,1,0,1,1,0,1"],
                },
            },
            "camera_slots": [
                {
                    "slot": 1,
                    "profile": "closeup",
                    "id": "feeder",
                    "stream_name": "feeder_main",
                    "name": "Feeder",
                },
            ],
        },
    )
    assert valid == [
        {
            "id": "feeder_main",
            "stream_name": "feeder_main",
            "name": "Feeder",
            "camera_slot": "camera_1",
            "legacy_id": "feeder",
            "camera_profile": "closeup",
            "detect_stream_name": "feeder_detect",
            "opencv_masks": ["0,0,1,0,1,1,0,1"],
        },
    ]


def test_get_valid_cameras_dual_read_legacy_fallback():
    valid = get_valid_cameras(
        video_config={
            "cameras": [
                {
                    "id": "BirdBox",
                    "stream_name": "birdbox",
                    "detect_stream_name": "birdbox_det",
                },
                {
                    "id": "Forest",
                    "stream_name": "forest",
                    "detect_stream_name": "forest_det",
                    "camera_slot": "2",
                },
            ],
        },
    )
    assert [v["camera_slot"] for v in valid] == ["camera_1", "camera_2"]
    assert [v["id"] for v in valid] == ["birdbox", "forest"]
    assert [v["legacy_id"] for v in valid] == ["BirdBox", "Forest"]


def test_get_valid_cameras_preserves_tuning_role_and_zones():
    zones = [{"name": "feeder", "polygon": [[0, 0], [1, 0], [1, 1]]}]
    valid = get_valid_cameras(
        [
            {
                "id": "BirdBox",
                "stream_name": "BirdBox",
                "detect_stream_name": "BirdBox_detect",
                "tuning_role": "feeder_close",
                "detection_interest_zones": zones,
                "detection_interest_zones_required": True,
            }
        ],
    )

    assert valid[0]["tuning_role"] == "feeder_close"
    assert valid[0]["detection_interest_zones"] == zones
    assert valid[0]["detection_interest_zones_required"] is True

"""video.cameras: optional detect_stream_name (Frigate-style substream)."""

from app_config.cameras import cameras_for_processor, get_valid_cameras


def test_get_valid_cameras_without_detect_stream():
    """When detect_stream_name omitted, key is absent."""
    rows = get_valid_cameras(
        [{"id": "a", "stream_name": "main_a", "name": "A"}],
    )
    assert len(rows) == 1
    assert rows[0]["id"] == "a"
    assert rows[0]["stream_name"] == "main_a"
    assert rows[0]["camera_slot"] == "camera_1"
    assert "detect_stream_name" not in rows[0]


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
            "id": "x",
            "stream_name": "rec_x",
            "detect_stream_name": "det_x",
            "camera_slot": "camera_1",
        },
    ]


def test_cameras_for_processor_omits_detect_when_absent():
    """Processor dict has no detect key if unset."""
    valid = get_valid_cameras([{"id": "y", "stream_name": "only_y"}])
    proc = cameras_for_processor(valid)
    assert proc == [{"id": "y", "stream_name": "only_y", "camera_slot": "camera_1"}]


def test_cameras_preserve_opencv_masks():
    """Per-camera OpenCV masks survive valid/processor filtering."""
    raw = [
        {
            "id": "BirdBox",
            "stream_name": "bird",
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
            "id": "feeder",
            "stream_name": "feeder_main",
            "name": "Feeder",
            "camera_slot": "camera_1",
            "camera_profile": "closeup",
            "detect_stream_name": "feeder_detect",
            "opencv_masks": ["0,0,1,0,1,1,0,1"],
        },
    ]


def test_get_valid_cameras_dual_read_legacy_fallback():
    valid = get_valid_cameras(
        video_config={
            "cameras": [
                {"id": "BirdBox", "stream_name": "birdbox"},
                {"id": "Forest", "stream_name": "forest", "camera_slot": "2"},
            ],
        },
    )
    assert [v["camera_slot"] for v in valid] == ["camera_1", "camera_2"]

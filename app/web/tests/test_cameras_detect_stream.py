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
        {"id": "x", "stream_name": "rec_x", "detect_stream_name": "det_x"},
    ]


def test_cameras_for_processor_omits_detect_when_absent():
    """Processor dict has no detect key if unset."""
    valid = get_valid_cameras([{"id": "y", "stream_name": "only_y"}])
    proc = cameras_for_processor(valid)
    assert proc == [{"id": "y", "stream_name": "only_y"}]

"""Tests for stream_probe (SOTA-02 / #493)."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from stream_probe import (
    StreamCapabilities,
    _parse_fps_value,
    attach_stream_capabilities,
    force_recording_resolution,
    parse_configured_video_size,
    probe_processor_startup,
    probe_stream_ffprobe,
    probe_stream_url,
    resolve_main_size,
)


def test_parse_fps_fraction():
    assert _parse_fps_value("7/1") == 7.0
    assert _parse_fps_value("30000/1001") > 29.0


def test_parse_fps_invalid():
    assert _parse_fps_value("0/0") == 0.0
    assert _parse_fps_value(None) == 0.0


@patch("stream_probe.shutil.which", return_value="/usr/bin/ffprobe")
@patch("stream_probe.subprocess.run")
def test_probe_stream_ffprobe_parses_json(mock_run, _which):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(
            {
                "streams": [
                    {
                        "width": 704,
                        "height": 576,
                        "r_frame_rate": "7/1",
                        "avg_frame_rate": "7/1",
                    }
                ]
            }
        ),
        stderr="",
    )
    caps = probe_stream_ffprobe("rtsp://example/detect")
    assert caps is not None
    assert caps.width == 704
    assert caps.height == 576
    assert caps.fps == 7.0
    assert caps.source == "ffprobe"


@patch("stream_probe.probe_stream_ffprobe")
@patch("stream_probe.probe_stream_opencv")
def test_probe_stream_url_prefers_ffprobe_when_complete(mock_cv, mock_ff):
    mock_ff.return_value = StreamCapabilities(704, 576, 7.0, source="ffprobe")
    mock_cv.return_value = StreamCapabilities(640, 480, 25.0, source="opencv")
    caps = probe_stream_url("rtsp://x", prefer="auto")
    assert caps is not None
    assert caps.width == 704
    mock_cv.assert_not_called()


def test_resolve_main_size_probe_over_config_by_default():
    cfg = {"video.video_width": 1920, "video.video_height": 1080}
    probe = StreamCapabilities(704, 576, 7.0)
    assert resolve_main_size(cfg, probe) == (704, 576)


def test_resolve_main_size_force_config_over_probe():
    cfg = {
        "video.video_width": 1920,
        "video.video_height": 1080,
        "video.force_recording_resolution": True,
    }
    probe = StreamCapabilities(704, 576, 7.0)
    assert resolve_main_size(cfg, probe) == (1920, 1080)
    assert force_recording_resolution(cfg) is True


def test_parse_configured_video_size_zero_is_auto():
    assert parse_configured_video_size({"video.video_width": 0, "video.video_height": 0}) is None


def test_resolve_main_size_from_probe():
    cfg = {}
    probe = StreamCapabilities(704, 576, 7.0)
    assert resolve_main_size(cfg, probe) == (704, 576)


def test_resolve_main_size_raises_without_config_or_probe():
    with pytest.raises(ValueError, match="stream probe failed"):
        resolve_main_size({}, None)


def test_resolve_main_size_ignores_config_without_force_when_probe_missing():
    cfg = {"video.video_width": 1920, "video.video_height": 1080}
    with pytest.raises(ValueError, match="stream probe failed"):
        resolve_main_size(cfg, None)


@patch("stream_probe.probe_stream_url")
def test_probe_processor_startup_go2rtc_probes_first_record_stream(mock_probe):
    mock_probe.return_value = StreamCapabilities(2688, 1520, 20.0, source="ffprobe")
    cfg = {
        "video.source": "go2rtc",
        "video.go2rtc_url": "http://192.168.1.11:1984",
        "video.go2rtc_username": "user",
        "video.go2rtc_password": "frigate",
        "video.cameras": [{"id": "BirdBox", "stream_name": "BirdBox"}],
    }
    caps = probe_processor_startup(cfg)
    assert caps is not None
    assert caps.main_size == (2688, 1520)
    called_url = mock_probe.call_args[0][0]
    assert ":8554/" in called_url
    assert called_url.endswith("/BirdBox")


def test_attach_stream_capabilities_sets_fps():
    src = MagicMock()
    caps = StreamCapabilities(1280, 720, 12.5, source="ffprobe")
    attach_stream_capabilities(src, caps)
    assert src.stream_capabilities == caps
    assert src.source_fps == 12.5
    assert src._source_fps == 12.5


@patch("stream_probe.probe_stream_opencv")
@patch("stream_probe.probe_stream_ffprobe", return_value=None)
def test_probe_stream_url_opencv_fallback(_ff, mock_cv):
    mock_cv.return_value = StreamCapabilities(640, 480, 10.0, source="measured")
    caps = probe_stream_url("rtsp://x", prefer="auto")
    assert caps is not None
    assert caps.fps == 10.0

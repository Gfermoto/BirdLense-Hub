"""Проверки status_service.check_video_reachable."""

from __future__ import annotations

from unittest.mock import patch

from services import status_service


def test_resolve_go2rtc_base_url_defaults_to_local():
    with patch.dict("os.environ", {}, clear=False):
        assert status_service.resolve_go2rtc_base_url() == "http://127.0.0.1:1984"


def test_check_video_reachable_ok_via_hub_proxy(monkeypatch):
    monkeypatch.setattr(
        status_service.app_config,
        "get",
        lambda key, default=None: (
            [{"id": "BirdBox", "stream_name": "BirdBox"}]
            if key == "video.cameras"
            else default
        ),
    )
    with patch.dict(status_service.os.environ, {"BIRDLENSE_PORT": "8085"}, clear=False):
        with patch.object(status_service, "_probe_frame_url", side_effect=[False, True]):
            assert status_service.check_video_reachable() == "ok"


def test_check_video_reachable_not_configured_without_cameras(monkeypatch):
    monkeypatch.setattr(status_service.app_config, "get", lambda key, default=None: [])
    assert status_service.check_video_reachable() == "not_configured"

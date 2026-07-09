"""SOTA-08: /api/debug/motion-preview."""

from __future__ import annotations

import numpy as np


def test_motion_preview_requires_auth(client, monkeypatch):
    import routes.debug_motion_preview_routes as routes_mod

    monkeypatch.setattr(routes_mod, "settings_check_access", lambda: False)
    r = client.get("/api/debug/motion-preview")
    assert r.status_code == 403


def test_motion_preview_synthetic(client, monkeypatch):
    import services.motion_preview_debug_service as svc

    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    frame[20:40, 20:40] = 200

    monkeypatch.setattr(svc, "_fetch_camera_frame_bgr", lambda _cid: (frame, None))
    import routes.debug_motion_preview_routes as routes_mod

    monkeypatch.setattr(routes_mod, "settings_check_access", lambda: True)

    r = client.get("/api/debug/motion-preview", query_string={"mode": "detection_mog2"})
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("image_jpeg_base64")
    assert isinstance(body.get("warnings"), list)

"""Auth regression tests for video routes."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from flask import Flask


def test_fusion_trace_allows_mcp_style_non_session_access(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "app_config.app_config",
        types.SimpleNamespace(app_config=types.SimpleNamespace(get=lambda *a, **k: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "auth",
        types.SimpleNamespace(
            contributor_or_admin_access=lambda: False,
            ui_sensitive_export_access=lambda: False,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "models",
        types.SimpleNamespace(
            Species=object,
            SpeciesVisit=object,
            Video=object,
            VideoSpecies=object,
            db=types.SimpleNamespace(session=None),
        ),
    )
    monkeypatch.setitem(sys.modules, "sqlalchemy", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "sqlalchemy.orm", types.SimpleNamespace(joinedload=lambda *a, **k: None))
    monkeypatch.setitem(
        sys.modules,
        "services.api_json_validation",
        types.SimpleNamespace(parse_request_json_dict=lambda request: ({}, None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.cache",
        types.SimpleNamespace(cache_get=lambda key: (False, None), cache_set=lambda *a, **k: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.dataset_export_service",
        types.SimpleNamespace(
            extract_and_save_crop_for_detection=lambda *a, **k: None,
            move_crop_on_species_correction=lambda *a, **k: False,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.detection_crop_service",
        types.SimpleNamespace(VIDEO_PATH_SAFE_RE=types.SimpleNamespace(match=lambda *_: True)),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.http_response_cache",
        types.SimpleNamespace(
            bust_response_caches=lambda: None,
            bust_all_api_caches=lambda: None,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.video_neighbors_service",
        types.SimpleNamespace(
            VideoNeighborsParamError=ValueError,
            build_video_neighbors_payload=lambda *a, **k: {},
            parse_video_neighbors_request_args=lambda args: ("utc", False, "video", None, 0),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.fusion_trace_service",
        types.SimpleNamespace(build_fusion_trace_api_payload=lambda video_id: ({"video_id": video_id}, 200)),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.video_payload_service",
        types.SimpleNamespace(
            build_video_detail_dict=lambda video: {},
            build_video_detection_frames_dict=lambda video: {},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.favorites_catalog_service",
        types.SimpleNamespace(build_favorites_by_species_payload=lambda session: {}),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.visit_processor",
        types.SimpleNamespace(VisitProcessor=object),
    )
    monkeypatch.setitem(
        sys.modules,
        "util",
        types.SimpleNamespace(
            ensure_utc=lambda value: value,
            full_path_for_video=lambda path: path,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "routes.ui_route_constants",
        types.SimpleNamespace(CACHE_DETECTION_FRAMES_SEC=30, CACHE_FAVORITES_CATALOG_SEC=30),
    )

    module_path = Path(__file__).resolve().parents[1] / "routes" / "ui_video_routes.py"
    spec = importlib.util.spec_from_file_location("test_ui_video_routes_mod", module_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    app = Flask(__name__)
    monkeypatch.setattr(mod, "contributor_or_admin_access", lambda: False)
    monkeypatch.setattr(mod, "ui_sensitive_export_access", lambda: True)
    monkeypatch.setattr(
        mod,
        "build_fusion_trace_api_payload",
        lambda video_id: ({"video_id": video_id, "available": False}, 200),
    )

    mod.register_ui_video_routes(app)
    client = app.test_client()

    response = client.get(
        "/api/ui/videos/77/fusion-trace",
        headers={"Authorization": "Bearer mcp-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["video_id"] == 77

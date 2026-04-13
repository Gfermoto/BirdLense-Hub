"""GET/POST /api/ui/system/file-test/* (#270)."""

from __future__ import annotations

import io

import pytest

from app_config.app_config import app_config


def _patch_general_key(monkeypatch, key: str, value):
    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, key, value)


def _open_access(monkeypatch):
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    _patch_general_key(monkeypatch, "settings_password", "")
    _patch_general_key(monkeypatch, "contributor_password", "")


@pytest.fixture
def file_mode_tmp(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    d = tmp_path / "file_test"
    d.mkdir(parents=True, exist_ok=True)
    app_config.set("video.source", "file")
    app_config.set("video.file_dir", str(d))
    yield d


def test_file_test_files_409_when_not_file_source(client, monkeypatch):
    _open_access(monkeypatch)
    app_config.set("video.source", "go2rtc")
    r = client.get("/api/ui/system/file-test/files")
    assert r.status_code == 409


def test_file_test_list_and_status(client, monkeypatch, file_mode_tmp):
    _open_access(monkeypatch)
    (file_mode_tmp / "a.mp4").write_bytes(b"")
    r = client.get("/api/ui/system/file-test/files")
    assert r.status_code == 200
    body = r.get_json()
    assert body["file_dir"]
    assert len(body["files"]) == 1
    assert body["files"][0]["name"] == "a.mp4"

    r2 = client.get("/api/ui/system/file-test/status")
    assert r2.status_code == 200
    st = r2.get_json()
    assert st["video_source"] == "file"
    assert "desired" in st


def test_file_test_upload_delete_admin(client, monkeypatch, file_mode_tmp):
    _open_access(monkeypatch)
    data = {"file": (io.BytesIO(b"fake-mp4"), "clip.mp4")}
    r = client.post("/api/ui/system/file-test/upload", data=data, content_type="multipart/form-data")
    assert r.status_code == 201
    assert r.get_json().get("name") == "clip.mp4"
    assert (file_mode_tmp / "clip.mp4").is_file()

    r2 = client.delete("/api/ui/system/file-test/files/clip.mp4")
    assert r2.status_code == 200
    assert not (file_mode_tmp / "clip.mp4").exists()


def test_file_test_run_stop_writes_desired(client, monkeypatch, file_mode_tmp):
    import json
    import os

    _open_access(monkeypatch)
    from services.system_file_test_service import DESIRED_NAME, _control_dir

    r = client.post("/api/ui/system/file-test/run", json={"armed": True, "loop": True})
    assert r.status_code == 200
    desired_path = os.path.join(_control_dir(), DESIRED_NAME)
    with open(desired_path, encoding="utf-8") as f:
        d = json.load(f)
    assert d.get("armed") is True
    assert d.get("loop") is True

    r2 = client.post("/api/ui/system/file-test/stop", json={})
    assert r2.status_code == 200
    with open(desired_path, encoding="utf-8") as f:
        d2 = json.load(f)
    assert d2.get("armed") is False

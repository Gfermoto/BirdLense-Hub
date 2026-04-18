"""GET/POST /api/ui/system/processor-weights/* (#276)."""

from __future__ import annotations

import io
import zipfile

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


def _fake_pt_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("data.pkl", b"\x00" * 5000)
    return buf.getvalue()


@pytest.fixture
def isolated_user_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    uc = tmp_path / "user_config.yaml"
    uc.write_text("processor:\n  models: {}\n", encoding="utf-8")
    monkeypatch.setattr(app_config, "user_config_file", str(uc))
    app_config.reload()
    yield uc
    app_config.reload()


def test_processor_weights_status_ok(client, monkeypatch, isolated_user_config):
    _open_access(monkeypatch)
    r = client.get("/api/ui/system/processor-weights/status")
    assert r.status_code == 200
    body = r.get_json()
    assert "binary" in body and "classifier" in body and "allowlist" in body
    assert "custom_weights_dir" in body
    assert body["binary"].get("path")
    assert "fingerprint_sha256_16" in body["binary"]


def test_processor_weights_upload_binary_and_reset(client, monkeypatch, isolated_user_config):
    _open_access(monkeypatch)
    data = {"file": (io.BytesIO(_fake_pt_bytes()), "custom.pt")}
    r = client.post(
        "/api/ui/system/processor-weights/upload?role=binary",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("ok") is True
    cw = j.get("status", {}).get("custom_weights_dir")
    assert cw
    assert j["status"]["binary"]["fingerprint_sha256_16"]
    import os

    assert os.path.isfile(os.path.join(cw, "binary.pt"))

    r2 = client.post("/api/ui/system/processor-weights/reset", json={"roles": ["binary"]})
    assert r2.status_code == 200
    assert not os.path.isfile(os.path.join(cw, "binary.pt"))


def test_processor_weights_classifier_requires_allowlist_or_ack(client, monkeypatch, isolated_user_config):
    _open_access(monkeypatch)
    # break allowlist path so classifier upload is blocked without ack
    app_config.set("species.catalog_allowlist_file", "/nonexistent/allowlist.txt")
    data = {"file": (io.BytesIO(_fake_pt_bytes()), "c.pt")}
    r = client.post(
        "/api/ui/system/processor-weights/upload?role=classifier",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert r.get_json().get("error") == "allowlist_missing_upload_class_names_or_ack"

    data2 = {"file": (io.BytesIO(_fake_pt_bytes()), "c.pt")}
    r2 = client.post(
        "/api/ui/system/processor-weights/upload?role=classifier&acknowledge_classifier_only=1",
        data=data2,
        content_type="multipart/form-data",
    )
    assert r2.status_code == 200


def test_processor_weights_class_names_upload(client, monkeypatch, isolated_user_config):
    _open_access(monkeypatch)
    txt = "Parus major (Great Tit)\n"
    data = {"file": (io.BytesIO(txt.encode("utf-8")), "class_names.txt")}
    r = client.post(
        "/api/ui/system/processor-weights/upload?role=class_names",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 200

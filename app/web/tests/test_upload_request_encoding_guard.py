"""#341: запрет сжатого Content-Encoding на upload-эндпоинтах."""

from __future__ import annotations


def test_file_upload_rejects_gzip_content_encoding(client):
    """gzip в заголовке → 415 до декораторов auth."""
    r = client.post(
        "/api/ui/system/file-test/upload",
        headers={"Content-Encoding": "gzip"},
        data=b"x",
    )
    assert r.status_code == 415
    body = r.get_json()
    assert body.get("error")


def test_file_upload_allows_missing_content_encoding(client):
    """Без Content-Encoding доходит до вью (не 415)."""
    r = client.post("/api/ui/system/file-test/upload", data={})
    assert r.status_code != 415


def test_yaml_import_rejects_br(client):
    """Brotli token → 415."""
    r = client.post(
        "/api/ui/settings/yaml-import",
        headers={"Content-Encoding": "br"},
        data=b"x",
    )
    assert r.status_code == 415


def test_upload_allows_identity_only(client):
    """Явный identity разрешён."""
    r = client.post(
        "/api/ui/system/file-test/upload",
        headers={"Content-Encoding": "identity"},
        data={},
    )
    assert r.status_code != 415

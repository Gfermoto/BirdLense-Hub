"""UI API for NAS/SFTP recordings mirror (#350)."""

from app_config.app_config import app_config


def test_recordings_mirror_test_requires_host_and_username(client):
    old_storage = app_config.config.get("storage")
    try:
        app_config.config["storage"] = {
            "recordings_mirror": {
                "protocol": "sftp",
                "host": "",
                "username": "",
            }
        }
        response = client.post("/api/ui/storage/recordings-mirror/test", json={})
        assert response.status_code == 400
        assert response.get_json()["ok"] is False
    finally:
        if old_storage is None:
            app_config.config.pop("storage", None)
        else:
            app_config.config["storage"] = old_storage


def test_recordings_mirror_test_requires_password_or_key(client):
    old_storage = app_config.config.get("storage")
    try:
        app_config.config["storage"] = {
            "recordings_mirror": {
                "protocol": "sftp",
                "host": "nas.local",
                "username": "birdlense",
                "sftp_password": "",
                "ssh_private_key_path": "",
            }
        }
        response = client.post("/api/ui/storage/recordings-mirror/test", json={})
        assert response.status_code == 400
        assert "password" in response.get_json()["error"].lower()
    finally:
        if old_storage is None:
            app_config.config.pop("storage", None)
        else:
            app_config.config["storage"] = old_storage

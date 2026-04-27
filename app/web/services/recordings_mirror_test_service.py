"""SFTP mirror connection test for UI-managed NAS settings (#350)."""

from __future__ import annotations

import os
from typing import Any

from app_config.app_config import app_config


def _mirror_config() -> dict[str, Any]:
    storage = app_config.config.get("storage") or {}
    if not isinstance(storage, dict):
        return {}
    mirror = storage.get("recordings_mirror") or {}
    return mirror if isinstance(mirror, dict) else {}


def _mkdir_p(sftp: Any, remote_dir: str) -> None:
    remote_dir = remote_dir.replace("\\", "/").rstrip("/")
    if not remote_dir or remote_dir == "/":
        return
    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir
    cur = ""
    for part in [p for p in remote_dir.split("/") if p]:
        cur = f"{cur}/{part}"
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def test_recordings_mirror_connection() -> tuple[dict, int]:
    """Connect to configured SFTP target and ensure the remote base dir exists."""
    cfg = _mirror_config()
    proto = str(cfg.get("protocol") or "sftp").strip().lower()
    if proto != "sftp":
        return {"ok": False, "error": "Only SFTP is supported"}, 400

    host = str(cfg.get("host") or "").strip()
    username = str(cfg.get("username") or "").strip()
    if not host or not username:
        return {"ok": False, "error": "SFTP host and username are required"}, 400

    password = str(app_config.get("storage.recordings_mirror.sftp_password") or "").strip()
    key_path = str(cfg.get("ssh_private_key_path") or "").strip()
    key_pass = str(app_config.get("storage.recordings_mirror.sftp_key_passphrase") or "").strip()
    if not password and not (key_path and os.path.isfile(key_path)):
        return {"ok": False, "error": "SFTP password or SSH private key path is required"}, 400

    import paramiko

    try:
        port = int(cfg.get("port") or 22)
    except (TypeError, ValueError):
        port = 22
    remote_base = str(cfg.get("remote_base_path") or "/birdlense/recordings").strip() or "/birdlense/recordings"
    strict = bool(cfg.get("strict_host_key", True))

    client = paramiko.SSHClient()
    try:
        if strict:
            known_hosts = str(cfg.get("known_hosts_path") or "").strip()
            if known_hosts and os.path.isfile(known_hosts):
                client.load_host_keys(known_hosts)
            else:
                client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507

        connect_kw: dict[str, Any] = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 15,
            "banner_timeout": 15,
        }
        if password:
            connect_kw["password"] = password
        if key_path and os.path.isfile(key_path):
            connect_kw["key_filename"] = key_path
            if key_pass:
                connect_kw["passphrase"] = key_pass

        client.connect(**connect_kw)
        sftp = client.open_sftp()
        try:
            _mkdir_p(sftp, remote_base)
            sftp.stat(remote_base)
        finally:
            sftp.close()
        return {"ok": True, "remote_base_path": remote_base}, 200
    except Exception as e:
        return {"ok": False, "error": str(e) or type(e).__name__}, 502
    finally:
        client.close()

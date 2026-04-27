"""Фоновое зеркалирование каталога сессии записи на SFTP (NAS), issue #350.

Запись по-прежнему идёт на локальный диск; после финализации сессии (каталог
ещё на диске) ставится задача на загрузку копии на удалённый SFTP без блокировки
finalize. Пути в БД не меняются.
"""

from __future__ import annotations

import logging
import os
import posixpath
import shutil
import threading
import time
from typing import Any

from app_config.app_config import app_config
from processor_runtime_stats import inc_counter
from processor_support import get_data_dir

logger = logging.getLogger(__name__)

_mirror_sem_lock = threading.Lock()
_mirror_sem_state: dict[str, Any] = {"n": 0, "sem": None}


def _mirror_block() -> dict[str, Any]:
    st = app_config.config.get("storage") or {}
    if not isinstance(st, dict):
        return {}
    rm = st.get("recordings_mirror")
    return rm if isinstance(rm, dict) else {}


def _mirror_enabled() -> bool:
    b = _mirror_block()
    if not bool(b.get("enabled")):
        return False
    proto = str(b.get("protocol") or "sftp").strip().lower()
    return proto == "sftp"


def _semaphore(max_concurrent: int) -> threading.BoundedSemaphore:
    n = max(1, min(8, int(max_concurrent or 2)))
    with _mirror_sem_lock:
        if _mirror_sem_state["sem"] is None or int(_mirror_sem_state["n"]) != n:
            _mirror_sem_state["n"] = n
            _mirror_sem_state["sem"] = threading.BoundedSemaphore(n)
        return _mirror_sem_state["sem"]


def _session_relative_to_recordings(session_dir: str, recordings_root: str) -> str | None:
    try:
        rec_real = os.path.realpath(recordings_root)
        sess_real = os.path.realpath(session_dir)
    except (OSError, ValueError):
        return None
    if not sess_real.startswith(rec_real.rstrip(os.sep) + os.sep) and sess_real != rec_real:
        return None
    try:
        rel = os.path.relpath(sess_real, rec_real)
    except ValueError:
        return None
    if rel.startswith(".." + os.sep) or rel == "..":
        return None
    return rel.replace(os.sep, "/")


def _mkdir_p(sftp: Any, remote_dir: str) -> None:
    """Создать цепочку каталогов на SFTP (по одному уровню)."""
    remote_dir = remote_dir.replace("\\", "/").rstrip("/")
    if not remote_dir or remote_dir == "/":
        return
    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir
    parts = [p for p in remote_dir.split("/") if p]
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}"
        try:
            sftp.stat(cur)
        except OSError:
            try:
                sftp.mkdir(cur)
            except OSError as e:
                logger.warning("recordings_mirror: mkdir %s: %s", cur, e)


def _upload_session_impl(session_dir: str) -> None:
    import paramiko

    cfg = _mirror_block()
    host = str(cfg.get("host") or "").strip()
    username = str(cfg.get("username") or "").strip()
    if not host or not username:
        logger.info("recordings_mirror: disabled or incomplete host/username")
        return

    password = str(app_config.get("storage.recordings_mirror.sftp_password") or "").strip()
    key_path = str(cfg.get("ssh_private_key_path") or "").strip()
    key_pass = str(app_config.get("storage.recordings_mirror.sftp_key_passphrase") or "").strip()

    if not password and not (key_path and os.path.isfile(key_path)):
        logger.warning(
            "recordings_mirror: no credentials (set SFTP password in Library → Storage or "
            "user_config storage.recordings_mirror; optional env BIRDLENSE_RECORDINGS_MIRROR_SFTP_*; "
            "or ssh_private_key_path to a key inside the container)",
        )
        inc_counter("recordings_mirror_uploads_failed_total")
        return

    try:
        port = int(cfg.get("port") or 22)
    except (TypeError, ValueError):
        port = 22

    recordings_root = os.path.join(get_data_dir(), "recordings")
    rel = _session_relative_to_recordings(session_dir, recordings_root)
    if not rel:
        logger.warning("recordings_mirror: session dir outside recordings: %s", session_dir)
        inc_counter("recordings_mirror_uploads_failed_total")
        return

    remote_base = str(cfg.get("remote_base_path") or "/birdlense/recordings").strip().replace("\\", "/").rstrip("/")
    if not remote_base.startswith("/"):
        remote_base = "/" + remote_base
    remote_session_prefix = posixpath.join(remote_base, rel.replace("\\", "/"))

    retries = max(1, min(10, int(cfg.get("upload_retries") or 3)))
    backoff = max(1.0, float(cfg.get("retry_backoff_seconds") or 5.0))
    strict = bool(cfg.get("strict_host_key", True))

    last_err: Exception | None = None
    for attempt in range(retries):
        client = paramiko.SSHClient()
        try:
            if strict:
                kh_path = str(cfg.get("known_hosts_path") or "").strip()
                if kh_path and os.path.isfile(kh_path):
                    client.load_host_keys(kh_path)
                else:
                    client.load_system_host_keys()
                client.set_missing_host_key_policy(paramiko.RejectPolicy())
            else:
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kw: dict[str, Any] = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": 30,
                "banner_timeout": 30,
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
                for root, _dirs, files in os.walk(session_dir):
                    for name in files:
                        local_path = os.path.join(root, name)
                        rel_file = os.path.relpath(local_path, session_dir).replace(os.sep, "/")
                        remote_path = posixpath.join(
                            remote_session_prefix.replace("\\", "/"),
                            rel_file,
                        )
                        parent = posixpath.dirname(remote_path)
                        _mkdir_p(sftp, parent)
                        sftp.put(local_path, remote_path)
            finally:
                try:
                    sftp.close()
                except Exception:
                    pass
            client.close()
            inc_counter("recordings_mirror_uploads_success_total")
            logger.info(
                "recordings_mirror: uploaded session %s -> %s",
                rel,
                remote_session_prefix,
            )

            if bool(cfg.get("delete_local_after_success")):
                try:
                    shutil.rmtree(session_dir, ignore_errors=False)
                    logger.warning(
                        "recordings_mirror: removed local session after upload (delete_local_after_success): %s",
                        session_dir,
                    )
                    inc_counter("recordings_mirror_local_deleted_after_upload_total")
                except OSError as e:
                    logger.error("recordings_mirror: failed to remove local session %s: %s", session_dir, e)

            return
        except Exception as e:
            last_err = e
            logger.warning(
                "recordings_mirror: attempt %s/%s failed: %s",
                attempt + 1,
                retries,
                e,
            )
            try:
                client.close()
            except Exception:
                pass
            if attempt + 1 < retries:
                time.sleep(backoff * (2**attempt))

    if last_err:
        logger.error("recordings_mirror: giving up on %s: %s", session_dir, last_err)
    inc_counter("recordings_mirror_uploads_failed_total")


def _upload_worker(session_dir: str) -> None:
    sem = _semaphore(int(_mirror_block().get("max_concurrent_uploads") or 2))
    sem.acquire()
    try:
        _upload_session_impl(session_dir)
    except Exception as e:
        logger.exception("recordings_mirror: unexpected error: %s", e)
        inc_counter("recordings_mirror_uploads_failed_total")
    finally:
        try:
            sem.release()
        except ValueError:
            pass


def schedule_recordings_session_mirror(session_dir: str) -> None:
    """Поставить фоновую загрузку каталога сессии, если зеркало включено и каталог есть."""
    if not _mirror_enabled():
        return
    if not session_dir or not os.path.isdir(session_dir):
        return

    t = threading.Thread(
        target=_upload_worker,
        args=(session_dir,),
        name="recordings-remote-mirror",
        daemon=True,
    )
    t.start()
    inc_counter("recordings_mirror_uploads_scheduled_total")

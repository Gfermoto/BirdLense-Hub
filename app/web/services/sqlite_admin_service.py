"""SQLite: проверка целостности, backup, замена live БД (#265)."""
from __future__ import annotations

import os
import shutil
import sqlite3


def sqlite_main_file_path(engine) -> str | None:
    """Путь к файлу для sqlite:///:memory: остаётся ':memory:' (не файловый)."""
    if not str(engine.url).startswith('sqlite:///'):
        return None
    path = engine.url.database
    return path or None


def validate_sqlite_file(path: str) -> None:
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        check = conn.execute('PRAGMA integrity_check;').fetchone()
        if not check or check[0] != 'ok':
            raise sqlite3.DatabaseError('integrity_check failed')


def backup_sqlite_to_file(src_path: str, dst_path: str) -> None:
    parent = os.path.dirname(dst_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(src_path, timeout=30) as src_conn:
        src_conn.execute('PRAGMA busy_timeout = 30000')
        with sqlite3.connect(dst_path, timeout=30) as dst_conn:
            dst_conn.execute('PRAGMA busy_timeout = 30000')
            src_conn.backup(dst_conn)
            dst_conn.commit()


def remove_sqlite_sidecars(db_path: str) -> None:
    for suffix in ('-wal', '-shm'):
        sidecar = f'{db_path}{suffix}'
        try:
            if os.path.exists(sidecar):
                os.remove(sidecar)
        except OSError:
            pass


def replace_live_sqlite_db(live_db_path: str, restored_path: str) -> None:
    if os.path.isfile(live_db_path):
        shutil.copymode(live_db_path, restored_path)
    remove_sqlite_sidecars(live_db_path)
    os.replace(restored_path, live_db_path)
    remove_sqlite_sidecars(live_db_path)

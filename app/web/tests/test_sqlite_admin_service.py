"""Юнит-тесты sqlite_admin_service (#293)."""

from sqlalchemy import create_engine

from services.sqlite_admin_service import sqlite_main_file_path


def test_sqlite_main_file_path_memory_database_name():
    eng = create_engine("sqlite:///:memory:")
    assert sqlite_main_file_path(eng) == ":memory:"


def test_sqlite_main_file_path_none_for_non_sqlite_engine():
    class _Url:
        database = "db"

        def __str__(self):
            return "postgresql://localhost/db"

    class _Eng:
        url = _Url()

    assert sqlite_main_file_path(_Eng()) is None


def test_sqlite_main_file_path_file(tmp_path):
    p = tmp_path / "hub.db"
    eng = create_engine(f"sqlite:///{p}")
    assert sqlite_main_file_path(eng) == str(p)

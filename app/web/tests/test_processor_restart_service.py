"""Юнит-тесты services.processor_restart_service (#293)."""

import os

from services.processor_restart_service import write_processor_restart_flag


def test_write_processor_restart_flag_creates_files(tmp_path):
    base = str(tmp_path / "data")
    write_processor_restart_flag(base)
    assert os.path.isfile(os.path.join(base, "restart_processor.flag"))
    assert os.path.isfile(os.path.join(base, ".startup_notify_skip"))
    with open(os.path.join(base, "restart_processor.flag"), encoding="utf-8") as f:
        assert f.read() == "1"

"""Tests for processor_exception_handling (#619)."""

from __future__ import annotations

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestProcessorExceptionHandling(unittest.TestCase):
    def test_reraise_memory_error(self):
        from processor_exception_handling import reraise_if_io_critical

        with self.assertRaises(MemoryError):
            reraise_if_io_critical(MemoryError("oom"))

    def test_reraise_os_error(self):
        from processor_exception_handling import reraise_if_io_critical

        with self.assertRaises(OSError):
            reraise_if_io_critical(OSError("disk full"))

    def test_swallows_value_error(self):
        from processor_exception_handling import reraise_if_io_critical

        reraise_if_io_critical(ValueError("bad value"))

    def test_reraise_critical_only_memory_for_probe_path(self):
        from processor_exception_handling import reraise_if_critical

        with self.assertRaises(MemoryError):
            reraise_if_critical(MemoryError("oom"))
        reraise_if_critical(OSError("network"))


if __name__ == "__main__":
    unittest.main()

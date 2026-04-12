"""Shim: реализация в app_config (общая с веб-слоем снимка FIFO)."""

from app_config.birdnet_merge_key import (  # noqa: F401
    birdnet_merge_key,
    reset_birdnet_merge_key_cache_for_tests,
    sqlite_path_for_birdnet_merge,
)

__all__ = [
    "birdnet_merge_key",
    "reset_birdnet_merge_key_cache_for_tests",
    "sqlite_path_for_birdnet_merge",
]

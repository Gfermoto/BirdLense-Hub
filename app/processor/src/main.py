"""Точка входа процессора: heartbeat + цикл движения (сборка в processor_bootstrap)."""

import logging

from processor_cv2_init import configure_opencv_ffmpeg_logging

configure_opencv_ffmpeg_logging()

from processor_bootstrap import (
    build_processor_run_context,
    close_processor_media,
    parse_processor_args,
    run_motion_loop,
)
from processor_support import start_heartbeat_daemon, start_opencv_overlay_daemon


def main() -> None:
    """Запуск фонового heartbeat, сборка пайплайна и главный цикл до выхода."""
    from processor_config_guard import assert_processor_config_valid

    assert_processor_config_valid()
    args = parse_processor_args()
    ctx = build_processor_run_context(args)
    start_heartbeat_daemon()
    start_opencv_overlay_daemon()
    try:
        run_motion_loop(ctx)
    finally:
        try:
            close_processor_media(ctx)
        except Exception as e:
            logging.warning("Media close failed: %s", e)


if __name__ == "__main__":
    main()

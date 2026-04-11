"""Корневая настройка logging процесса Hub (#292)."""

from __future__ import annotations

import logging


def configure_process_logging() -> None:
    """Один раз на процесс: консольный handler, формат как раньше в app.py."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()],
    )

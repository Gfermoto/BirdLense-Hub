"""Session directory cleanup helpers for finalized recordings."""

from __future__ import annotations

import logging
import shutil


def remove_session_dir(path: str, *, reason: str) -> None:
    try:
        shutil.rmtree(path)
    except OSError as err:
        logging.warning(
            "Finalize: could not remove %s session dir %s: %s",
            reason,
            path,
            err,
        )

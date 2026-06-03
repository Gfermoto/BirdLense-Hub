"""Retention scheduler must read nested retention.* via app_config.get()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize(
    ("days", "max_gb", "should_run"),
    [
        (90, 32, True),
        (None, 32, True),
        (90, None, True),
        (None, None, False),
    ],
)
def test_scheduled_retention_reads_nested_config(days, max_gb, should_run):
    from services import retention_scheduler_service as sched

    app = MagicMock()
    with patch.object(sched.app_config, "get") as get_mock:
        get_mock.side_effect = lambda key, default=None: {
            "retention.auto_run_enabled": True,
            "retention.mode": "cascade",
            "retention.days": days,
            "retention.max_gb": max_gb,
        }.get(key, default)

        with patch("services.retention_service.run_retention") as run_mock:
            run_mock.return_value = (0, 0)
            sched.maybe_run_scheduled_retention(app)

    if should_run:
        run_mock.assert_called_once()
    else:
        run_mock.assert_not_called()

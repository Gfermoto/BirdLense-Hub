"""Retention scheduler must read nested retention.* via app_config.get()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize(
    ("days", "max_gb", "should_check"),
    [
        (90, 32, True),
        (None, 32, True),
        (90, None, True),
        (None, None, False),
    ],
)
def test_scheduled_retention_reads_nested_config(days, max_gb, should_check):
    from services import retention_scheduler_service as sched

    app = MagicMock()
    with patch.object(sched.app_config, "get") as get_mock:
        get_mock.side_effect = lambda key, default=None: {
            "retention.auto_run_enabled": True,
            "retention.mode": "cascade",
            "retention.days": days,
            "retention.max_gb": max_gb,
        }.get(key, default)

        with patch(
            "services.quota_maintainer.quota_deletion_pending",
            return_value=(False, ""),
        ) as pending_mock:
            with patch("services.quota_maintainer.run_quota_trim") as run_mock:
                sched.maybe_run_scheduled_retention(app)

    if should_check:
        pending_mock.assert_called_once()
        run_mock.assert_not_called()
    else:
        pending_mock.assert_not_called()
        run_mock.assert_not_called()


@pytest.mark.parametrize(
    ("pending", "reason", "should_run"),
    [
        (True, "days", True),
        (True, "max_gb", True),
        (False, "", False),
    ],
)
def test_scheduler_skips_when_not_pending(pending, reason, should_run):
    from services import retention_scheduler_service as sched

    app = MagicMock()
    with patch.object(sched.app_config, "get") as get_mock:
        get_mock.side_effect = lambda key, default=None: {
            "retention.auto_run_enabled": True,
            "retention.mode": "cascade",
            "retention.days": 90,
            "retention.max_gb": 32,
        }.get(key, default)

        with patch(
            "services.quota_maintainer.quota_deletion_pending",
            return_value=(pending, reason),
        ):
            with patch("services.quota_maintainer.run_quota_trim") as run_mock:
                run_mock.return_value = (0, 0)
                sched.maybe_run_scheduled_retention(app)

    if should_run:
        run_mock.assert_called_once_with(dry_run=False, policy_scope=reason)
    else:
        run_mock.assert_not_called()

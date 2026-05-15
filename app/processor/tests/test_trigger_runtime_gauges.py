"""Tests for trigger_runtime_gauges (Scale B1 / #432)."""

import os
import sys
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)


def test_trigger_gauges_frigate_degraded_without_live_mqtt(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import processor_runtime_stats as prs
    import trigger_runtime_gauges as trg

    prs.reset_runtime_stats_for_tests()

    tc = {
        "opencv": {"enabled": True},
        "frigate": {"enabled": True},
        "motion_sensor": {"enabled": False},
        "scales": {"enabled": False},
    }

    class Agg:
        def is_mqtt_live(self):
            return False

    with patch.object(trg, "get_active_trigger_names", return_value=["frigate", "opencv"]), patch.object(
        trg,
        "effective_active_trigger_names_for_mqtt_status",
        return_value=["opencv"],
    ):
        trg.refresh_trigger_runtime_gauges(
            mqtt_broker="mqtt.local",
            mqtt_aggregator=Agg(),
            trigger_config=tc,
        )

    snap = prs.runtime_stats_snapshot()
    assert snap["gauges"]["trigger_cfg_frigate_enabled"] == 1
    assert snap["gauges"]["trigger_mqtt_live"] == 0
    assert snap["gauges"]["trigger_frigate_degraded_no_mqtt"] == 1
    assert snap["gauges"]["trigger_degraded_effective_lt_configured"] == 1


def test_trigger_gauges_no_degrade_when_mqtt_not_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import processor_runtime_stats as prs
    import trigger_runtime_gauges as trg

    prs.reset_runtime_stats_for_tests()

    tc = {
        "opencv": {"enabled": True},
        "frigate": {"enabled": True},
        "motion_sensor": {"enabled": False},
        "scales": {"enabled": False},
    }

    with patch.object(trg, "get_active_trigger_names", return_value=["opencv"]), patch.object(
        trg,
        "effective_active_trigger_names_for_mqtt_status",
        return_value=["opencv"],
    ):
        trg.refresh_trigger_runtime_gauges(
            mqtt_broker=None,
            mqtt_aggregator=None,
            trigger_config=tc,
        )

    snap = prs.runtime_stats_snapshot()
    assert snap["gauges"]["trigger_mqtt_configured"] == 0
    assert snap["gauges"]["trigger_frigate_degraded_no_mqtt"] == 0

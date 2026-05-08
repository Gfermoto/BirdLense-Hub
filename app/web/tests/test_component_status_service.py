"""Юнит-тесты для services.component_status_service (MQTT в шапке)."""

from __future__ import annotations

from services.component_status_service import mqtt_display_for_ui


def test_mqtt_ui_web_error_overrides_heartbeat_ok():
    """Flask не подключается к брокеру — красный, даже если heartbeat ещё «ok»."""
    assert (
        mqtt_display_for_ui(
            mqtt_broker='192.168.1.2',
            feed_source='mqtt',
            mqtt_status_web='error',
            heartbeat_data={'mqtt_connected': True},
        )
        == 'error'
    )


def test_mqtt_ui_heartbeat_false_overrides_web_ok():
    """Процессор сообщил разрыв — красный даже при временном ok веб-клиента."""
    assert (
        mqtt_display_for_ui(
            mqtt_broker='192.168.1.2',
            feed_source='mqtt',
            mqtt_status_web='ok',
            heartbeat_data={'mqtt_connected': False},
        )
        == 'error'
    )


def test_mqtt_ui_both_ok():
    assert (
        mqtt_display_for_ui(
            mqtt_broker='192.168.1.2',
            feed_source='mqtt',
            mqtt_status_web='ok',
            heartbeat_data={'mqtt_connected': True},
        )
        == 'ok'
    )


def test_mqtt_ui_no_broker_feed_not_mqtt_not_used():
    assert (
        mqtt_display_for_ui(
            mqtt_broker='',
            feed_source='esphome',
            mqtt_status_web='ok',
            heartbeat_data={'mqtt_connected': True},
        )
        == 'not_used'
    )


def test_mqtt_ui_no_broker_feed_mqtt_uses_web():
    assert (
        mqtt_display_for_ui(
            mqtt_broker='',
            feed_source='mqtt',
            mqtt_status_web='not_configured',
            heartbeat_data=None,
        )
        == 'not_configured'
    )

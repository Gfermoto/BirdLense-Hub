"""Pydantic schemas for normalized MQTT events (#265)."""
import os
import sys

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(current_dir, '../src')))

pydantic = pytest.importorskip('pydantic')

from schemas.events import (  # noqa: E402
    BirdnetMqttEvent,
    FrigateMqttEvent,
    validate_mqtt_detection_dict,
)


def test_validate_frigate_round_trip():
    d = {
        'source': 'frigate',
        'species': 'Blue Tit',
        'label': 'bird',
        'sub_label': '',
        'confidence': 0.91,
        'camera': 'cam1',
        'timestamp': '2026-04-08T12:00:00+00:00',
    }
    m, err = validate_mqtt_detection_dict(d)
    assert err is None
    assert isinstance(m, FrigateMqttEvent)
    assert m.species == 'Blue Tit'


def test_validate_birdnet_optional_fields():
    d = {
        'source': 'birdnet',
        'species': 'Song Sparrow',
        'common_name': 'Song Sparrow',
        'confidence': 0.55,
        'timestamp': '2026-04-08T12:00:00+00:00',
        'scientific_name': 'Melospiza melodia',
    }
    m, err = validate_mqtt_detection_dict(d)
    assert err is None
    assert isinstance(m, BirdnetMqttEvent)


def test_validate_unknown_source():
    m, err = validate_mqtt_detection_dict({'source': 'other'})
    assert m is None
    assert err is not None

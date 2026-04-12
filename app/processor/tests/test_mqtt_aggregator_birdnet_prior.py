"""Tests for BirdNET rolling prior storage in MQTTEventAggregator."""

import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

# Wildcard topic matching must stay real: mqtt_aggregator uses +/# for Frigate snapshot
# and BirdNET subtrees. A naive ``sub == topic`` breaks other processor tests in the same
# pytest session (order-dependent flakes).
import paho.mqtt.client as _real_paho_client  # noqa: E402

fake_paho = types.ModuleType('paho')
fake_paho_mqtt = types.ModuleType('paho.mqtt')
fake_paho_mqtt_client = types.ModuleType('paho.mqtt.client')
fake_paho_mqtt_client.topic_matches_sub = _real_paho_client.topic_matches_sub
fake_paho_mqtt.client = fake_paho_mqtt_client
fake_paho.mqtt = fake_paho_mqtt
sys.modules.setdefault('paho', fake_paho)
sys.modules.setdefault('paho.mqtt', fake_paho_mqtt)
sys.modules.setdefault('paho.mqtt.client', fake_paho_mqtt_client)

from birdnet_merge_key import reset_birdnet_merge_key_cache_for_tests  # noqa: E402
from mqtt_aggregator import (
    MQTTEventAggregator,
    _parse_birdnet_event,
    _parse_birdnet_event_with_reason,
)  # noqa: E402


class TestBirdnetEventParsing(unittest.TestCase):
    def test_parse_birdnet_event_keeps_normalized_fields(self):
        payload = json.dumps(
            {
                "BeginTime": "2026-04-07T12:00:00Z",
                "CommonName": "Great Tit",
                "ScientificName": "Parus major",
                "SpeciesCode": "parmaj",
                "Confidence": 0.91,
                "Source": {"displayName": "garden_mic_1"},
                "SourceNode": "garden_mic_1",
            }
        ).encode("utf-8")
        event = _parse_birdnet_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event["species"], "Great Tit")
        self.assertEqual(event["common_name"], "Great Tit")
        self.assertEqual(event["scientific_name"], "Parus major")
        self.assertEqual(event["species_code"], "parmaj")
        self.assertEqual(event["audio_source"], "garden_mic_1")
        self.assertIn("_ts_epoch", event)




    def test_parse_birdnet_event_with_reason_code(self):
        payload = json.dumps({"CommonName": "Robin", "Confidence": 0.8}).encode("utf-8")
        event, reason = _parse_birdnet_event_with_reason(payload)
        self.assertIsNotNone(event)
        self.assertTrue(reason.startswith("ok_"))

class TestBirdnetRollingPrior(unittest.TestCase):
    def setUp(self):
        self.agg = MQTTEventAggregator(broker="127.0.0.1")

    def test_prior_uses_last_24_hours_and_expires_after_25(self):
        now = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)
        fresh = {
            "source": "birdnet",
            "species": "Great Tit",
            "confidence": 0.9,
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "_ts_epoch": (now - timedelta(hours=1)).timestamp(),
            "audio_source": "mic-1",
        }
        old_but_valid = {
            "source": "birdnet",
            "species": "Great Tit",
            "confidence": 0.4,
            "timestamp": (now - timedelta(hours=23)).isoformat(),
            "_ts_epoch": (now - timedelta(hours=23)).timestamp(),
            "audio_source": "mic-2",
        }
        expired = {
            "source": "birdnet",
            "species": "Blue Tit",
            "confidence": 0.95,
            "timestamp": (now - timedelta(hours=25, minutes=1)).isoformat(),
            "_ts_epoch": (now - timedelta(hours=25, minutes=1)).timestamp(),
            "audio_source": "mic-3",
        }
        self.agg._remember_birdnet_event(fresh)
        self.agg._remember_birdnet_event(old_but_valid)
        self.agg._remember_birdnet_event(expired)

        scores = self.agg.get_birdnet_prior_scores(
            now=now,
            window_hours=24,
            ttl_hours=25,
            half_life_hours=6,
        )
        self.assertIn("Great Tit", scores)
        self.assertNotIn("Blue Tit", scores)
        self.assertEqual(scores["Great Tit"]["support_count"], 2)
        self.assertEqual(scores["Great Tit"]["audio_sources"], ["mic-1", "mic-2"])

        kept = self.agg.get_birdnet_events(now=now, ttl_hours=25)
        kept_species = [ev["species"] for ev in kept]
        self.assertEqual(kept_species.count("Great Tit"), 2)
        self.assertNotIn("Blue Tit", kept_species)

    def test_prior_respects_min_confidence_and_decay(self):
        now = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)
        self.agg._remember_birdnet_event(
            {
                "source": "birdnet",
                "species": "Robin",
                "confidence": 0.8,
                "timestamp": now.isoformat(),
                "_ts_epoch": now.timestamp(),
            }
        )
        self.agg._remember_birdnet_event(
            {
                "source": "birdnet",
                "species": "Robin",
                "confidence": 0.1,
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "_ts_epoch": (now - timedelta(hours=1)).timestamp(),
            }
        )
        scores = self.agg.get_birdnet_prior_scores(
            now=now,
            window_hours=24,
            ttl_hours=25,
            half_life_hours=6,
            min_confidence=0.2,
        )
        self.assertIn("Robin", scores)
        self.assertEqual(scores["Robin"]["support_count"], 1)
        self.assertGreater(scores["Robin"]["score"], 0.79)

    def test_prior_buckets_by_canonical_name_from_scientific(self):
        reset_birdnet_merge_key_cache_for_tests()
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: (os.unlink(path) if os.path.isfile(path) else None))
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE species_taxon ("
            "id INTEGER PRIMARY KEY, taxon_key TEXT UNIQUE NOT NULL, "
            "scientific_name TEXT, common_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active')"
        )
        conn.execute(
            "CREATE TABLE species_alias ("
            "id INTEGER PRIMARY KEY, alias TEXT NOT NULL UNIQUE, "
            "alias_key TEXT NOT NULL, taxon_id INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO species_taxon (id, taxon_key, scientific_name, common_name) "
            "VALUES (1, 'pm', 'Parus major', 'Great Tit')"
        )
        conn.commit()
        conn.close()
        reset_birdnet_merge_key_cache_for_tests()

        now = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)
        self.agg._birdnet_merge_db_path = path
        self.agg._remember_birdnet_event(
            {
                "source": "birdnet",
                "species": "Большая синица",
                "common_name": "Большая синица",
                "scientific_name": "Parus major",
                "confidence": 0.9,
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "_ts_epoch": (now - timedelta(hours=1)).timestamp(),
            }
        )
        scores = self.agg.get_birdnet_prior_scores(
            now=now,
            window_hours=24,
            ttl_hours=25,
            half_life_hours=6,
        )
        self.assertIn("Great Tit", scores)
        self.assertNotIn("Большая синица", scores)
        reset_birdnet_merge_key_cache_for_tests()


if __name__ == "__main__":
    unittest.main()

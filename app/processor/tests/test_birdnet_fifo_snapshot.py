"""Снимок FIFO BirdNET для UI (агрегат без сырого MQTT)."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

_current = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_current, '../src')))
sys.path.insert(0, os.path.abspath(os.path.join(_current, '../..')))

from birdnet_fifo_snapshot import (
    build_birdnet_fifo_snapshot_payload,
    sanitize_birdnet_event_for_export,
    write_birdnet_fifo_snapshot,
)


class BirdnetFifoSnapshotTests(unittest.TestCase):
    def test_sanitize_strips_internal_keys(self):
        ev = {
            "species": "Robin",
            "confidence": 0.71,
            "timestamp": "2026-04-09T12:00:00+00:00",
            "_ts_epoch": 12345.0,
            "mqtt_topic": "secret/topic",
        }
        s = sanitize_birdnet_event_for_export(ev)
        self.assertEqual(s["species"], "Robin")
        self.assertNotIn("_ts_epoch", s)
        self.assertNotIn("mqtt_topic", s)

    def test_build_payload_counts_and_recent(self):
        events = [
            {
                "species": "A",
                "timestamp": "2026-04-09T10:00:00+00:00",
                "confidence": 0.5,
            },
            {
                "species": "B",
                "timestamp": "2026-04-09T11:00:00+00:00",
                "confidence": 0.6,
            },
            {
                "species": "A",
                "timestamp": "2026-04-09T12:00:00+00:00",
                "confidence": 0.7,
            },
        ]
        p = build_birdnet_fifo_snapshot_payload(
            events=events,
            fifo_cap=10000,
            mqtt_connected=True,
            processor_pid=4242,
            recent_limit=2,
        )
        self.assertEqual(p["queue_len"], 3)
        self.assertEqual(p["species_counts"]["A"], 2)
        self.assertEqual(p["species_counts"]["B"], 1)
        self.assertEqual(len(p["recent"]), 2)
        self.assertEqual(p["recent"][0]["species"], "B")
        self.assertEqual(p["processor_pid"], 4242)
        self.assertTrue(p["mqtt_connected"])
        self.assertIn("species_hearing", p)
        self.assertIn("fifo_fill_ratio", p)
        tbl = p.get("species_fifo_table")
        self.assertIsInstance(tbl, list)
        self.assertEqual(len(tbl), 2)
        labels = {r["display_label"] for r in tbl}
        self.assertEqual(labels, {"A", "B"})
        by_label = {r["display_label"]: r for r in tbl}
        self.assertEqual(by_label["A"]["event_count"], 2)
        self.assertEqual(by_label["B"]["event_count"], 1)
        for r in tbl:
            self.assertIn("active", r)
            self.assertIn("canonical_for_video", r)
            self.assertIn("seconds_since_heard", r)

    def test_species_hearing_active_within_window(self):
        base = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            {"species": "Fresh", "timestamp": base.isoformat(), "confidence": 0.5},
            {"species": "Stale", "timestamp": (base - timedelta(hours=30)).isoformat(), "confidence": 0.5},
        ]
        p = build_birdnet_fifo_snapshot_payload(
            events=events,
            fifo_cap=100,
            mqtt_connected=False,
            processor_pid=1,
            recent_limit=10,
            now=base,
            hearing_active_hours=24,
        )
        by_sp = p["species_hearing"]["by_species"]
        self.assertEqual(by_sp["Fresh"]["active"], 1)
        self.assertEqual(by_sp["Stale"]["active"], 0)
        self.assertEqual(p["fifo_fill_ratio"], 0.02)

    def test_write_creates_file(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        events = [
            {
                "species": "X",
                "timestamp": "2026-04-09T12:00:00+00:00",
                "confidence": 0.9,
            }
        ]
        write_birdnet_fifo_snapshot(
            data_dir=tmp,
            events=events,
            fifo_cap=500,
            mqtt_connected=False,
            processor_pid=1,
        )
        path = os.path.join(tmp, "diagnostics", "birdnet_fifo_snapshot.json")
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["queue_len"], 1)


if __name__ == "__main__":
    unittest.main()

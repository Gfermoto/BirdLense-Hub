"""Персистентность BirdNET FIFO в SQLite (#269)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from birdnet_fifo_persist import (
    BirdnetFifoPersist,
    hydrate_birdnet_events_from_db,
    hub_sqlite_path,
    prune_birdnet_event_list,
)


class BirdnetFifoPersistTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = hub_sqlite_path(self._tmp.name)

    def test_insert_hydrate_roundtrip(self):
        p = BirdnetFifoPersist(self.db_path, busy_timeout_ms=5000)
        p.start()
        now = datetime.now(timezone.utc)
        iso = now.isoformat()
        ev = {
            "species": "Test Sparrow",
            "confidence": 0.9,
            "timestamp": iso,
            "source": "birdnet",
            "_ts_epoch": now.timestamp(),
        }
        p.enqueue_insert(dict(ev))
        p.enqueue_prune(now.timestamp() - 3600 * 26, 10_000)
        p.wait_queue_drained()

        loaded = hydrate_birdnet_events_from_db(
            self.db_path,
            ttl_hours=25,
            cap=10_000,
            now=now,
        )
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].get("species"), "Test Sparrow")

    def test_prune_birdnet_event_list_matches_cap(self):
        base = datetime.now(timezone.utc)
        evs = []
        for i in range(5):
            t = base.timestamp() + i * 60
            evs.append(
                {
                    "species": f"S{i}",
                    "timestamp": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                    "_ts_epoch": t,
                }
            )
        cap = 3
        out = prune_birdnet_event_list(evs, now=base, ttl_hours=25, cap=cap)
        self.assertEqual(len(out), cap)
        self.assertEqual(out[-1].get("species"), "S4")

    def test_sqlite_payload_roundtrip_json(self):
        os.makedirs(os.path.join(self._tmp.name, "db"), exist_ok=True)
        import sqlite3

        now = datetime.now(timezone.utc)
        ts = now.timestamp()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE birdnet_fifo_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_epoch REAL NOT NULL,
                payload TEXT NOT NULL
            )""",
        )
        ev = {"species": "X", "timestamp": now.isoformat(), "_ts_epoch": ts}
        conn.execute(
            "INSERT INTO birdnet_fifo_event (ts_epoch, payload) VALUES (?, ?)",
            (ts, json.dumps(ev)),
        )
        conn.commit()
        conn.close()

        loaded = hydrate_birdnet_events_from_db(
            self.db_path,
            ttl_hours=25,
            cap=1000,
            now=now,
        )
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["species"], "X")

    def test_table_accumulates_multiple_rows(self):
        """Проверка накопления: несколько INSERT подряд увеличивают COUNT(*) в SQLite."""
        import sqlite3

        p = BirdnetFifoPersist(self.db_path, busy_timeout_ms=5000)
        p.start()
        base = datetime.now(timezone.utc)
        low = base.timestamp() - 3600 * 26
        n = 7
        for i in range(n):
            ts = base.timestamp() + i * 0.05
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            p.enqueue_insert(
                {
                    "species": f"Accum Finch {i}",
                    "confidence": 0.5 + i * 0.01,
                    "timestamp": dt.isoformat(),
                    "source": "birdnet",
                    "_ts_epoch": ts,
                }
            )
        p.enqueue_prune(low, 50_000)
        p.wait_queue_drained()

        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM birdnet_fifo_event").fetchone()[0]
            species = set()
            for (blob,) in conn.execute("SELECT payload FROM birdnet_fifo_event"):
                pl = json.loads(blob) if isinstance(blob, str) else json.loads(blob.decode("utf-8"))
                species.add(pl.get("species"))
        finally:
            conn.close()

        self.assertEqual(count, n, "ожидали по строке на каждое событие")
        self.assertEqual(len(species), n)
        for i in range(n):
            self.assertIn(f"Accum Finch {i}", species)


if __name__ == "__main__":
    unittest.main()

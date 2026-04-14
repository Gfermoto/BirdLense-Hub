"""Резолв ключа слияния BirdNET ↔ видео по научному имени и алиасам (SQLite hub)."""

import os
import sqlite3
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(current_dir, "../src")))

from birdnet_merge_key import (  # noqa: E402
    birdnet_merge_key,
    reset_birdnet_merge_key_cache_for_tests,
)


class TestBirdnetMergeKey(unittest.TestCase):
    def setUp(self):
        reset_birdnet_merge_key_cache_for_tests()

    def tearDown(self):
        reset_birdnet_merge_key_cache_for_tests()

    def _mk_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.unlink(path) if os.path.isfile(path) else None)
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
        conn.execute(
            "INSERT INTO species_alias (alias, alias_key, taxon_id) "
            "VALUES ('Большая синица', 'x', 1)"
        )
        conn.commit()
        conn.close()
        reset_birdnet_merge_key_cache_for_tests()
        return path

    def test_scientific_maps_ignoring_localized_common(self):
        path = self._mk_db()
        ev = {
            "species": "Большая синица",
            "common_name": "Большая синица",
            "scientific_name": "Parus major",
        }
        self.assertEqual(
            birdnet_merge_key(ev, {}, path),
            "Great Tit",
        )

    def test_alias_when_no_scientific(self):
        path = self._mk_db()
        ev = {"species": "Большая синица", "common_name": "Большая синица"}
        self.assertEqual(birdnet_merge_key(ev, {}, path), "Great Tit")

    def test_no_db_falls_back_to_normalize(self):
        ev = {"species": "eurasian_jay", "common_name": "eurasian_jay"}
        m = {"eurasian_jay": "Eurasian Jay"}
        self.assertEqual(birdnet_merge_key(ev, m, None), "Eurasian Jay")

    def test_yaml_scientific_overrides_russian_db_common_name(self):
        """species_mapping по Sci (EN) важнее русского common_name в SQLite."""
        path = self._mk_db()
        conn = sqlite3.connect(path)
        conn.execute(
            "UPDATE species_taxon SET common_name = 'Большая синица' WHERE id = 1"
        )
        conn.commit()
        conn.close()
        reset_birdnet_merge_key_cache_for_tests()
        mapping = {"Parus major (Great Tit)": "Great Tit"}
        ev = {
            "species": "Большая синица",
            "scientific_name": "Parus major",
        }
        self.assertEqual(birdnet_merge_key(ev, mapping, path), "Great Tit")

    def test_scientific_mapping_without_sqlite_file(self):
        ev = {"scientific_name": "Turdus iliacus", "species": "Белобровик"}
        m = {"Turdus iliacus (Redwing)": "Redwing"}
        self.assertEqual(birdnet_merge_key(ev, m, None), "Redwing")

    def test_yaml_canonical_keeps_ebird_hyphenation(self):
        """Значение из species_mapping не прогоняется через _to_title_case (Red-breasted, не Red-Breasted)."""
        m = {"Ficedula parva (Red-breasted Flycatcher)": "Red-breasted Flycatcher"}
        ev = {"scientific_name": "Ficedula parva", "species": "Малая мухоловка"}
        self.assertEqual(birdnet_merge_key(ev, m, None), "Red-breasted Flycatcher")


if __name__ == "__main__":
    unittest.main()

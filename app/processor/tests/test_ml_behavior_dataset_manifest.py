"""Synthetic tests for scripts/ml_behavior_dataset_manifest.py (Wave 1)."""

import importlib.util
import sys
import tempfile
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / 'scripts' / 'ml_behavior_dataset_manifest.py'
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location('ml_behavior_dataset_manifest', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['ml_behavior_dataset_manifest'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMlBehaviorDatasetManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_manifest_builds_taxonomy_and_splits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ann = root / 'ann'
            ann.mkdir(parents=True, exist_ok=True)
            (ann / 'clip_a.csv').write_text(
                '\n'.join(
                    [
                        '0,0,10,10,2,bird_1,Great Tit',
                        '0,0,10,10,2,bird_1,Great Tit',
                        '0,0,10,10,7,bird_1,Great Tit',
                    ]
                ),
                encoding='utf-8',
            )
            (ann / 'clip_b.csv').write_text(
                '\n'.join(
                    [
                        '0,0,10,10,3,bird_2,Magpie',
                        '0,0,10,10,1,bird_2,Magpie',
                    ]
                ),
                encoding='utf-8',
            )
            out = self.mod.build_behavior_dataset_manifest(
                annotations_root=str(ann),
                dataset_id='beh-001',
                split_seed=123,
            )

            self.assertEqual(out['schema'], 'behavior_dataset_manifest@v1')
            self.assertEqual(out['dataset_id'], 'beh-001')
            self.assertEqual(out['video_count'], 2)
            self.assertEqual(len(out['taxonomy']), 7)
            labels = {
                label
                for row in out['videos']
                for label in row.get('behavior_labels', [])
            }
            self.assertIn('feeding', labels)
            self.assertIn('walking', labels)
            self.assertTrue(all(row.get('split') in ('train', 'val', 'test') for row in out['videos']))

    def test_split_is_deterministic_for_same_seed(self):
        with tempfile.TemporaryDirectory() as td:
            ann = Path(td) / 'ann'
            ann.mkdir(parents=True, exist_ok=True)
            for i in range(6):
                (ann / f'clip_{i}.csv').write_text(
                    f'0,0,10,10,{(i % 7) + 1},bird_{i},Species',
                    encoding='utf-8',
                )
            first = self.mod.build_behavior_dataset_manifest(
                annotations_root=str(ann),
                dataset_id='beh-002',
                split_seed=77,
            )
            second = self.mod.build_behavior_dataset_manifest(
                annotations_root=str(ann),
                dataset_id='beh-002',
                split_seed=77,
            )
            first_split = {r['video_key']: r['split'] for r in first['videos']}
            second_split = {r['video_key']: r['split'] for r in second['videos']}
            self.assertEqual(first_split, second_split)


if __name__ == '__main__':
    unittest.main()

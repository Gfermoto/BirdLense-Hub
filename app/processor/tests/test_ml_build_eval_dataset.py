"""Synthetic tests for versioned eval dataset builder (#404)."""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / 'scripts' / 'ml_build_eval_dataset.py'
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location('ml_build_eval_dataset', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['ml_build_eval_dataset'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMlBuildEvalDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_build_manifest_with_labels(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            videos = root / 'videos'
            videos.mkdir(parents=True, exist_ok=True)
            (videos / 'clip1.mp4').write_bytes(b'video-1')
            (videos / 'clip2.mp4').write_bytes(b'video-2')

            labels = root / 'labels.json'
            labels.write_text(
                json.dumps(
                    {
                        'schema_version': 1,
                        'gold_by_basename': {
                            'clip1.mp4': ['Great Tit'],
                            'orphan.mp4': ['Bird'],
                        },
                    }
                ),
                encoding='utf-8',
            )

            manifest = self.mod.build_eval_dataset_manifest(
                videos_root=str(videos),
                labels_json=str(labels),
                dataset_id='eval-001',
            )

            self.assertEqual(manifest['schema'], 'eval_dataset_manifest@v1')
            self.assertEqual(manifest['dataset_id'], 'eval-001')
            self.assertEqual(manifest['video_count'], 2)
            self.assertEqual(len(manifest['files']), 2)
            self.assertTrue(all(len(row['sha256']) == 64 for row in manifest['files']))
            cov = manifest['labels_coverage']
            self.assertTrue(cov['labels_provided'])
            self.assertEqual(cov['labeled_basename_count'], 1)
            self.assertEqual(cov['videos_without_labels'], ['clip2.mp4'])
            self.assertEqual(cov['labels_without_videos'], ['orphan.mp4'])
            self.assertEqual(manifest['gold_labels']['gold_by_basename'], {'clip1.mp4': ['Great Tit']})

    def test_manifest_without_labels_is_supported(self):
        with tempfile.TemporaryDirectory() as td:
            videos = Path(td) / 'videos'
            videos.mkdir(parents=True, exist_ok=True)
            (videos / 'clip1.mkv').write_bytes(b'video-1')

            manifest = self.mod.build_eval_dataset_manifest(
                videos_root=str(videos),
                labels_json=None,
                dataset_id='eval-002',
                patterns=('*.mkv',),
            )

            self.assertEqual(manifest['dataset_id'], 'eval-002')
            self.assertEqual(manifest['video_count'], 1)
            self.assertIsNone(manifest['gold_labels'])
            self.assertFalse(manifest['labels_coverage']['labels_provided'])


if __name__ == '__main__':
    unittest.main()

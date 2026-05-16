"""Synthetic tests for scripts/ml_action_model_shortlist.py (#406)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, '../../..'))
_scripts_path = os.path.join(_repo_root, 'scripts')
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestMlActionModelShortlist(unittest.TestCase):
    """Action-model shortlist checks."""

    def test_default_shortlist_has_mvp(self):
        """Default shortlist should pick an MVP model."""
        from ml_action_model_shortlist import build_action_model_shortlist

        out = build_action_model_shortlist(min_dataset_clips=800)
        self.assertTrue(out['ok'])
        self.assertTrue(out['gates']['mvp_selected'])
        self.assertTrue(out['mvp_model']['id'])

    def test_dataset_gate_fails_when_too_small(self):
        """Dataset gate fails for tiny clip counts."""
        from ml_action_model_shortlist import build_action_model_shortlist

        out = build_action_model_shortlist(min_dataset_clips=120)
        self.assertFalse(out['ok'])
        self.assertFalse(out['gates']['dataset_minimum_ok'])


if __name__ == '__main__':
    unittest.main()
